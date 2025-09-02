from datetime import datetime
from lxml import etree
from .base import BaseCollector, register_collector


@register_collector
class CollectorJichangx(BaseCollector):
    name = "jichangx"
    home_page = "https://jichangx.com"

    def get_download_urls(self) -> list[tuple[str, str]]:
        urls = [
            (
                "v2ray.txt",
                f"{self.home_page}/nodes/v2ray-{datetime.now().strftime('%Y%m%d')}-01",
            ),
        ]
        return urls
