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
            '(//div[contains(@class,"title-article")])[1]//a/@href'
        )
        if not links:
            raise ValueError("No links found on homepage.")
        return links[0]

    def parse_urls(self, today_page: str) -> list[tuple[str, str]]:
        page_etree = etree.HTML(today_page)
        rules = {
            "clash.yaml": '//*[@id="md_content_2"]/div/div[5]/div[4]/p/a/@href',
            "v2ray.txt": '//*[@id="md_content_2"]/div/div[5]/div[2]/p/a/@href',
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
