"""Manifest 服务（异步版本）

管理 manifest.json，记录采集状态和缓存信息。
"""

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from core.models import CollectorResult, FileManifest, SiteManifest


class ManifestService:
    """Manifest 服务（异步）"""

    def __init__(self, manifest_file: Path):
        self.manifest_file = manifest_file
        self.last_run: Optional[str] = None
        self.sites: dict[str, SiteManifest] = {}
        self._load()

    def _load(self):
        """加载 manifest 文件（同步，因为 __init__ 不能是 async）"""
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
                    title=site_data.get("title"),
                    collected_at=site_data.get("collected_at"),
                    duration_seconds=site_data.get("duration_seconds"),
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
        existing = self.sites.get(result.site)

        if result.from_cache and existing is not None:
            # 缓存命中：保留旧的真实采集时间、标题、updated_at、耗时
            collected_at = existing.collected_at
            title = existing.title
            updated_at = existing.updated_at
            duration_seconds = existing.duration_seconds
        else:
            # 首次采集 / 失败重采：用本次真实时间
            collected_at = result.collected_at or now
            title = result.title
            updated_at = now if result.status != "failed" else None
            duration_seconds = result.duration_seconds

        self.sites[result.site] = SiteManifest(
            today_page=result.today_page,
            status=result.status,
            updated_at=updated_at,
            title=title,
            collected_at=collected_at,
            duration_seconds=duration_seconds,
            files=result.files,
            error=result.error,
        )

    async def save(self):
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
                "title": site_data.title,
                "collected_at": site_data.collected_at,
                "duration_seconds": site_data.duration_seconds,
                "files": files_dict,
            }
            if site_data.error:
                site_dict["error"] = site_data.error

            data["sites"][site_name] = site_dict

        self.manifest_file.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(
            self.manifest_file.write_text,
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def get_site(self, site: str) -> Optional[SiteManifest]:
        """获取站点信息"""
        return self.sites.get(site)
