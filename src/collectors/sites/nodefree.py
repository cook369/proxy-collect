"""NodeFree 采集器"""
from typing import Optional
from lxml import etree
from collectors.base import BaseCollector, register_collector
from collectors.mixins import TwoStepCollectorMixin


@register_collector
class NodefreeCollector(TwoStepCollectorMixin, BaseCollector):
    """NodeFree 站点采集器"""

    name = "nodefree"
    home_page = "https://nodefree.me"
    
    def get_today_url(self, home_html: str) -> Optional[str]:
        """从首页获取今日链接"""
        tree = etree.HTML(home_html)
        links = tree.xpath(
            '//a[text()[contains(., "订阅链接免费节点")]]/@href'
        )
        if not links:
            raise ValueError("No links found on homepage.")
        return links[0]

    def parse_download_urls(self, today_html: str) -> list[tuple[str, str]]:
        """从今日页面解析下载链接"""
        tree = etree.HTML(today_html)
        rules = {
            "v2ray.txt": 'string(//h2[contains(., "v2ray订阅链接")]/following-sibling::p[1])',
            "clash.yaml": 'string(//h2[contains(., "clash订阅链接")]/following-sibling::p[1])',
        }

        urls: list[tuple[str, str]] = []
        for filename, xpath_expr in rules.items():
            hrefs = tree.xpath(xpath_expr)
            if hrefs:
                urls.append((filename, hrefs))

        return urls
