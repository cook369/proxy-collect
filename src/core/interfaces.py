"""核心接口定义

使用 Protocol 定义接口，支持鸭子类型和依赖注入。
"""
from typing import Protocol, runtime_checkable
from pathlib import Path
from core.models import CollectorResult


@runtime_checkable
class HttpClient(Protocol):
    """HTTP 客户端接口"""

    def get(self, url: str, timeout: int = 30) -> str:
        """发送 GET 请求并返回响应内容"""
        ...


@runtime_checkable
class RecordStorage(Protocol):
    """记录存储接口"""

    def is_downloaded(self, site: str, url: str) -> bool:
        """检查 URL 是否已下载"""
        ...

    def update_site(self, site: str, data: dict[str, bool]) -> None:
        """更新站点记录"""
        ...

    def save(self) -> None:
        """保存记录到文件"""
        ...


@runtime_checkable
class ReportGenerator(Protocol):
    """报告生成器接口"""

    def generate(self, results: list[CollectorResult]) -> str:
        """生成报告内容"""
        ...

    def save(self, content: str, file_path: Path) -> None:
        """保存报告到文件"""
        ...
