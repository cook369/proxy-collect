"""Jichangx 采集器"""

from datetime import datetime

from collectors.base import BaseCollector, register_collector
from core.models import DownloadTask


@register_collector
class JichangxCollector(BaseCollector):
    """Jichangx 站点采集器"""

    name = "jichangx"
    home_page = "https://jichangx.com"

    def get_download_tasks(self) -> list[DownloadTask]:
        """构建下载任务"""
        date_str = datetime.now().strftime("%Y%m%d")
        return [
            DownloadTask(
                filename="v2ray.txt",
                url=f"{self.home_page}/nodes/v2ray-{date_str}-01",
            )
        ]
