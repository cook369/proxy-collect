"""xiaozhou168站点采集器"""

import logging

import requests

from collectors.base import BaseCollector, register_collector
from collectors.mixins import HtmlParser, TwoStepCollectorMixin
from config.settings import default_config
from core.models import DownloadTask
from services.paste_to_service import PasteToService
from utils.extractors import create_download_tasks_from_regex_rules
from utils.passwords import (
    CharsetPasswordStrategy,
    DictionaryPasswordStrategy,
)

logger = logging.getLogger(__name__)



@register_collector
class XZ168(TwoStepCollectorMixin, BaseCollector):
    """xiaozhou168站点采集器"""

    name = "xz168"
    home_page = (
        "https://www.xiaozhou168.top/"
    )
    paste_to_password: str | None = "1668"
    paste_to_password_strategy: (
        CharsetPasswordStrategy | DictionaryPasswordStrategy | None
    ) = None
    
    # ── TwoStep 采集流程 ──
    
    def get_today_url(self, home_html: str) -> str | None:
        """从首页获取今日链接"""
        parser = HtmlParser(home_html, self.name)
        return parser.xpath('//a[text()[contains(., "免费精选节点")]]/@href')

    def parse_download_tasks(self, today_html: str) -> list[DownloadTask]:
        """从今日页面解析下载任务"""
        parser = HtmlParser(today_html, self.name)
        tmp_url = parser.xpath('string(//*[starts-with(@id, "post-")]/div[2]/p[5]/a)')
        if not tmp_url:
            raise ValueError("invalid today url")
        
        response = requests.head(
            tmp_url,
            allow_redirects=True,
            timeout=10
        )
        target_url = response.url
        
        paste_to_service = PasteToService(
            http_client=self.http_client,
            timeout=default_config.collector.fetch_timeout,
            max_workers=default_config.collector.paste_to_password_workers,
            password_strategy=self.paste_to_password_strategy,
        )
        decrypt_result = paste_to_service.decrypt_url(
            target_url,
            password=self.paste_to_password,
        )
        content = decrypt_result.content
        if not self.paste_to_password:
            logger.info(
                f"[{self.name}] password decrypt {target_url} "
                f"with {decrypt_result.password} share"
            )
        patterns = {
            "v2ray.txt": r"1、V2ray.*?(https?://[^\\\s]+)",
            "clash.yaml": r"2、clash.*?(https?://[^\\\s]+)",
        }
        return create_download_tasks_from_regex_rules(content, patterns)
        
