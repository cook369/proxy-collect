import logging

from collectors.base import BaseCollector, register_collector
from config.settings import default_config
from core.models import DownloadTask
from services.paste_to_service import PasteToService
from utils.check import check_html_contains
from utils.extractors import create_download_tasks_from_regex_rules
from utils.paste_to import CharsetPasswordStrategy, DictionaryPasswordStrategy
from utils.youtube import extract_youtube_redirect_url, find_latest_video_url


@register_collector
class ZYFXSCollector(BaseCollector):
    """资源分享师站点采集器"""

    name = "zyfxs"
    home_page = (
        "https://www.youtube.com/playlist?list=PLFF7T03a7nnF-5POF9QxmABrzSKGy8fhC"
    )
    paste_to_password: str | None = None
    paste_to_password_strategy: (
        CharsetPasswordStrategy | DictionaryPasswordStrategy | None
    ) = None

    def get_download_tasks(self) -> list[DownloadTask]:
        """从 YouTube 最新视频中的 paste.to 分享提取订阅任务"""
        check_playlist = check_html_contains("playlistVideoRenderer")
        if not self.today_page:
            playlist_html = self.fetch_html(self.home_page, check_html=check_playlist)
            self.today_page = self.get_today_url(playlist_html)
        self.skip_if_cached()

        video_html = self.fetch_html(self.today_page)
        paste_url = self.extract_paste_url(video_html)

        logging.info(f"[{self.name}] try decrypt {paste_url} share")
        paste_to_service = PasteToService(
            http_client=self.http_client,
            timeout=default_config.collector.fetch_timeout,
            max_workers=default_config.collector.paste_to_password_workers,
            password_strategy=self.paste_to_password_strategy,
        )
        decrypt_result = paste_to_service.decrypt_url(
            paste_url,
            password=self.paste_to_password,
        )
        if not self.paste_to_password:
            logging.info(
                f"[{self.name}] password decrypt {paste_url} with {decrypt_result.password} share"
            )
        return self.parse_subscription_tasks(decrypt_result.content)

    def get_today_url(self, home_html: str) -> str:
        """从 YouTube 播放列表页面提取最新视频 URL"""
        video, title = find_latest_video_url(
            home_html,
            ("节点分享", "免费节点"),
            reverse=True,
        )
        logging.info(f"[{self.name}] find video {video}, title {title}")

        return video

    def extract_paste_url(self, video_html: str) -> str:
        """从 YouTube 视频页提取 paste.to 分享 URL"""
        target_url = extract_youtube_redirect_url(
            video_html,
            "paste.to",
        )
        return target_url

    def parse_subscription_tasks(self, content: str) -> list[DownloadTask]:
        """从解密后的分享内容提取订阅链接"""
        patterns = {
            "v2ray.txt": r"V2ray.*?(https?://[^\s<>'\"，）)]+?\.jpg)",
            "clash.yaml": r"clash.*?(https?://[^\s<>'\"，）)]+?\.jpg)",
        }
        return create_download_tasks_from_regex_rules(content, patterns)
