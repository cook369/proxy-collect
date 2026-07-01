import logging
import re
import zipfile
from io import BytesIO

from collectors.base import YouTubeBaseCollector, register_collector
from core.exceptions import ParseError
from core.models import DownloadTask
from utils.extractors import create_download_tasks_from_file
from utils.youtube import find_latest_video_url_in_home

# zip 安全限制
MAX_ZIP_ENTRIES = 50
MAX_ZIP_ENTRY_SIZE = 10 * 1024 * 1024  # 10MB 单文件


@register_collector
class FXRJCollector(YouTubeBaseCollector):
    """分享日记站点采集器"""

    name = "fxrj"
    home_page = "https://www.youtube.com/@fxrj"
    redirect_target_host = "drive.google.com"

    def get_today_url(self, home_html: str) -> tuple[str, str]:
        """从 YouTube 频道页提取最新视频 (url, title)"""
        video, title = find_latest_video_url_in_home(home_html)
        logging.info(f"[{self.name}] find video {video}, title {title}")
        return video, ""

    def resolve_tasks_from_redirect(self, target_url: str) -> list[DownloadTask]:
        """从 Google Drive 下载 zip 并提取订阅任务"""
        download_url = self._convert_gdriver_download_url(target_url)
        logging.info(f"[{self.name}] try decrypt {target_url} share")
        return self.parse_subscription_tasks(download_url)

    @staticmethod
    def _convert_gdriver_download_url(url: str) -> str:
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
                    f"Zip file contains too many entries "
                    f"({len(names)}), limit is {MAX_ZIP_ENTRIES}"
                )

            for name in names:
                if name.endswith("/"):
                    continue

                basename = name.split("/")[-1]
                if basename.startswith(".") or ".." in name:
                    continue

                info = zf.getinfo(name)
                if info.file_size > MAX_ZIP_ENTRY_SIZE:
                    logging.warning(
                        f"[{self.name}] Skipping oversized file "
                        f"{name} ({info.file_size} bytes)"
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
                if key not in result:
                    result[key] = content.decode("utf-8", errors="ignore")
                else:
                    logging.warning(
                        f"[{self.name}] Skipping duplicate file {name}, "
                        f"already have {key}"
                    )
        finally:
            zf.close()

        return create_download_tasks_from_file(result)
