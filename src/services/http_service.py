"""HTTP 请求服务

提供基础 HTTP 请求和支持代理池的 HTTP 请求服务。
"""

import logging
import time
from typing import Optional, Union
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import RLock
import requests
import urllib3
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from core.exceptions import ProxyError
from core.models import ProxyInfo, ProxyType


class HttpService:
    """基础 HTTP 请求服务"""

    def __init__(
        self, session: Optional[requests.Session] = None, verify_ssl: bool = False
    ):
        """初始化 HTTP 服务

        Args:
            session: 可选的 requests.Session 实例
            verify_ssl: 是否验证 SSL 证书（默认 False，因为代理站点证书可能有问题）
        """
        self.verify_ssl = verify_ssl
        self.session = session or self._create_session()

        # 只在禁用 SSL 验证时才禁用警告
        if not verify_ssl:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    def _create_session(self) -> requests.Session:
        """创建 HTTP 会话"""
        session = requests.Session()
        session.verify = self.verify_ssl
        session.headers.update(
            {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        )
        return session

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((requests.RequestException, ValueError)),
        reraise=True,
    )
    def get(self, url: str, proxy: Optional[str] = None, timeout: int = 30) -> str:
        """发送 GET 请求

        Args:
            url: 请求 URL
            proxy: 代理地址（可选）
            timeout: 超时时间（秒）

        Returns:
            响应内容

        Raises:
            requests.HTTPError: HTTP 错误
            ValueError: 响应内容为空
        """
        proxies = {"http": proxy, "https": proxy} if proxy else None
        resp = self.session.get(url, proxies=proxies, timeout=timeout)
        resp.raise_for_status()

        if not resp.text.strip():
            raise ValueError("Empty response")

        return resp.text


class ProxyPool:
    """代理池管理"""

    def __init__(self, proxies: Optional[Union[list[str], list[ProxyInfo]]] = None):
        self.lock = RLock()
        self._proxies: dict[str, ProxyInfo] = {}

        if proxies:
            for proxy in proxies:
                self._add_proxy(proxy)

    def _add_proxy(self, proxy: Union[str, ProxyInfo]) -> None:
        """内部添加代理"""
        if isinstance(proxy, str):
            proxy_info = self._parse_proxy_string(proxy)
        else:
            proxy_info = proxy

        if proxy_info:
            key = f"{proxy_info.host}:{proxy_info.port}"
            self._proxies[key] = proxy_info

    def _parse_proxy_string(self, proxy_str: str) -> Optional[ProxyInfo]:
        """解析代理字符串"""
        try:
            # 格式: scheme://host:port
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

    def add(self, proxy: Union[str, ProxyInfo], priority: int = 0):
        """添加代理"""
        with self.lock:
            self._add_proxy(proxy)

    def get_sorted(self) -> list[ProxyInfo]:
        """获取按健康度排序的代理列表"""
        with self.lock:
            return sorted(self._proxies.values(), key=lambda p: -p.health_score)

    def get_proxy_urls(self) -> list[str]:
        """获取代理 URL 列表（向后兼容）"""
        with self.lock:
            return [p.url for p in self._proxies.values()]

    def record_success(self, proxy: Union[str, ProxyInfo], response_time: float):
        """记录成功请求"""
        with self.lock:
            key = self._get_key(proxy)
            if key and key in self._proxies:
                self._proxies[key].record_success(response_time)

    def record_failure(self, proxy: Union[str, ProxyInfo]):
        """记录失败请求"""
        with self.lock:
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

    def increase_priority(self, proxy: str):
        """提升代理优先级（向后兼容）"""
        self.record_success(proxy, 1.0)

    def decrease_priority(self, proxy: str):
        """降低代理优先级（向后兼容）"""
        self.record_failure(proxy)


class ProxyHttpService:
    """支持代理池的 HTTP 服务"""

    def __init__(
        self,
        http_service: HttpService,
        proxy_pool: Optional[ProxyPool] = None,
        max_workers: int = 10,
    ):
        self.http_service = http_service
        self.proxy_pool = proxy_pool
        self.executor = ThreadPoolExecutor(max_workers=max_workers)

    def fetch_with_proxies(self, url: str, timeout: int = 30) -> str:
        """使用代理池并发请求"""
        if not self.proxy_pool:
            return self.http_service.get(url, timeout=timeout)

        proxies = self.proxy_pool.get_sorted()
        if not proxies:
            raise ProxyError("No proxies available")

        futures = {
            self.executor.submit(self._try_fetch, url, proxy, timeout): proxy
            for proxy in proxies
        }

        for future in as_completed(futures):
            proxy = futures[future]
            try:
                result, response_time = future.result()
                self.proxy_pool.record_success(proxy, response_time)

                for f in futures:
                    if f != future:
                        f.cancel()

                logging.info(f"Successfully fetched {url} with proxy: {proxy.url}")
                return result

            except Exception as e:
                self.proxy_pool.record_failure(proxy)
                logging.debug(f"Proxy {proxy.url} failed: {e}")

        raise ProxyError(f"All proxies failed to fetch {url}")

    def _try_fetch(self, url: str, proxy: ProxyInfo, timeout: int) -> tuple[str, float]:
        """尝试使用指定代理获取"""
        start_time = time.time()
        result = self.http_service.get(url, proxy=proxy.url, timeout=timeout)
        response_time = time.time() - start_time
        return result, response_time

    def get(self, url: str, timeout: int = 30) -> str:
        """获取 URL 内容（兼容 HttpService 接口）"""
        return self.fetch_with_proxies(url, timeout)

    def shutdown(self):
        """关闭线程池"""
        self.executor.shutdown(wait=True)
