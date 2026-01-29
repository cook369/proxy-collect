"""核心数据模型

纯数据模型，不包含业务逻辑。
"""
from dataclasses import dataclass, field


@dataclass
class CollectorResult:
    """采集器执行结果"""

    site: str
    all_urls: list[str]
    tried_urls: list[str]
    success_urls: list[str]
    failed_urls: list[str]
    url_status: dict[str, bool]
    result: str  # "success" or "failed"


@dataclass
class DownloadTask:
    """下载任务"""

    filename: str
    url: str
    site: str


@dataclass
class ProxyInfo:
    """代理信息"""

    url: str
    priority: int = 0
    success_count: int = 0
    fail_count: int = 0
