"""Jichangx 采集器"""

from datetime import datetime

from collectors.base import BaseCollector, register_collector


@register_collector
class JichangxCollector(BaseCollector):
    """Jichangx 站点采集器"""

    name = "jichangx"
    home_page = "https://jichangx.com"

    def get_download_urls(self) -> list[tuple[str, str]]:
        """构建下载 URL"""
        date_str = datetime.now().strftime("%Y%m%d")
        return [("v2ray.txt", f"{self.home_page}/nodes/v2ray-{date_str}-01")]
