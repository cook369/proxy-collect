"""HTTP 请求服务

提供基础 HTTP 请求和支持代理池的 HTTP 请求服务。
"""
import logging
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import RLock
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class HttpService:
    """基础 HTTP 请求服务"""

    def __init__(self, session: Optional[requests.Session] = None):
        self.session = session or self._create_session()

    def _create_session(self) -> requests.Session:
        """创建 HTTP 会话"""
        session = requests.Session()
        session.verify = False
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        })
        return session

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

    def __init__(self, proxies: Optional[list[str]] = None):
        self.lock = RLock()
        self.priority: dict[str, int] = {}

        if proxies:
            for proxy in proxies:
                self.priority[proxy] = 0

    def add(self, proxy: str, priority: int = 0):
        """添加代理"""
        with self.lock:
            self.priority[proxy] = priority

    def get_sorted(self) -> list[str]:
        """获取按优先级排序的代理列表"""
        with self.lock:
            return sorted(self.priority.keys(), key=lambda p: -self.priority[p])

    def increase_priority(self, proxy: str):
        """提升代理优先级"""
        with self.lock:
            if proxy in self.priority:
                self.priority[proxy] += 1

    def decrease_priority(self, proxy: str):
        """降低代理优先级"""
        with self.lock:
            if proxy in self.priority:
                self.priority[proxy] -= 1


class ProxyHttpService:
    """支持代理池的 HTTP 服务"""

    def __init__(
        self,
        http_service: HttpService,
        proxy_pool: Optional[ProxyPool] = None,
        max_workers: int = 10
    ):
        self.http_service = http_service
        self.proxy_pool = proxy_pool
        self.executor = ThreadPoolExecutor(max_workers=max_workers)

    def fetch_with_proxies(self, url: str, timeout: int = 30) -> str:
        """使用代理池并发请求

        Args:
            url: 请求 URL
            timeout: 超时时间（秒）

        Returns:
            响应内容

        Raises:
            RuntimeError: 所有代理都失败
        """
        if not self.proxy_pool:
            # 无代理池，直接请求
            return self.http_service.get(url, timeout=timeout)

        proxies = self.proxy_pool.get_sorted()
        if not proxies:
            raise RuntimeError("No proxies available")

        # 并发尝试所有代理
        futures = {
            self.executor.submit(self._try_fetch, url, proxy, timeout): proxy
            for proxy in proxies
        }

        for future in as_completed(futures):
            proxy = futures[future]
            try:
                result = future.result()

                # 成功，提升优先级
                self.proxy_pool.increase_priority(proxy)

                # 取消其他任务
                for f in futures:
                    if f != future:
                        f.cancel()

                extralog = f"proxy: {proxy}" if proxy else "direct"
                logging.info(f"Successfully fetched {url} with {extralog}")
                return result

            except Exception as e:
                # 失败，降低优先级
                self.proxy_pool.decrease_priority(proxy)
                logging.debug(f"Proxy {proxy} failed: {e}")

        raise RuntimeError(f"All proxies failed to fetch {url}")

    def _try_fetch(self, url: str, proxy: str, timeout: int) -> str:
        """尝试使用指定代理获取"""
        return self.http_service.get(url, proxy=proxy, timeout=timeout)

    def shutdown(self):
        """关闭线程池"""
        self.executor.shutdown(wait=True)
