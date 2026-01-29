"""核心接口定义

使用 Protocol 定义接口，支持鸭子类型和依赖注入。
"""

from typing import Protocol, runtime_checkable


@runtime_checkable
class HttpClient(Protocol):
    """HTTP 客户端接口"""

    def get(self, url: str, timeout: int = 30) -> str:
        """发送 GET 请求并返回响应内容"""
        ...
