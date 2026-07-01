"""核心接口定义

使用 Protocol 定义接口，支持鸭子类型和依赖注入。
"""

from typing import Any, Callable, Optional, Protocol, runtime_checkable

from utils.check import default_check_html


@runtime_checkable
class HttpClient(Protocol):
    """HTTP 客户端接口（异步）"""

    async def get(
        self,
        url: str,
        timeout: int = 30,
        headers: Optional[dict[str, str]] = None,
        check_html: Callable[[str], bool] = default_check_html,
    ) -> str:
        """发送 GET 请求并返回响应内容"""
        ...

    async def get_raw(
        self,
        url: str,
        proxy: Optional[str] = None,
        timeout: int = 30,
        headers: Optional[dict[str, str]] = None,
    ) -> bytes:
        """发送 GET 请求并返回二进制响应内容"""
        ...

    async def post(
        self,
        url: str,
        json: Optional[dict[str, Any]] = None,
        timeout: int = 30,
        headers: Optional[dict[str, str]] = None,
    ) -> str:
        """发送 POST 请求并返回响应内容"""
        ...
