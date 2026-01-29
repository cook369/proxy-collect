"""NodeFree 采集器"""
from collectors.base import BaseCollector, register_collector
from collectors.mixins import DateBasedUrlMixin


@register_collector
class NodefreeCollector(DateBasedUrlMixin, BaseCollector):
    """NodeFree 站点采集器"""

    name = "nodefree"
    home_page = "https://nodefree.me"

    def get_download_urls(self) -> list[tuple[str, str]]:
        """构建基于日期的下载 URL"""
        return self.build_date_urls(
            "https://nodefree.githubrowcontent.com",
            "%Y/%m/%Y%m%d",
            {
                "clash.yaml": ".yaml",
                "v2ray.txt": ".txt"
            }
        )
