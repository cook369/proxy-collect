import logging

import random
from threading import Lock
import time
from typing import Optional, Union

import requests

from collectors.base import BaseCollector, register_collector
from collectors.mixins import HtmlParser
from config.settings import default_config
from core.models import DownloadTask, ProxyInfo
from utils.check import check_html_contains
from utils.extractors import create_download_tasks_from_regex_rules
from utils.passwords import (
    CharsetPasswordStrategy,
    DictionaryPasswordStrategy,
    PasswordAttemptResult,
    brute_force_password,
)


@register_collector
class JCNodeCollector(BaseCollector):
    """jcnode采集器"""

    name = "jcnode"
    home_page = "https://jcnode.com/posts/free-nodes/"
    verify_url = "https://jcnode.com/api/verify"
    verification_code: str | None = None
    verification_code_strategy: (
        CharsetPasswordStrategy | DictionaryPasswordStrategy | None
    ) = None
    proxy_reuse_interval = 0
    verify_headers = {
        "content-type": "application/json",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    }

    def __init__(
        self,
        proxies_list: Optional[Union[list[str], list[ProxyInfo]]] = None,
        http_client=None,
    ):
        super().__init__(proxies_list=proxies_list, http_client=http_client)
        self._proxy_lock = Lock()
        self._proxy_last_used_at: dict[str, float] = {}

    def get_download_tasks(self) -> list[DownloadTask]:
        """从 jcnode 页面口令接口获取订阅任务"""
        check_playlist = check_html_contains("免费节点")
        if not self.today_page:
            playlist_html = self.fetch_html(self.home_page, check_html=check_playlist)
            self.today_page = self.get_today_url(playlist_html)
        self.skip_if_cached()

        logging.info(f"[{self.name}] preparing password verification")

        if self.verification_code:
            verification_result = PasswordAttemptResult(
                password=self.verification_code,
                content=self.verify_code(self.verification_code),
            )
        else:
            verification_result = brute_force_password(
                max_workers=default_config.collector.http_password_workers,
                password_strategy=self.verification_code_strategy,
                try_password=self.verify_code,
            )

        logging.info(f"[{self.name}] password verification succeeded")
        return self.parse_subscription_tasks(verification_result.content)

    def get_today_url(self, home_html: str) -> str:
        parser = HtmlParser(home_html, self.name)
        data = parser.xpath('//*[@id="top"]/main/article/div/p[5]/a/@href')
        if not data:
            raise ValueError("invalid today url")
        return data

    def parse_subscription_tasks(self, content: str) -> list[DownloadTask]:
        """从验证接口响应内容提取订阅链接"""
        patterns = {
            "v2ray.txt": r'"v2ray":"(https?://.*?)"',
            "clash.yaml": r'"clash":"(https?://.*?)"',
        }
        return create_download_tasks_from_regex_rules(content, patterns)

    def verify_code(self, password: str) -> str:
        """用单个口令请求 jcnode 验证接口。"""
        last_error: requests.RequestException | None = None

        logging.debug(f"[{self.name}] trying password candidate")

        for proxy in self._proxy_candidates():
            self._wait_for_proxy_slot(proxy)
            proxies = {"http": proxy.url, "https": proxy.url} if proxy else None

            try:
                response = requests.post(
                    self.verify_url,
                    proxies=proxies,
                    headers=self.verify_headers,
                    json={"code": password},
                    timeout=default_config.collector.fetch_timeout,
                )
                response.raise_for_status()
            except requests.RequestException as e:
                last_error = e
                logging.info(f"[{self.name}] proxy request failed, trying next proxy")
                continue

            if "口令错误" in response.text:
                logging.debug(f"[{self.name}] password candidate rejected")
                raise ValueError("password error")
            if not response.text.strip():
                raise ValueError("empty verification response")
            return response.text

        if last_error:
            raise last_error
        raise ValueError("no proxy available")

    def _proxy_candidates(self) -> list[ProxyInfo | None]:
        if not self.proxy_pool:
            return [None]

        proxies = self.proxy_pool.get_sorted()
        if not proxies:
            return [None]

        random.shuffle(proxies)
        return proxies

    def _wait_for_proxy_slot(self, proxy: ProxyInfo | None) -> None:
        if proxy is None:
            return

        wait_seconds = self._reserve_proxy_slot(proxy)
        if wait_seconds > 0:
            time.sleep(wait_seconds)

    def _reserve_proxy_slot(self, proxy: ProxyInfo) -> float:
        proxy_key = proxy.url
        with self._proxy_lock:
            now = time.monotonic()
            next_available = (
                self._proxy_last_used_at.get(proxy_key, 0) + self.proxy_reuse_interval
            )
            wait_seconds = max(0.0, next_available - now)
            self._proxy_last_used_at[proxy_key] = now + wait_seconds
            return wait_seconds
