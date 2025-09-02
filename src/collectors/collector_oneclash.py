from datetime import datetime
from lxml import etree
from .base import BaseCollector, register_collector


@register_collector
class CollectorOneclash(BaseCollector):
    name = "oneclash"
    home_page = "https://oneclash.cc"

    def get_download_urls(self) -> list[tuple[str, str]]:
        url_suffix = f"{datetime.now().strftime('%Y/%m/%Y%m%d')}"
        urls = [
            (
                "clash.yaml",
                f"https://oneclash.githubrowcontent.com/{url_suffix}.yaml",
            ),
            (
                "v2ray.txt",
                f"https://oneclash.githubrowcontent.com/{url_suffix}.txt",
            ),
        ]
        return urls
