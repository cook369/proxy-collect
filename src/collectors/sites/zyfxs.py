"""资源分享师站点采集器"""

from collectors.base import YouTubePasteToCollector, register_collector
from core.models import DownloadTask
from utils.extractors import create_download_tasks_from_regex_rules


@register_collector
class ZYFXSCollector(YouTubePasteToCollector):
    """资源分享师站点采集器"""

    name = "zyfxs"
    home_page = (
        "https://www.youtube.com/playlist?list=PLFF7T03a7nnF-5POF9QxmABrzSKGy8fhC"
    )
    playlist_keywords = ("节点分享", "免费节点")

    def parse_subscription_tasks(self, content: str) -> list[DownloadTask]:
        """从解密后的分享内容提取订阅链接"""
        patterns = {
            "v2ray.txt": r"v2ray.*?(https?://[^\s<>'\"，）)]+)(?:\\n|\n|$)",
            "clash.yaml": r"clash.*?(https?://[^\s<>'\"，）)]+)(?:\\n|\n|$)",
        }
        return create_download_tasks_from_regex_rules(content, patterns)
