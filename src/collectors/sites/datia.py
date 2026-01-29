"""Datia 采集器"""
from collectors.base import BaseCollector, register_collector
from collectors.mixins import DateBasedUrlMixin


@register_collector
class DatiaCollector(DateBasedUrlMixin, BaseCollector):
    """Datia 站点采集器"""

    name = "datiya"
    home_page = "https://free.datiya.com"

    def get_download_urls(self) -> list[tuple[str, str]]:
        """构建基于日期的下载 URL"""
        return self.build_date_urls(
            f"{self.home_page}/uploads",
            "%Y%m%d",
            {
                "clash.yaml": "-clash.yaml",
                "v2ray.txt": "-v2ray.txt"
            }
        )
