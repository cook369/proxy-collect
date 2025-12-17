import logging
from lxml import etree
from .base import BaseCollector, register_collector


@register_collector
class Collector85la(BaseCollector):
    """85la 采集器"""

    name = "85la"
    home_page = "https://www.85la.com"

    def get_today_url(self, home_page: str) -> str:
        home_etree = etree.HTML(home_page)
        links = home_etree.xpath(
            '//a[text()[contains(., "免费节点")] and text()[contains(., "高速节点")]]/@href'
        )
        if not links:
            raise ValueError("No links found on homepage.")
        return links[0]

    def parse_urls(self, today_page: str) -> list[tuple[str, str]]:
        page_etree = etree.HTML(today_page)
        rules = {
            "v2ray.txt": '(//h3[contains(., "V2ray 订阅地址")]/following-sibling::a)/@href',
            "clash.yaml": '(//h3[contains(., "Clash.meta 订阅地址")]/following-sibling::a)/@href',
        }
        urls: list[tuple[str, str]] = []
        for filename, xpath_expr in rules.items():
            hrefs: list[str] = page_etree.xpath(xpath_expr)
            if hrefs:
                urls.append((filename, hrefs[0]))
        return urls

    def get_download_urls(self) -> list[tuple[str, str]]:
        home_page = self.fetch_html(self.home_page)
        today_url = self.get_today_url(home_page)
        if not today_url:
            return []
        logging.info(f"Today's URL: {today_url}")
        today_page = self.fetch_html(today_url)
        return self.parse_urls(today_page)
