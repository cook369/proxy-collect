"""HTTP 请求服务（异步版本）

提供基于 aiohttp 的异步 HTTP 请求和支持代理池的 HTTP 请求服务。
"""

import asyncio
import logging
import time
from typing import Any, Callable, Iterator, Optional, Union

import aiohttp
from aiohttp_socks import ProxyConnector, ProxyType as SocksProxyType
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from core.exceptions import ProxyError
from core.models import ProxyInfo, ProxyType
from utils.check import default_check_html

# 代理竞速默认批大小：每批并发尝试的代理数
DEFAULT_PROXY_BATCH_SIZE = 5


def _chunked(items: list, size: int) -> Iterator[list]:
    """按固定大小切分列表（最后一块可能更短）"""
    for start in range(0, len(items), size):
        yield items[start : start + size]


def _proxy_url_to_socks_type(proxy_info: ProxyInfo) -> SocksProxyType:
    """将内部 ProxyType 映射到 aiohttp-socks 类型"""
    mapping = {
        ProxyType.SOCKS5: SocksProxyType.SOCKS5,
        ProxyType.SOCKS4: SocksProxyType.SOCKS4,
        ProxyType.HTTP: SocksProxyType.HTTP,
        ProxyType.HTTPS: SocksProxyType.HTTP,
    }
    return mapping.get(proxy_info.proxy_type, SocksProxyType.SOCKS5)


class HttpService:
    """基础 HTTP 请求服务（异步）"""

    def __init__(
        self,
        session: Optional[aiohttp.ClientSession] = None,
        verify_ssl: bool = False,
    ):
        """初始化 HTTP 服务

        Args:
            session: 可选的 aiohttp.ClientSession 实例
            verify_ssl: 是否验证 SSL 证书（默认 False，因为代理站点证书可能有问题）
        """
        self.verify_ssl = verify_ssl
        self._own_session = session is None
        self._session = session  # 延迟初始化，需要 event loop

    @property
    def session(self) -> aiohttp.ClientSession:
        """延迟获取或创建 session（需要 event loop）"""
        if self._session is None:
            self._session = self._create_session()
        return self._session

    @session.setter
    def session(self, value: Optional[aiohttp.ClientSession]):
        self._session = value

    def _create_session(self) -> aiohttp.ClientSession:
        """创建 HTTP 会话（无代理）"""
        connector = aiohttp.TCPConnector(
            limit=60,
            limit_per_host=60,
            ssl=self.verify_ssl,
        )
        session = aiohttp.ClientSession(
            connector=connector,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
            },
        )
        return session

    def _create_proxy_connector(self, proxy_info: ProxyInfo) -> ProxyConnector:
        """为指定代理创建 SOCKS connector"""
        socks_type = _proxy_url_to_socks_type(proxy_info)
        return ProxyConnector(
            proxy_type=socks_type,
            host=proxy_info.host,
            port=proxy_info.port,
            ssl=self.verify_ssl,
            limit=1,
        )

    async def close(self) -> None:
        """关闭 HTTP 会话"""
        if self._own_session and self.session is not None:
            await self.session.close()
            self.session = None

    async def _get(
        self,
        url: str,
        timeout: int = 30,
        headers: Optional[dict[str, str]] = None,
        check_html: Callable[[str], bool] = default_check_html,
        proxy_info: Optional[ProxyInfo] = None,
    ) -> str:
        """发送单次 GET 请求（不重试）

        供代理竞速等场景使用：单代理失败应立即让位给其它代理，而不是在同一
        代理上重试，以免被放弃的请求因重试被拖到 3×timeout，影响收尾。
        """
        if proxy_info:
            # 使用代理：创建临时 connector
            connector = self._create_proxy_connector(proxy_info)
            kwargs: dict[str, Any] = {
                "connector": connector,
                "headers": headers or {},
                "timeout": aiohttp.ClientTimeout(
                    total=timeout,
                    sock_connect=timeout,
                ),
            }
            async with aiohttp.ClientSession(**kwargs) as session:
                async with session.get(url) as resp:
                    resp.raise_for_status()
                    text = await resp.text(encoding="utf-8")
        else:
            # 直连：使用共享 session
            req_kwargs: dict[str, Any] = {
                "timeout": aiohttp.ClientTimeout(total=timeout, sock_connect=timeout),
            }
            if headers:
                req_kwargs["headers"] = headers
            async with self.session.get(url, **req_kwargs) as resp:
                resp.raise_for_status()
                text = await resp.text(encoding="utf-8")

        if not text.strip():
            raise ValueError("Empty response")
        if not check_html(text):
            raise ValueError("Response content failed validation")

        return text

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((aiohttp.ClientError, ValueError, asyncio.TimeoutError)),
        reraise=True,
    )
    async def get(
        self,
        url: str,
        proxy: Optional[str] = None,
        timeout: int = 30,
        headers: Optional[dict[str, str]] = None,
        check_html: Callable[[str], bool] = default_check_html,
    ) -> str:
        """发送 GET 请求（带重试）

        Args:
            url: 请求 URL
            proxy: 代理 URL（可选，如 "socks5://host:port"）
            timeout: 超时时间（秒）

        Returns:
            响应内容

        Raises:
            aiohttp.ClientError: HTTP 错误
            ValueError: 响应内容为空
        """
        proxy_info = ProxyPool.parse_proxy_url(proxy) if proxy else None
        return await self._get(
            url, timeout=timeout, headers=headers, check_html=check_html,
            proxy_info=proxy_info,
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError)),
        reraise=True,
    )
    async def post(
        self,
        url: str,
        json: Optional[dict[str, Any]] = None,
        proxy: Optional[str] = None,
        timeout: int = 30,
        headers: Optional[dict[str, str]] = None,
    ) -> str:
        """发送 POST 请求（带重试）

        Args:
            url: 请求 URL
            json: JSON 请求体
            proxy: 代理 URL（可选）
            timeout: 超时时间（秒）
            headers: 额外的请求头

        Returns:
            响应内容
        """
        if proxy:
            info = ProxyPool.parse_proxy_url(proxy)
            connector = self._create_proxy_connector(info) if info else None
        else:
            connector = None

        kwargs: dict[str, Any] = {
            "timeout": aiohttp.ClientTimeout(total=timeout, sock_connect=timeout),
        }
        if headers:
            kwargs["headers"] = headers
        if json is not None:
            kwargs["json"] = json

        if connector:
            kwargs["connector"] = connector
            async with aiohttp.ClientSession(**kwargs) as session:
                async with session.post(url) as resp:
                    resp.raise_for_status()
                    text = await resp.text(encoding="utf-8")
        else:
            async with self.session.post(url, **kwargs) as resp:
                resp.raise_for_status()
                text = await resp.text(encoding="utf-8")

        if not text.strip():
            raise ValueError("Empty response")
        return text

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError)),
        reraise=True,
    )
    async def get_raw(
        self,
        url: str,
        proxy: Optional[str] = None,
        timeout: int = 30,
        headers: Optional[dict[str, str]] = None,
    ) -> bytes:
        """发送 GET 请求获取二进制内容

        Args:
            url: 请求 URL
            proxy: 代理 URL（可选）
            timeout: 超时时间（秒）

        Returns:
            二进制响应内容
        """
        if proxy:
            info = ProxyPool.parse_proxy_url(proxy)
            connector = self._create_proxy_connector(info) if info else None
        else:
            connector = None

        kwargs: dict[str, Any] = {
            "timeout": aiohttp.ClientTimeout(total=timeout, sock_connect=timeout),
        }
        if headers:
            kwargs["headers"] = headers

        if connector:
            kwargs["connector"] = connector
            async with aiohttp.ClientSession(**kwargs) as session:
                async with session.get(url) as resp:
                    resp.raise_for_status()
                    content = await resp.read()
        else:
            async with self.session.get(url, **kwargs) as resp:
                resp.raise_for_status()
                content = await resp.read()

        if not content:
            raise ValueError("Empty response")
        return content


class ProxyPool:
    """代理池管理（异步）"""

    def __init__(self, proxies: Optional[Union[list[str], list[ProxyInfo]]] = None):
        self._lock = asyncio.Lock()
        self._proxies: dict[str, ProxyInfo] = {}

        if proxies:
            for proxy in proxies:
                self._add_proxy(proxy)

    def _add_proxy(self, proxy: Union[str, ProxyInfo]) -> None:
        """内部添加代理（不加锁，调用方需持有锁）"""
        if isinstance(proxy, str):
            proxy_info = self._parse_proxy_string(proxy)
        else:
            proxy_info = proxy

        if proxy_info:
            key = f"{proxy_info.host}:{proxy_info.port}"
            self._proxies[key] = proxy_info

    @staticmethod
    def _parse_proxy_string(proxy_str: str) -> Optional[ProxyInfo]:
        """解析代理字符串"""
        try:
            if "://" in proxy_str:
                scheme, rest = proxy_str.split("://", 1)
                host, port_str = rest.rsplit(":", 1)
                port = int(port_str)

                type_map = {
                    "http": ProxyType.HTTP,
                    "https": ProxyType.HTTPS,
                    "socks4": ProxyType.SOCKS4,
                    "socks5": ProxyType.SOCKS5,
                    "socks5h": ProxyType.SOCKS5,
                }
                proxy_type = type_map.get(scheme.lower(), ProxyType.SOCKS5)
                return ProxyInfo(host=host, port=port, proxy_type=proxy_type)
        except (ValueError, IndexError):
            pass
        return None

    @staticmethod
    def parse_proxy_url(proxy_url: str) -> Optional[ProxyInfo]:
        """解析代理 URL 字符串为 ProxyInfo（公开静态方法）"""
        return ProxyPool._parse_proxy_string(proxy_url)

    async def add(self, proxy: Union[str, ProxyInfo], priority: int = 0):
        """添加代理"""
        async with self._lock:
            self._add_proxy(proxy)

    async def get_sorted(self) -> list[ProxyInfo]:
        """获取按健康度排序的代理列表"""
        async with self._lock:
            return sorted(self._proxies.values(), key=lambda p: -p.health_score)

    async def get_proxy_urls(self) -> list[str]:
        """获取代理 URL 列表（向后兼容）"""
        async with self._lock:
            return [p.url for p in self._proxies.values()]

    async def record_success(self, proxy: Union[str, ProxyInfo], response_time: float):
        """记录成功请求"""
        async with self._lock:
            key = self._get_key(proxy)
            if key and key in self._proxies:
                self._proxies[key].record_success(response_time)

    async def record_failure(self, proxy: Union[str, ProxyInfo]):
        """记录失败请求"""
        async with self._lock:
            key = self._get_key(proxy)
            if key and key in self._proxies:
                self._proxies[key].record_failure()

    def _get_key(self, proxy: Union[str, ProxyInfo]) -> Optional[str]:
        """获取代理的键"""
        if isinstance(proxy, ProxyInfo):
            return f"{proxy.host}:{proxy.port}"
        elif isinstance(proxy, str):
            info = self._parse_proxy_string(proxy)
            if info:
                return f"{info.host}:{info.port}"
        return None

    async def increase_priority(self, proxy: str):
        """提升代理优先级（向后兼容）"""
        await self.record_success(proxy, 1.0)

    async def decrease_priority(self, proxy: str):
        """降低代理优先级（向后兼容）"""
        await self.record_failure(proxy)


class ProxyHttpService:
    """支持代理池的 HTTP 服务（异步）"""

    def __init__(
        self,
        http_service: HttpService,
        proxy_pool: Optional[ProxyPool] = None,
        batch_size: int = DEFAULT_PROXY_BATCH_SIZE,
    ):
        self.http_service = http_service
        self.proxy_pool = proxy_pool
        self.batch_size = max(1, batch_size)

    async def fetch_with_proxies(
        self,
        url: str,
        timeout: int = 30,
        headers: Optional[dict[str, str]] = None,
        check_html: Callable[[str], bool] = default_check_html,
    ) -> str:
        """使用代理池按健康度小批次竞速请求

        代理按健康度排序后分批，每批最多 ``batch_size`` 个并发竞速，命中即返回。
        """
        if not self.proxy_pool:
            return await self.http_service.get(
                url, timeout=timeout, headers=headers, check_html=check_html
            )

        proxies = await self.proxy_pool.get_sorted()
        if not proxies:
            raise ProxyError("No proxies available")

        for batch in _chunked(proxies, self.batch_size):
            result = await self._race_batch(url, batch, timeout, headers, check_html)
            if result is not None:
                return result

        raise ProxyError(f"All proxies failed to fetch {url}")

    async def _race_batch(
        self,
        url: str,
        proxies: list[ProxyInfo],
        timeout: int,
        headers: Optional[dict[str, str]],
        check_html: Callable[[str], bool],
    ) -> Optional[str]:
        """并发竞速一批代理，返回首个通过校验的响应；整批失败返回 None。"""
        tasks = {
            asyncio.create_task(
                self._try_fetch(url, proxy, timeout, headers)
            ): proxy
            for proxy in proxies
        }

        done, pending = await asyncio.wait(
            tasks.keys(), return_when=asyncio.FIRST_COMPLETED
        )

        # Cancel remaining tasks
        for task in pending:
            task.cancel()

        # Check completed tasks
        for task in done:
            proxy = tasks[task]
            try:
                result, response_time, _ = task.result()
                if check_html(result):
                    await self.proxy_pool.record_success(proxy, response_time)
                    logging.info(
                        f"Successfully fetched {url} with proxy: {proxy.url}"
                    )
                    return result
                else:
                    await self.proxy_pool.record_failure(proxy)
                    logging.info(f"Proxy {proxy.url} returned invalid content")
            except Exception as e:
                await self.proxy_pool.record_failure(proxy)
                logging.debug(f"Proxy {proxy.url} failed: {e}")

        # Follow up with remaining results from cancelled tasks
        for task in pending:
            proxy = tasks[task]
            try:
                await task
            except (asyncio.CancelledError, Exception):
                await self.proxy_pool.record_failure(proxy)

        return None

    async def _try_fetch(
        self,
        url: str,
        proxy: ProxyInfo,
        timeout: int,
        headers: Optional[dict[str, str]] = None,
    ) -> tuple[str, float, ProxyInfo]:
        """尝试使用指定代理获取（单次，不重试）"""
        start_time = time.time()
        connector = self.http_service._create_proxy_connector(proxy)
        req_kwargs: dict[str, Any] = {
            "timeout": aiohttp.ClientTimeout(total=timeout, sock_connect=timeout),
        }
        if headers:
            req_kwargs["headers"] = headers
        async with aiohttp.ClientSession(connector=connector, **req_kwargs) as session:
            async with session.get(url) as resp:
                resp.raise_for_status()
                text = await resp.text(encoding="utf-8")
        response_time = time.time() - start_time
        if not text.strip():
            raise ValueError("Empty response")
        return text, response_time, proxy

    async def get(
        self,
        url: str,
        timeout: int = 30,
        headers: Optional[dict[str, str]] = None,
        check_html: Callable[[str], bool] = default_check_html,
    ) -> str:
        """获取 URL 内容（兼容 HttpClient 接口）"""
        return await self.fetch_with_proxies(url, timeout, headers, check_html)

    async def get_raw(
        self,
        url: str,
        proxy: Optional[str] = None,
        timeout: int = 30,
        headers: Optional[dict[str, str]] = None,
    ) -> bytes:
        """获取二进制内容（兼容 HttpClient 接口，使用分批竞速）"""
        if not self.proxy_pool:
            return await self.http_service.get_raw(
                url, proxy=proxy, timeout=timeout, headers=headers
            )

        proxies = await self.proxy_pool.get_sorted()
        if not proxies:
            raise ProxyError("No proxies available")

        for batch in _chunked(proxies, self.batch_size):
            result = await self._race_batch_raw(url, batch, timeout, headers)
            if result is not None:
                return result

        raise ProxyError(f"All proxies failed to fetch {url}")

    async def _race_batch_raw(
        self,
        url: str,
        proxies: list[ProxyInfo],
        timeout: int,
        headers: Optional[dict[str, str]],
    ) -> Optional[bytes]:
        """并发竞速一批代理获取二进制内容，返回首个成功结果；整批失败返回 None"""
        tasks = {
            asyncio.create_task(
                self._try_fetch_raw(url, proxy, timeout, headers)
            ): proxy
            for proxy in proxies
        }

        done, pending = await asyncio.wait(
            tasks.keys(), return_when=asyncio.FIRST_COMPLETED
        )

        # Cancel remaining tasks
        for task in pending:
            task.cancel()

        for task in done:
            proxy = tasks[task]
            try:
                result, response_time, _ = task.result()
                await self.proxy_pool.record_success(proxy, response_time)
                logging.info(
                    f"Successfully fetched (raw) {url} with proxy: {proxy.url}"
                )
                return result
            except Exception as e:
                await self.proxy_pool.record_failure(proxy)
                logging.debug(f"Proxy {proxy.url} failed (raw): {e}")

        for task in pending:
            proxy = tasks[task]
            try:
                await task
            except (asyncio.CancelledError, Exception):
                await self.proxy_pool.record_failure(proxy)

        return None

    async def _try_fetch_raw(
        self,
        url: str,
        proxy: ProxyInfo,
        timeout: int,
        headers: Optional[dict[str, str]] = None,
    ) -> tuple[bytes, float, ProxyInfo]:
        """尝试使用指定代理获取二进制内容（单次，不重试）"""
        start_time = time.time()
        connector = self.http_service._create_proxy_connector(proxy)
        req_kwargs: dict[str, Any] = {
            "timeout": aiohttp.ClientTimeout(total=timeout, sock_connect=timeout),
        }
        if headers:
            req_kwargs["headers"] = headers
        async with aiohttp.ClientSession(connector=connector, **req_kwargs) as session:
            async with session.get(url) as resp:
                resp.raise_for_status()
                content = await resp.read()
        response_time = time.time() - start_time
        if not content:
            raise ValueError("Empty response")
        return content, response_time, proxy

    async def post(
        self,
        url: str,
        json: Optional[dict[str, Any]] = None,
        timeout: int = 30,
        headers: Optional[dict[str, str]] = None,
    ) -> str:
        """发送 POST 请求（兼容 HttpClient 接口，使用代理池）"""
        if not self.proxy_pool:
            return await self.http_service.post(
                url, json=json, timeout=timeout, headers=headers
            )

        proxies = await self.proxy_pool.get_sorted()
        if not proxies:
            raise ProxyError("No proxies available")

        for proxy_info in proxies:
            try:
                connector = self.http_service._create_proxy_connector(proxy_info)
                req_kwargs: dict[str, Any] = {
                    "timeout": aiohttp.ClientTimeout(total=timeout, sock_connect=timeout),
                }
                if headers:
                    req_kwargs["headers"] = headers
                if json is not None:
                    req_kwargs["json"] = json
                async with aiohttp.ClientSession(
                    connector=connector, **req_kwargs
                ) as session:
                    async with session.post(url) as resp:
                        resp.raise_for_status()
                        text = await resp.text(encoding="utf-8")
                await self.proxy_pool.record_success(proxy_info, 1.0)
                return text
            except Exception:
                await self.proxy_pool.record_failure(proxy_info)

        raise ProxyError(f"All proxies failed to POST {url}")
