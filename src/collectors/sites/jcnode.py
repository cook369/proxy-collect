import logging

import random
from threading import Lock

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
    FatalPasswordAttemptError,
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
    verify_network_retry_rounds = 3
    verify_headers = {
        "content-type": "application/json",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._failed_proxy_lock = Lock()
        self._failed_proxy_urls: set[str] = set()

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
        logging.info(
            f"[{self.name}] password decrypt {self.home_page} with {verification_result.password} share"
        )
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
        failed_rounds = 0

        logging.debug(f"[{self.name}] trying password candidate")

        while failed_rounds < self.verify_network_retry_rounds:
            candidates = self._proxy_candidates()
            if not candidates:
                failed_rounds += 1
                self._reset_failed_proxies()
                logging.info(
                    f"[{self.name}] all proxies failed, retrying same password"
                )
                continue

            for proxy in candidates:
                if self._is_proxy_failed(proxy):
                    continue

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
                    self._mark_proxy_failed(proxy)
                    logging.debug(
                        f"[{self.name}] proxy request failed, trying next proxy: {e}"
                    )
                    continue

                if "口令错误" in response.text:
                    logging.debug(f"[{self.name}] password candidate rejected")
                    raise ValueError("password error")
                if not response.text.strip():
                    self._mark_proxy_failed(proxy)
                    logging.debug(
                        f"[{self.name}] empty verification response, trying next proxy"
                    )
                    continue
                return response.text

            failed_rounds += 1
            if failed_rounds < self.verify_network_retry_rounds:
                logging.info(
                    f"[{self.name}] all proxies failed, retrying same password"
                )
                self._reset_failed_proxies()

        if last_error:
            raise FatalPasswordAttemptError(
                "jcnode verification network failed"
            ) from last_error
        raise FatalPasswordAttemptError("no proxy available for jcnode verification")

    def _proxy_candidates(self) -> list[ProxyInfo | None]:
        if not self.proxy_pool:
            return [None]

        proxies = self.proxy_pool.get_sorted()
        if not proxies:
            return [None]

        with self._failed_proxy_lock:
            failed_proxy_urls = set(self._failed_proxy_urls)

        candidates = [proxy for proxy in proxies if proxy.url not in failed_proxy_urls]
        if not candidates:
            return []

        random.shuffle(candidates)
        return candidates

    def _mark_proxy_failed(self, proxy: ProxyInfo | None) -> None:
        if proxy is None:
            return

        with self._failed_proxy_lock:
            self._failed_proxy_urls.add(proxy.url)

    def _is_proxy_failed(self, proxy: ProxyInfo | None) -> bool:
        if proxy is None:
            return False

        with self._failed_proxy_lock:
            return proxy.url in self._failed_proxy_urls

    def _reset_failed_proxies(self) -> None:
        with self._failed_proxy_lock:
            self._failed_proxy_urls.clear()
