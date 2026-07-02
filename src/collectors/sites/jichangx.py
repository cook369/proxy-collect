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
        now = datetime.now()
        date_str = now.strftime("%Y%m%d")
        page_date = now.strftime("%Y-%m-%d")
        self.today_page = f"{self.home_page}/free-nodes-{page_date}/"
        self.title = now.strftime("%Y年%m月%d日")
        return [
            DownloadTask(
                filename="v2ray.txt",
                url=f"{self.home_page}/nodes/v2ray-{date_str}-01",
            )
        ]
