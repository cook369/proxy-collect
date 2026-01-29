"""CFMem 采集器"""
import re
from lxml import etree
from typing import Optional

from collectors.base import BaseCollector, register_collector
from collectors.mixins import TwoStepCollectorMixin


@register_collector
class CfmemCollector(TwoStepCollectorMixin, BaseCollector):
    """CFMem 站点采集器"""

    name = "cfmeme"
    home_page = "https://www.cfmem.com"

    def get_today_url(self, home_html: str) -> Optional[str]:
        """从首页获取今日链接"""
        tree = etree.HTML(home_html)
        links = tree.xpath('//*[@id="Blog1"]/div[1]/article[1]/div[1]/h2/a/@href')
        if not links:
            raise ValueError("No links found on homepage.")
        return links[0]

    def parse_download_urls(self, today_html: str) -> list[tuple[str, str]]:
        """从今日页面解析下载链接"""
        tree = etree.HTML(today_html)
        rules = {
            "clash.yaml": [
                '//*[@id="post-body"]/div/div[4]/div[2]/span/text()',
                r"https?://[^\s'\"<>]+?\.(?:yaml)",
            ],
            "v2ray.txt": [
                '//*[@id="post-body"]/div/div[4]/div[1]/span/text()',
                r"https?://[^\s'\"<>]+?\.(?:txt)",
            ],
        }

        urls: list[tuple[str, str]] = []
        for filename, (xpath_expr, regex_expr) in rules.items():
            hrefs = tree.xpath(xpath_expr)
            if hrefs:
                matches = re.findall(regex_expr, hrefs[0])
                if matches:
                    urls.append((filename, str(matches[0])))

        return urls
