"""文件处理服务

处理下载文件的后处理，包括时间戳注入。
"""
from datetime import datetime
from pathlib import Path
from typing import Optional
import logging
import re


class FileProcessor:
    """文件处理器"""

    @staticmethod
    def inject_timestamp_to_clash(
        content: str,
        site: str,
        timestamp: Optional[str] = None
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

        # VLESS 时间戳节点
        timestamp_node = f'''  - name: "⏰ {timestamp} | {site}"
    type: vless
    server: 127.0.0.1
    port: 1
    uuid: 00000000-0000-0000-0000-000000000000
    tls: false
    skip-cert-verify: true
    udp: false
'''
        # 查找 proxies: 行并在其后插入
        pattern = r'(proxies:\s*\n)'
        if re.search(pattern, content):
            content = re.sub(pattern, r'\1' + timestamp_node, content, count=1)
        else:
            logging.warning(f"[{site}] No 'proxies:' found in clash.yaml")

        return content

    @staticmethod
    def process_downloaded_file(
        file_path: Path,
        site: str,
        timestamp: Optional[str] = None
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
                content, site, timestamp
            )
            file_path.write_text(processed, encoding="utf-8")
            logging.info(f"[{site}] Injected timestamp to {filename}")
