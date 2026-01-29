"""下载记录服务

管理各站点的下载记录，避免重复下载。
"""
import json
import logging
from pathlib import Path
from threading import RLock


class RecordService:
    """下载记录服务"""

    def __init__(self, record_file: Path):
        self.record_file = record_file
        self.data: dict[str, dict[str, bool]] = {}
        self.lock = RLock()
        self._load()

    def _load(self):
        """加载记录文件"""
        if self.record_file.exists():
            try:
                self.data = json.loads(
                    self.record_file.read_text(encoding="utf-8")
                )
            except Exception as e:
                logging.warning(f"Failed to load record from {self.record_file}: {e}")

    def is_downloaded(self, site: str, url: str) -> bool:
        """检查 URL 是否已下载

        Args:
            site: 站点名称
            url: URL 地址

        Returns:
            是否已下载
        """
        with self.lock:
            return self.data.get(site, {}).get(url, False)

    def update_site(self, site: str, site_data: dict[str, bool]):
        """更新站点记录

        Args:
            site: 站点名称
            site_data: 站点数据（URL -> 是否成功）
        """
        with self.lock:
            self.data[site] = site_data

    def save(self):
        """保存记录到文件"""
        with self.lock:
            self.record_file.parent.mkdir(parents=True, exist_ok=True)
            self.record_file.write_text(
                json.dumps(self.data, indent=2),
                encoding="utf-8"
            )
