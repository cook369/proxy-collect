import logging

from collectors.base import BaseCollector, register_collector
from collectors.mixins import HtmlParser
from config.settings import default_config
from core.exceptions import ProxyError
from core.models import DownloadTask
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
        """用单个口令请求 jcnode 验证接口。

        通过 self.http_client.post() 发送请求，代理池自动管理代理选择与重试。
        当所有代理失败时，重试 verify_network_retry_rounds 轮（每轮代理池会重新排序）。
        """
        last_error: Exception | None = None
        failed_rounds = 0

        logging.debug(f"[{self.name}] trying password candidate")

        while failed_rounds < self.verify_network_retry_rounds:
            try:
                response = self.http_client.post(
                    self.verify_url,
                    json={"code": password},
                    timeout=default_config.collector.fetch_timeout,
                    headers=self.verify_headers,
                )
            except ProxyError as e:
                last_error = e
                failed_rounds += 1
                if failed_rounds < self.verify_network_retry_rounds:
                    logging.info(
                        f"[{self.name}] all proxies failed, retrying same password"
                    )
                continue
            except Exception as e:
                last_error = e
                failed_rounds += 1
                if failed_rounds < self.verify_network_retry_rounds:
                    logging.info(
                        f"[{self.name}] request failed, retrying same password: {e}"
                    )
                continue

            if "口令错误" in response:
                logging.debug(f"[{self.name}] password candidate rejected")
                raise ValueError("password error")
            if not response.strip():
                failed_rounds += 1
                logging.debug(
                    f"[{self.name}] empty verification response, retrying"
                )
                continue
            return response

        if last_error:
            raise FatalPasswordAttemptError(
                "jcnode verification network failed"
            ) from last_error
        raise FatalPasswordAttemptError("no proxy available for jcnode verification")
