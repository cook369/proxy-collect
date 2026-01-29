"""Datia 采集器"""
from typing import Optional
from lxml import etree
from collectors.base import BaseCollector, register_collector
from collectors.mixins import TwoStepCollectorMixin


@register_collector
class DatiaCollector(TwoStepCollectorMixin, BaseCollector):
    """Datia 站点采集器"""

    name = "datiya"
    home_page = "https://free.datiya.com"

    def get_today_url(self, home_html: str) -> Optional[str]:
        """从首页获取今日链接"""
        tree = etree.HTML(home_html)
        links = tree.xpath(
            '//a[text()[contains(., "高速免费节点")]]/@href'
        )
        if not links:
            raise ValueError("No links found on homepage.")
        return self.home_page + links[0]

    def parse_download_urls(self, today_html: str) -> list[tuple[str, str]]:
        """从今日页面解析下载链接"""
        tree = etree.HTML(today_html)
        rules = {
            "v2ray.txt": 'string(//ol[contains(., "V2ray配置")]/following-sibling::pre[1])',
            "clash.yaml": 'string(//ol[contains(., "Clash配置")]/following-sibling::pre[1])',
        }

        urls: list[tuple[str, str]] = []
        for filename, xpath_expr in rules.items():
            hrefs = tree.xpath(xpath_expr)
            if hrefs:
                urls.append((filename, hrefs))

        return urls
