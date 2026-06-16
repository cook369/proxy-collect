import logging
import re
import zipfile
from io import BytesIO

from collectors.base import BaseCollector, register_collector
from core.exceptions import ParseError
from core.models import DownloadTask
from utils.check import check_html_contains
from utils.extractors import create_download_tasks_from_file
from utils.youtube import extract_youtube_redirect_url, find_latest_video_url_in_home

# zip 安全限制
MAX_ZIP_ENTRIES = 50
MAX_ZIP_ENTRY_SIZE = 10 * 1024 * 1024  # 10MB 单文件


@register_collector
class FXRJCollector(BaseCollector):
    """分享日记站点采集器"""

    name = "fxrj"
    home_page = "https://www.youtube.com/@fxrj"

    def get_download_tasks(self) -> list[DownloadTask]:
        """从 YouTube 最新视频中的 Google Drive 分享提取订阅任务"""
        check_playlist = check_html_contains("免费节点")
        if not self.today_page:
            home_html = self.fetch_html(self.home_page, check_html=check_playlist)
            self.today_page = self.get_today_url(home_html)
        self.skip_if_cached()

        video_html = self.fetch_html(self.today_page)
        gdriver_url = self.extract_gdriver_url(video_html)

        logging.info(f"[{self.name}] try decrypt {gdriver_url} share")

        return self.parse_subscription_tasks(gdriver_url)

    def get_today_url(self, home_html: str) -> str:
        """从 YouTube 主页提取最新视频 URL"""
        video, title = find_latest_video_url_in_home(
            home_html,
        )
        logging.info(f"[{self.name}] find video {video}, title {title}")

        return video

    def extract_gdriver_url(self, video_html: str) -> str:
        """从 YouTube 视频页提取 Google Drive 分享 URL"""
        target_url = extract_youtube_redirect_url(
            video_html,
            "drive.google.com",
        )
        return self.convert_gdriver_download_url(target_url)

    def convert_gdriver_download_url(self, url: str) -> str:
        """将 Google Drive 分享链接转换为直接下载链接"""
        m = re.search(r"/file/d/([^/]+)", url)
        if not m:
            raise ValueError("Invalid Google Drive file sharing link")

        file_id = m.group(1)

        return (
            f"https://drive.usercontent.google.com/download"
            f"?id={file_id}&export=download&authuser=0"
        )

    def parse_subscription_tasks(self, url: str) -> list[DownloadTask]:
        """从 Google Drive 下载的 zip 文件中提取订阅配置"""
        data = self.fetch_data(url)
        zip_buffer = BytesIO(data)

        try:
            zf = zipfile.ZipFile(zip_buffer)
        except zipfile.BadZipFile as e:
            raise ParseError(f"Downloaded content is not a valid zip file: {e}") from e

        result: dict[str, str] = {}

        try:
            names = zf.namelist()
            if len(names) > MAX_ZIP_ENTRIES:
                raise ParseError(
                    f"Zip file contains too many entries ({len(names)}), limit is {MAX_ZIP_ENTRIES}"
                )

            for name in names:
                # 跳过目录
                if name.endswith("/"):
                    continue

                # 跳过隐藏文件和路径遍历
                basename = name.split("/")[-1]
                if basename.startswith(".") or ".." in name:
                    continue

                info = zf.getinfo(name)
                if info.file_size > MAX_ZIP_ENTRY_SIZE:
                    logging.warning(
                        f"[{self.name}] Skipping oversized file {name} ({info.file_size} bytes)"
                    )
                    continue

                key = basename
                if basename.endswith(".txt"):
                    key = "v2ray.txt"
                elif basename.endswith(".yaml"):
                    key = "clash.yaml"
                else:
                    continue

                content = zf.read(name)
                # 同类型文件只保留第一个，避免覆盖
                if key not in result:
                    result[key] = content.decode("utf-8", errors="ignore")
                else:
                    logging.warning(
                        f"[{self.name}] Skipping duplicate file {name}, already have {key}"
                    )
        finally:
            zf.close()

        return create_download_tasks_from_file(result)
