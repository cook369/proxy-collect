"""小青科学网采集器"""

from collectors.base import YouTubePasteToCollector, register_collector
from core.models import DownloadTask
from utils.extractors import create_download_tasks_from_regex_rules


@register_collector
class XQKXWCollector(YouTubePasteToCollector):
    """小青科学网站点采集器"""

    name = "xqkxw"
    home_page = (
        "https://www.youtube.com/playlist?list=PLuUYvtnZVIVI79GPS7VvxhYYm0x2jjuOZ"
    )
    playlist_keywords = ("节点分享", "免费节点")

    def parse_subscription_tasks(self, content: str) -> list[DownloadTask]:
        """从解密后的分享内容提取订阅链接"""
        patterns = {
            "v2ray.txt": r"V2ray.*?(https?://[^\s<>'\"，）)]+?\.txt)",
            "clash.yaml": r"clash.*?(https?://[^\s<>'\"，）)]+?\.yaml)",
        }
        return create_download_tasks_from_regex_rules(content, patterns)
