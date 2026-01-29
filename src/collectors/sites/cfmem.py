"""CFMem 采集器"""

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
        links = tree.xpath(
            '//a[text()[contains(., "免费节点更新")]]/@href'
        )
        if not links:
            raise ValueError("No links found on homepage.")
        return links[1]

    def parse_download_urls(self, today_html: str) -> list[tuple[str, str]]:
        """从今日页面解析下载链接"""
        tree = etree.HTML(today_html)
        rules = {
            "v2ray.txt": 'string(//div[text()[contains(., "V2Ray / XRay")]]/following-sibling::div[1])',
            "clash.yaml": 'string(//div[text()[contains(., "Clash/Mihomo")]]/following-sibling::div[1])',
        }

        urls: list[tuple[str, str]] = []
        for filename, xpath_expr in rules.items():
            hrefs = tree.xpath(xpath_expr)
            if hrefs:
                urls.append((filename, hrefs))

        return urls
