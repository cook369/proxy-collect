from datetime import datetime
from lxml import etree
from .base import BaseCollector, register_collector


@register_collector
class CollectorNodefree(BaseCollector):
    name = "nodefree"
    home_page = "https://nodefree.me"

    def get_download_urls(self) -> list[tuple[str, str]]:
        url_suffix = f"{datetime.now().strftime('%Y/%m/%Y%m%d')}"
        urls = [
            (
                "clash.yaml",
                f"https://nodefree.githubrowcontent.com/{url_suffix}.yaml",
            ),
            (
                "v2ray.txt",
                f"https://nodefree.githubrowcontent.com/{url_suffix}.txt",
            ),
        ]
        return urls
