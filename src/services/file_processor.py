"""文件处理服务

处理下载文件的后处理，包括时间戳注入。
"""

from datetime import datetime
from pathlib import Path
from typing import Optional
import logging
import re

import yaml


class FileProcessor:
    """文件处理器"""

    @staticmethod
    def inject_timestamp_to_clash(
        content: str, site: str, timestamp: Optional[str] = None
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
        
        name = f"更新时间 {timestamp} | {site}"

        # VLESS 时间戳节点
        timestamp_node = {
            "name": name,
            "type": "vless",
            "server": "127.0.0.1", 
            "port": 1, 
            "uuid": "00000000-0000-0000-0000-000000000000",
            "network": "ws",
            "skip-cert-verify": True,
            "tls": False
            }
        data = yaml.safe_load(content)
        if 'proxies' in data:
            data['proxies'].insert(0, timestamp_node)
        if 'proxy-groups' in data:
            for i in range(len(data['proxy-groups'])):
                if 'proxies' in data['proxy-groups'][i]:
                    data['proxy-groups'][i]['proxies'].insert(0, name)
        
        content = yaml.safe_dump(data,allow_unicode=True)

        return content

    @staticmethod
    def process_downloaded_file(
        file_path: Path, site: str, timestamp: Optional[str] = None
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
