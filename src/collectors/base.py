"""采集器基类和注册表"""

from abc import ABC, abstractmethod
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Union, Callable

import yaml

from core.models import CollectorResult, DownloadTask, FileManifest, ProxyInfo
from core.interfaces import HttpClient
from core.exceptions import NetworkError, DownloadError, ValidationError
from config.settings import default_config
from utils.check import default_check_html, check_html_contains
from utils.extractors import create_download_tasks_from_regex_rules
from utils.youtube import extract_youtube_redirect_url, find_latest_video_url, extract_video_title
from services.paste_to_service import PasteToService

# 内容验证常量
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
MIN_FILE_SIZE = 100  # 100 bytes

# 采集器注册表
COLLECTOR_REGISTRY: dict[str, type["BaseCollector"]] = {}


class BaseCollector(ABC):
    """采集器基类"""

    name: str
    home_page: str
    today_page: str | None = None  # 今日页面 URL（由 mixin 设置）
    _current_output_dir: Path | None = None

    def __init__(
        self,
        proxies_list: Optional[Union[list[str], list[ProxyInfo]]] = None,
        http_client: Optional[HttpClient] = None,
    ):
        """初始化采集器

        Args:
            proxies_list: 代理列表（支持字符串或 ProxyInfo）
            http_client: HTTP 客户端（新方式，依赖注入）
        """
        self.proxy_pool = None
        if http_client is None:
            from services.http_service import HttpService, ProxyPool, ProxyHttpService

            http_service = HttpService()
            if proxies_list:
                self.proxy_pool = ProxyPool(proxies_list)
                self.http_client = ProxyHttpService(http_service, self.proxy_pool)
            else:
                self.http_client = http_service
        else:
            self.http_client = http_client

    def fetch_html(
        self,
        url: str,
        timeout: int = default_config.collector.fetch_timeout,
        check_html: Callable[[str], bool] = default_check_html,
    ) -> str:
        """获取 HTML 内容

        Args:
            url: 请求 URL
            check_html: HTML 内容检查函数
        Returns:
            HTML 内容

        Raises:
            NetworkError: 网络请求失败
        """
        if not self.http_client:
            raise NetworkError("HTTP client not initialized", url, self.name)

        logging.info(f"[{self.name}] Fetching: {url}")
        try:
            return self.http_client.get(
                url,
                timeout=timeout,
                check_html=check_html,
            )
        except Exception as e:
            raise NetworkError(str(e), url, self.name) from e

    def fetch_data(
        self,
        url: str,
        timeout: int = default_config.collector.fetch_timeout,
    ) -> bytes:
        """获取二进制内容

        Args:
            url: 请求 URL
            timeout: 请求超时时间（秒）
        Returns:
            二进制响应内容

        Raises:
            NetworkError: 网络请求失败
        """
        if not self.http_client:
            raise NetworkError("HTTP client not initialized", url, self.name)

        logging.info(f"[{self.name}] Fetching: {url}")
        try:
            return self.http_client.get_raw(
                url,
                timeout=timeout,
            )
        except Exception as e:
            raise NetworkError(str(e), url, self.name) from e

    @abstractmethod
    def get_download_tasks(self) -> list[DownloadTask]:
        """获取下载任务列表（子类实现）

        Returns:
            DownloadTask 列表
        """
        raise NotImplementedError

    def validate_content(self, content: str, filename: str) -> None:
        """验证下载内容

        Args:
            content: 文件内容
            filename: 文件名

        Raises:
            ValidationError: 内容验证失败
        """
        # 检查文件大小
        content_size = len(content.encode("utf-8"))
        if content_size > MAX_FILE_SIZE:
            raise ValidationError(
                f"File too large: {content_size} bytes (max {MAX_FILE_SIZE})",
                filename,
                self.name,
            )
        if content_size < MIN_FILE_SIZE:
            raise ValidationError(
                f"File too small: {content_size} bytes (min {MIN_FILE_SIZE})",
                filename,
                self.name,
            )

        # 验证 YAML 格式
        if filename.endswith((".yaml", ".yml")):
            try:
                yaml.safe_load(content)
            except yaml.YAMLError as e:
                raise ValidationError(
                    f"Invalid YAML format: {e}",
                    filename,
                    self.name,
                ) from e

    def download_file(self, task: DownloadTask, output_dir: Path) -> bool:
        """下载单个文件

        Args:
            task: 下载任务
            output_dir: 输出目录

        Returns:
            是否成功
        """
        try:
            content = ""
            if task.url:
                content = self.fetch_html(task.url)
            if task.data:
                content = task.data

            if not content:
                raise ValidationError(f"empty content for {task.filename}")

            # 应用内容处理器
            if task.processor:
                content = task.processor(content)

            # 验证内容
            self.validate_content(content, task.filename)

            file_path = output_dir / self.name / task.filename
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")

            logging.info(f"[{self.name}] Saved to: {file_path}")
            return True

        except ValidationError as e:
            logging.warning(f"[{self.name}] Validation failed for {task.filename}: {e}")
            return False
        except NetworkError as e:
            logging.error(f"[{self.name}] Network error downloading {task.url}: {e}")
            return False
        except Exception as e:
            raise DownloadError(str(e), task.url, task.filename, self.name) from e

    def get_cached_result(
        self, output_dir: Path | None = None
    ) -> CollectorResult | None:
        """获取已采集过同一 today_page 的缓存结果"""
        today_page = getattr(self, "today_page", None)
        if not today_page:
            return None

        from services.manifest_service import ManifestService

        output_dir = (
            output_dir or self._current_output_dir or default_config.app.output_dir
        )
        manifest = ManifestService(default_config.app.manifest_file)
        site = manifest.get_site(self.name)
        if not site or site.status != "success" or site.today_page != today_page:
            return None

        for filename, file_info in site.files.items():
            if file_info.success and not (output_dir / self.name / filename).exists():
                return None

        return CollectorResult(
            site=self.name,
            today_page=site.today_page,
            files=site.files,
            status=site.status,
            error=site.error,
            from_cache=True,
        )

    def skip_if_cached(self, output_dir: Path | None = None) -> None:
        """如果当前 today_page 已成功采集过，则中断当前采集并复用缓存结果"""
        cached_result = self.get_cached_result(output_dir)
        if cached_result:
            logging.info(f"[{self.name}] Already collected {self.today_page}, skip")
            raise CachedCollectorResult(cached_result)

    def run(self, output_dir: Path, timestamp: str | None = None) -> CollectorResult:
        """执行采集

        Args:
            output_dir: 输出目录

        Returns:
            采集结果
        """
        logging.info(f"[{self.name}] Start collector")
        start_time = time.time()
        files: dict[str, FileManifest] = {}
        error_msg: str | None = None
        self._current_output_dir = output_dir

        try:
            tasks = self.get_download_tasks()
            logging.info(f"[{self.name}] Found {len(tasks)} tasks")

            for task in tasks:
                success = self.download_file(task, output_dir)
                files[task.filename] = FileManifest(
                    url=task.url,
                    success=success,
                    error=None if success else "Download failed",
                )
        except CachedCollectorResult as e:
            logging.info(f"[{self.name}] Collector skipped by cache")
            e.result.duration_seconds = round(time.time() - start_time, 1)
            return e.result

        except Exception as e:
            error_msg = str(e)
            logging.error(f"[{self.name}] Error: {e}")

        duration = round(time.time() - start_time, 1)
        logging.info(f"[{self.name}] Collector finished in {duration}s")

        # 计算状态
        if error_msg and not files:
            status = "failed"
        elif all(f.success for f in files.values()):
            status = "success"
        elif any(f.success for f in files.values()):
            status = "partial"
        else:
            status = "failed"

        # 每个采集器使用自己完成时的实际时间
        ts = timestamp or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        return CollectorResult(
            site=self.name,
            today_page=getattr(self, "today_page", None),
            title=getattr(self, "title", None),
            collected_at=ts,
            files=files,
            status=status,
            error=error_msg,
            duration_seconds=duration,
        )


class CachedCollectorResult(Exception):
    """内部控制流：复用已采集结果并跳过后续解析/下载"""

    def __init__(self, result: CollectorResult):
        super().__init__("collector result cached")
        self.result = result


# -------------------- YouTube 采集器基类 -------------------- #


class YouTubeBaseCollector(BaseCollector):
    """YouTube 采集器基类

    公共骨架: 首页 → 找最新视频 → 拉视频页 → 提取重定向 URL → 处理内容
    子类实现 get_today_url / resolve_tasks_from_redirect。

    子类需定义:
        home_page: YouTube 首页/播放列表 URL
        redirect_target_host: 重定向目标域名（如 "paste.to"、"drive.google.com"）
        home_check_keyword: 首页 HTML 校验关键字（默认 "免费节点"）
    """

    redirect_target_host: str = ""
    home_check_keyword: str = "免费节点"

    def get_download_tasks(self) -> list[DownloadTask]:
        """从 YouTube 最新视频中提取订阅任务"""
        check_html = check_html_contains(self.home_check_keyword)
        if not self.today_page:
            home_html = self.fetch_html(self.home_page, check_html=check_html)
            self.today_page, self.title = self.get_today_url(home_html)
        self.skip_if_cached()

        video_html = self.fetch_html(self.today_page)
        # 用视频页面 HTML 重新提取标题，避免从首页/播放列表取到不准确的值
        video_title = extract_video_title(video_html)
        if video_title:
            self.title = video_title
        target_url = self.extract_redirect_url(video_html)

        logging.info(f"[{self.name}] processing redirect: {target_url}")
        return self.resolve_tasks_from_redirect(target_url)

    def extract_redirect_url(self, video_html: str) -> str:
        """从 YouTube 视频页提取重定向目标 URL"""
        return extract_youtube_redirect_url(video_html, self.redirect_target_host)

    @abstractmethod
    def get_today_url(self, home_html: str) -> tuple[str, str]:
        """从首页 HTML 提取最新视频 (url, title)（子类实现）"""
        raise NotImplementedError

    @abstractmethod
    def resolve_tasks_from_redirect(
        self, target_url: str
    ) -> list[DownloadTask]:
        """处理重定向目标 URL 并提取下载任务（子类实现）"""
        raise NotImplementedError


# -------------------- YouTube + Paste.to 采集器基类 -------------------- #


class YouTubePasteToCollector(YouTubeBaseCollector):
    """YouTube + Paste.to 采集器基类

    适用于从 YouTube 播放列表找最新视频，从视频描述提取 paste.to 分享链接，
    解密后提取订阅链接的采集器。

    子类需定义:
        home_page: YouTube 播放列表 URL
        playlist_keywords: 匹配视频标题的关键字元组
    """

    redirect_target_host = "paste.to"
    playlist_keywords: tuple[str, ...] = ("免费节点",)
    paste_to_password: str | None = None
    paste_to_password_strategy: (
        "CharsetPasswordStrategy | DictionaryPasswordStrategy | None"
    ) = None

    def get_today_url(self, home_html: str) -> tuple[str, str]:
        """从 YouTube 播放列表页面提取最新视频 (url, title)"""
        video, title = find_latest_video_url(
            home_html,
            self.playlist_keywords,
            reverse=False,
        )
        logging.info(f"[{self.name}] find video {video}, title {title}")
        return video, title

    def extract_paste_url(self, video_html: str) -> str:
        """从 YouTube 视频页提取 paste.to 分享 URL（公开，供测试调用）"""
        return extract_youtube_redirect_url(video_html, self.redirect_target_host)

    def resolve_tasks_from_redirect(
        self, target_url: str
    ) -> list[DownloadTask]:
        """解密 paste.to 分享链接并提取订阅任务"""
        paste_to_service = PasteToService(
            http_client=self.http_client,
            timeout=default_config.collector.fetch_timeout,
            max_workers=default_config.collector.paste_to_password_workers,
            password_strategy=self.paste_to_password_strategy,
        )
        decrypt_result = paste_to_service.decrypt_url(
            target_url,
            password=self.paste_to_password,
        )
        if not self.paste_to_password:
            logging.info(
                f"[{self.name}] password decrypt {target_url} "
                f"with {decrypt_result.password} share"
            )
        return self.parse_subscription_tasks(decrypt_result.content)

    @abstractmethod
    def parse_subscription_tasks(self, content: str) -> list[DownloadTask]:
        """从解密后的分享内容提取订阅链接（子类实现）"""
        raise NotImplementedError


# -------------------- 采集器注册表 -------------------- #


def register_collector(cls: type[BaseCollector]):
    """注册采集器子类

    Args:
        cls: 采集器类

    Returns:
        采集器类（用于装饰器）
    """
    name = cls.name
    if name in COLLECTOR_REGISTRY:
        raise ValueError(f"Collector {name} already registered")
    COLLECTOR_REGISTRY[name] = cls
    return cls


def list_collectors() -> list[str]:
    """列出所有已注册的采集器名称

    Returns:
        采集器名称列表
    """
    return list(COLLECTOR_REGISTRY.keys())


def get_collector(name: str) -> type[BaseCollector]:
    """获取指定名称的采集器类

    Args:
        name: 采集器名称

    Returns:
        采集器类

    Raises:
        ValueError: 采集器未注册
    """
    if name not in COLLECTOR_REGISTRY:
        raise ValueError(f"No collector registered under name: {name}")
    return COLLECTOR_REGISTRY[name]


__all__ = [
    "BaseCollector",
    "YouTubeBaseCollector",
    "YouTubePasteToCollector",
    "CollectorResult",
    "register_collector",
    "list_collectors",
    "get_collector",
]
