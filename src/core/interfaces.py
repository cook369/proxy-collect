"""核心接口定义

使用 Protocol 定义接口，支持鸭子类型和依赖注入。
"""

from collections.abc import Callable
from typing import Any, Protocol, runtime_checkable

from utils.check import default_check_html


@runtime_checkable
class HttpClient(Protocol):
    """HTTP 客户端接口"""

    def get(
        self,
        url: str,
        timeout: int = 30,
        headers: dict[str, str] | None = None,
        check_html: Callable[[str], bool] = default_check_html,
    ) -> str:
        """发送 GET 请求并返回响应内容"""
        ...

    def get_raw(
        self,
        url: str,
        proxy: str | None = None,
        timeout: int = 30,
        headers: dict[str, str] | None = None,
    ) -> bytes:
        """发送 GET 请求并返回二进制响应内容"""
        ...

    def post(
        self,
        url: str,
        json: dict[str, Any] | None = None,
        timeout: int = 30,
        headers: dict[str, str] | None = None,
    ) -> str:
        """发送 POST 请求并返回响应内容"""
        ...
