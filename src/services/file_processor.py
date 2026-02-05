"""文件处理服务

处理下载文件的后处理，包括时间戳注入。
"""

from datetime import datetime
from pathlib import Path
from typing import Optional
import logging

import yaml

from core.models import CollectorResult


class FileProcessor:
    """文件处理器"""

    @staticmethod
    def inject_timestamp_to_clash(
        content: str, result: CollectorResult, timestamp: Optional[str] = None
    ) -> str:
        """注入时间戳节点到 clash.yaml

        Args:
            content: 原始 YAML 内容
            site: 站点名称
            timestamp: 时间戳，默认当前时间

        Returns:
            处理后的 YAML 内容
        """
        if timestamp is None:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

        names = [
            f"更新时间 {timestamp}",
            f"站点 {result.site}",
            f"采集地址 {result.today_page}",
        ]

        data = yaml.safe_load(content)

        for name in names:
            new_node = {
                "name": name,
                "type": "vless",
                "server": "127.0.0.1",
                "port": 0,
                "uuid": "00000000-0000-0000-0000-000000000000",
                "network": "ws",
                "skip-cert-verify": True,
                "tls": False,
            }
            if "proxies" in data:
                data["proxies"].insert(0, new_node)
        if "proxy-groups" in data:
            group = {"name": "订阅信息", "proxies": names, "type": "select"}

            data["proxy-groups"].insert(0, group)

        content = yaml.safe_dump(data, allow_unicode=True)

        return content

    @staticmethod
    def process_downloaded_file(
        file_path: Path, result: CollectorResult, timestamp: Optional[str] = None
    ):
        """处理下载的文件

        Args:
            file_path: 文件路径
            site: 站点名称
            timestamp: 时间戳
        """
        if not file_path.exists():
            return

        filename = file_path.name

        if filename.endswith(".yaml") or filename.endswith(".yml"):
            content = file_path.read_text(encoding="utf-8")
            processed = FileProcessor.inject_timestamp_to_clash(
                content, result, timestamp
            )
            file_path.write_text(processed, encoding="utf-8")
            logging.info(f"[{result.site}] Injected timestamp to {filename}")
