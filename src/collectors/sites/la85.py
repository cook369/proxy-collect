"""85la 采集器"""

from lxml import etree
from typing import Optional

from collectors.base import BaseCollector, register_collector
from collectors.mixins import TwoStepCollectorMixin


@register_collector
class La85Collector(TwoStepCollectorMixin, BaseCollector):
    """85la 站点采集器"""

    name = "85la"
    home_page = "https://www.85la.com"

    def get_today_url(self, home_html: str) -> Optional[str]:
        """从首页获取今日链接"""
        tree = etree.HTML(home_html)
        links = tree.xpath(
            '//a[text()[contains(., "免费节点")] and text()[contains(., "高速节点")]]/@href'
        )
        if not links:
            raise ValueError("No links found on homepage.")
        return links[0]

    def parse_download_urls(self, today_html: str) -> list[tuple[str, str]]:
        """从今日页面解析下载链接"""
        tree = etree.HTML(today_html)
        rules = {
            "v2ray.txt": '(//h3[contains(., "V2ray 订阅地址")]/following-sibling::a)/@href',
            "clash.yaml": '(//h3[contains(., "Clash.meta 订阅地址")]/following-sibling::a)/@href',
        }

        urls: list[tuple[str, str]] = []
        for filename, xpath_expr in rules.items():
            hrefs = tree.xpath(xpath_expr)
            if hrefs:
                urls.append((filename, hrefs[0]))

        return urls
