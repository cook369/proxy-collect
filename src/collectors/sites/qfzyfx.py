"""青枫资源分享站点采集器"""

from collectors.base import YouTubePasteToCollector, register_collector
from core.models import DownloadTask
from utils.extractors import create_download_tasks_from_regex_rules


@register_collector
class QFZYFXCollector(YouTubePasteToCollector):
    """青枫资源分享站点采集器"""

    name = "qfzyfx"
    home_page = (
        "https://www.youtube.com/playlist?list=PLCnXKcEd8EBSTi6opWScaC54pqPsPxKjA"
    )
    playlist_keywords = ("免费节点",)

    def parse_subscription_tasks(self, content: str) -> list[DownloadTask]:
        """从解密后的分享内容提取订阅链接"""
        patterns = {
            "v2ray.txt": r"v2ray.*?(https?://[^\s<>'\"，）)]+)(?:\\n|\n|$)",
            "clash.yaml": r"clash.*?(https?://[^\s<>'\"，）)]+)(?:\\n|\n|$)",
        }
        return create_download_tasks_from_regex_rules(content, patterns)
