from .base import BaseCollector, register_collector
from datetime import datetime


@register_collector
class CollectorDatiya(BaseCollector):
    name = "datiya"
    home_page = "https://free.datiya.com"

    def get_today_url(self, home_page: str) -> str:
        return f"{self.home_page}/post/{datetime.now().strftime('%Y%m%d')}/"

    def get_dynamic_urls(self) -> list[tuple[str, str]]:
        url_suffix = f"{datetime.now().strftime('%Y%m%d')}"
        urls = [
            (
                "clash.yaml",
                f"{self.home_page}/uploads/{url_suffix}-clash.yaml",
            ),
            (
                "v2ray.txt",
                f"{self.home_page}/uploads/{url_suffix}-v2ray.txt",
            ),
        ]
        return urls
