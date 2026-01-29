"""Manifest 服务

管理 manifest.json，记录采集状态和缓存信息。
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from core.models import CollectorResult, FileManifest, SiteManifest


class ManifestService:
    """Manifest 服务"""

    def __init__(self, manifest_file: Path):
        self.manifest_file = manifest_file
        self.last_run: Optional[str] = None
        self.sites: dict[str, SiteManifest] = {}
        self._load()

    def _load(self):
        """加载 manifest 文件"""
        if not self.manifest_file.exists():
            return

        try:
            data = json.loads(self.manifest_file.read_text(encoding="utf-8"))
            self.last_run = data.get("last_run")

            for site_name, site_data in data.get("sites", {}).items():
                files = {}
                for fname, fdata in site_data.get("files", {}).items():
                    files[fname] = FileManifest(
                        url=fdata.get("url", ""),
                        success=fdata.get("success", False),
                        error=fdata.get("error"),
                    )

                self.sites[site_name] = SiteManifest(
                    today_page=site_data.get("today_page"),
                    status=site_data.get("status", "unknown"),
                    updated_at=site_data.get("updated_at"),
                    files=files,
                    error=site_data.get("error"),
                )
        except Exception as e:
            logging.warning(f"Failed to load manifest: {e}")

    def should_download(self, site: str, url: str) -> bool:
        """判断是否需要下载

        Args:
            site: 站点名称
            url: 下载 URL

        Returns:
            是否需要下载
        """
        site_data = self.sites.get(site)
        if not site_data:
            return True

        for file_info in site_data.files.values():
            if file_info.url == url and file_info.success:
                return False

        return True

    def update_from_result(self, result: CollectorResult):
        """从采集结果更新 manifest

        Args:
            result: 采集结果
        """
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        self.sites[result.site] = SiteManifest(
            today_page=result.today_page,
            status=result.status,
            updated_at=now if result.status != "failed" else None,
            files=result.files,
            error=result.error,
        )

    def save(self):
        """保存 manifest 到文件"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.last_run = now

        data = {"last_run": self.last_run, "sites": {}}

        for site_name, site_data in self.sites.items():
            files_dict = {}
            for fname, fdata in site_data.files.items():
                files_dict[fname] = {
                    "url": fdata.url,
                    "success": fdata.success,
                }
                if fdata.error:
                    files_dict[fname]["error"] = fdata.error

            site_dict = {
                "today_page": site_data.today_page,
                "status": site_data.status,
                "updated_at": site_data.updated_at,
                "files": files_dict,
            }
            if site_data.error:
                site_dict["error"] = site_data.error

            data["sites"][site_name] = site_dict

        self.manifest_file.parent.mkdir(parents=True, exist_ok=True)
        self.manifest_file.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def get_site(self, site: str) -> Optional[SiteManifest]:
        """获取站点信息"""
        return self.sites.get(site)
