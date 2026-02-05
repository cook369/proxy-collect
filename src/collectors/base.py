"""采集器基类和注册表"""

from abc import ABC, abstractmethod
import logging
from pathlib import Path
from typing import Optional, Union

import yaml

from core.models import CollectorResult, DownloadTask, FileManifest, ProxyInfo
from core.interfaces import HttpClient
from core.exceptions import NetworkError, DownloadError, ValidationError

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
        if http_client is None:
            from services.http_service import HttpService, ProxyPool, ProxyHttpService

            http_service = HttpService()
            if proxies_list:
                proxy_pool = ProxyPool(proxies_list)
                self.http_client = ProxyHttpService(http_service, proxy_pool)
            else:
                self.http_client = http_service
        else:
            self.http_client = http_client

    def fetch_html(self, url: str) -> str:
        """获取 HTML 内容

        Args:
            url: 请求 URL

        Returns:
            HTML 内容

        Raises:
            NetworkError: 网络请求失败
        """
        if not self.http_client:
            raise NetworkError("HTTP client not initialized", url, self.name)

        logging.info(f"[{self.name}] Fetching: {url}")
        try:
            return self.http_client.get(url, timeout=20)
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
            content = self.fetch_html(task.url)

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

    def run(self, output_dir: Path) -> CollectorResult:
        """执行采集

        Args:
            output_dir: 输出目录

        Returns:
            采集结果
        """
        logging.info(f"[{self.name}] Start collector")
        files: dict[str, FileManifest] = {}
        error_msg: str | None = None

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

        except Exception as e:
            error_msg = str(e)
            logging.error(f"[{self.name}] Error: {e}")

        logging.info(f"[{self.name}] Collector finished")

        # 计算状态
        if error_msg and not files:
            status = "failed"
        elif all(f.success for f in files.values()):
            status = "success"
        elif any(f.success for f in files.values()):
            status = "partial"
        else:
            status = "failed"

        return CollectorResult(
            site=self.name,
            today_page=getattr(self, "today_page", None),
            files=files,
            status=status,
            error=error_msg,
        )


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
    "CollectorResult",
    "register_collector",
    "list_collectors",
    "get_collector",
]
