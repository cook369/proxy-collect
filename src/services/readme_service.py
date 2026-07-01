"""README 生成服务

负责生成和维护 README.md 中的采集状态表格与订阅链接。
"""

import logging
import os
import re
import subprocess
from pathlib import Path
from urllib.parse import quote

from core.models import SiteManifest
from services.manifest_service import ManifestService

DEFAULT_GITHUB_REPOSITORY = "cook369/proxy-collect"


class ReadmeService:
    """README 生成服务"""

    def __init__(
        self,
        manifest: ManifestService,
        readme_file: Path,
        github_prefix: str,
        output_dir: Path,
    ):
        self.manifest = manifest
        self.readme_file = readme_file
        self.github_prefix = github_prefix
        self.output_dir = output_dir

    def update(self) -> None:
        """更新 README.md"""
        github_repository = self.get_github_repository()
        github_branch = self.get_current_branch()

        lines = self._build_status_section(github_repository, github_branch)

        self._write_readme(lines)

    def _build_status_section(
        self, repository: str, branch: str
    ) -> list[str]:
        """构建采集状态表格（含订阅链接）"""

        lines = ["\n## 采集状态\n"]
        lines.append("| 站点 | 状态 | 耗时 | 采集时间 | Clash | V2Ray | 来源 |")
        lines.append("|------|------|------|----------|-------|-------|------|")

        for site_name in sorted(self.manifest.sites.keys()):
            site = self.manifest.sites[site_name]
            status_icon = {"success": "✅", "partial": "⚠️", "failed": "❌"}.get(
                site.status, "❓"
            )
            # 耗时
            if site.duration_seconds is not None:
                duration = f"{site.duration_seconds:.1f}s"
            else:
                duration = "-"
            # 采集时间
            collected = site.collected_at[:16] if site.collected_at else "-"
            # 订阅文件状态（含链接）
            clash_cell = self._file_cell(
                site, site_name, "clash.yaml", repository, branch
            )
            v2ray_cell = self._file_cell(
                site, site_name, "v2ray.txt", repository, branch
            )
            # 来源
            source_parts = []
            if site.today_page:
                source_parts.append(f"[链接]({site.today_page})")
            if site.title:
                source_parts.append(f"*{site.title}*")
            source = " - ".join(source_parts) if source_parts else "-"
            lines.append(
                f"| {site_name} | {status_icon} | {duration} | {collected} "
                f"| {clash_cell} | {v2ray_cell} | {source} |"
            )

        lines.append(f"\n**最后运行**: {self.manifest.last_run}\n")
        lines.append("\n---\n")
        return lines

    def _file_cell(
        self, site: SiteManifest, site_name: str, filename: str,
        repository: str, branch: str
    ) -> str:
        """返回订阅文件在表格中的状态图标，成功时附带链接"""
        if site.status == "failed":
            return "-"
        file_info = site.files.get(filename)
        if file_info is None:
            return "-"
        if file_info.success:
            url = self._build_raw_github_url(
                self.github_prefix, repository, branch, site_name, filename
            )
            return f"[✅]({url})"
        return "❌"

    def _write_readme(self, lines: list[str]) -> None:
        """写入 README 文件，保留已有内容的前半部分"""
        if self.readme_file.exists():
            content = self.readme_file.read_text(encoding="utf-8")
            if "## 采集状态" in content:
                content = content.split("## 采集状态")[0].rstrip()
            content += "\n" + "\n".join(lines)
        else:
            content = "\n".join(lines)

        self.readme_file.write_text(content, encoding="utf-8")

    # -------------------- 静态工具方法 -------------------- #

    @staticmethod
    def _build_raw_github_url(
        github_prefix: str,
        repository: str,
        branch: str,
        site_name: str,
        filename: str,
    ) -> str:
        """构建 raw GitHub URL（带代理前缀）"""
        encoded_branch = quote(branch, safe="/")
        return (
            f"{github_prefix}/https://raw.githubusercontent.com/"
            f"{repository}/refs/heads/{encoded_branch}/dist/{site_name}/{filename}"
        )

    @staticmethod
    def get_current_branch() -> str:
        """获取当前 git 分支名"""
        env_branch = os.getenv("GITHUB_HEAD_REF") or os.getenv("GITHUB_REF_NAME")
        if env_branch:
            return env_branch

        try:
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=Path(__file__).resolve().parent.parent.parent,
                capture_output=True,
                text=True,
                check=True,
            )
            branch = result.stdout.strip()
            if branch and branch != "HEAD":
                return branch
        except Exception:
            logging.debug("Failed to detect current git branch", exc_info=True)

        return "main"

    @staticmethod
    def get_github_repository() -> str:
        """获取 GitHub owner/repo"""
        env_repository = os.getenv("GITHUB_REPOSITORY")
        if env_repository:
            return env_repository

        try:
            result = subprocess.run(
                ["git", "config", "--get", "remote.origin.url"],
                cwd=Path(__file__).resolve().parent.parent.parent,
                capture_output=True,
                text=True,
                check=True,
            )
            remote_url = result.stdout.strip()
            match = re.search(
                r"github\.com[:/](?P<repo>[^/\s]+/[^/\s]+?)(?:\.git)?$",
                remote_url,
            )
            if match:
                return match.group("repo")
        except Exception:
            logging.debug("Failed to detect GitHub repository", exc_info=True)

        return DEFAULT_GITHUB_REPOSITORY
