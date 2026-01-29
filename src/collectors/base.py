"""采集器基类和注册表

简化版本：移除 ProxyManager 和 DownloadRecord，通过依赖注入接收服务。
"""
from abc import ABC, abstractmethod
import logging
from pathlib import Path
from typing import Optional

# 从新模块导入
from core.models import CollectorResult, DownloadTask
from core.interfaces import HttpClient, RecordStorage

# 采集器注册表
COLLECTOR_REGISTRY: dict[str, type["BaseCollector"]] = {}


class BaseCollector(ABC):
    """采集器基类 - 简化版本，通过依赖注入接收服务"""

    name: str
    home_page: str

    def __init__(
        self,
        proxies_list: Optional[list[str]] = None,
        http_client: Optional[HttpClient] = None,
        record_storage: Optional[RecordStorage] = None
    ):
        """初始化采集器（支持两种方式）

        Args:
            proxies_list: 代理列表（旧方式，向后兼容）
            http_client: HTTP 客户端（新方式，依赖注入）
            record_storage: 记录存储（新方式，依赖注入）
        """
        if http_client is None:
            # 旧方式：从 proxies_list 创建服务
            from services.http_service import HttpService, ProxyPool, ProxyHttpService
            http_service = HttpService()
            if proxies_list:
                proxy_pool = ProxyPool(proxies_list)
                self.http_client = ProxyHttpService(http_service, proxy_pool)
            else:
                self.http_client = http_service
        else:
            # 新方式：使用传入的服务
            self.http_client = http_client

        self.record_storage = record_storage

    def fetch_html(self, url: str) -> str:
        """获取 HTML 内容

        Args:
            url: 请求 URL

        Returns:
            HTML 内容
        """
        if not self.http_client:
            raise RuntimeError("HTTP client not initialized")

        logging.info(f"[{self.name}] Fetching: {url}")
        return self.http_client.get(url, timeout=20)

    @abstractmethod
    def get_download_urls(self) -> list[tuple[str, str]]:
        """获取下载 URL 列表（子类实现）

        Returns:
            (文件名, URL) 元组列表
        """
        raise NotImplementedError

    def download_file(self, filename: str, url: str, output_dir: Path) -> bool:
        """下载单个文件

        Args:
            filename: 文件名
            url: 下载 URL
            output_dir: 输出目录

        Returns:
            是否成功
        """
        try:
            content = self.fetch_html(url)

            file_path = output_dir / self.name / filename
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")

            logging.info(f"[{self.name}] Saved to: {file_path}")
            return True

        except Exception as e:
            logging.error(f"[{self.name}] Failed to download {url}: {e}")
            return False

    def run(self, output_dir: Path) -> CollectorResult:
        """执行采集

        Args:
            output_dir: 输出目录

        Returns:
            采集结果
        """
        logging.info(f"[{self.name}] Start collector")
        result = "success"
        urls: list[tuple[str, str]] = []
        url_status: dict[str, bool] = {}

        try:
            # 获取下载 URL
            urls = self.get_download_urls()
            logging.info(f"[{self.name}] Found {len(urls)} URLs")

            # 下载文件
            for filename, url in urls:
                # 检查是否已下载
                if self.record_storage and self.record_storage.is_downloaded(self.name, url):
                    url_status[url] = True
                    continue

                # 下载文件
                success = self.download_file(filename, url, output_dir)
                url_status[url] = success

            # 更新记录
            if self.record_storage:
                self.record_storage.update_site(self.name, url_status)
                self.record_storage.save()

        except Exception as e:
            result = "failed"
            logging.error(f"[{self.name}] Error: {e}")

        logging.info(f"[{self.name}] Collector finished")

        # 构建结果
        all_urls = [url for _, url in urls]
        tried_urls = [url for url in url_status if url in all_urls]
        success_urls = [url for url, ok in url_status.items() if ok]
        failed_urls = [url for url, ok in url_status.items() if not ok]

        return CollectorResult(
            site=self.name,
            all_urls=all_urls,
            tried_urls=tried_urls,
            success_urls=success_urls,
            failed_urls=failed_urls,
            url_status=url_status,
            result=result,
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


# -------------------- 向后兼容 -------------------- #

# 为了向后兼容，从服务层导入并重新导出
from services.record_service import RecordService as DownloadRecord

__all__ = [
    "BaseCollector",
    "CollectorResult",
    "DownloadRecord",
    "register_collector",
    "list_collectors",
    "get_collector",
]
