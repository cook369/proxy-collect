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

    INFO_LABELS = ("更新时间", "站点", "采集地址")
    INFO_GROUP_NAME = "订阅信息"
    INFO_PROXY_TEMPLATE = {
        "type": "vless",
        "server": "127.0.0.1",
        "port": 0,
        "uuid": "00000000-0000-0000-0000-000000000000",
        "network": "ws",
        "skip-cert-verify": True,
        "tls": False,
    }

    @staticmethod
    def _is_subscription_info_name(name: str) -> bool:
        return any(name.startswith(f"{label} ") for label in FileProcessor.INFO_LABELS)

    @staticmethod
    def _is_subscription_info_proxy(proxy: dict) -> bool:
        name = proxy.get("name")
        return (
            isinstance(name, str)
            and FileProcessor._is_subscription_info_name(name)
            and proxy.get("uuid") == FileProcessor.INFO_PROXY_TEMPLATE["uuid"]
            and proxy.get("server") == FileProcessor.INFO_PROXY_TEMPLATE["server"]
            and proxy.get("port") == FileProcessor.INFO_PROXY_TEMPLATE["port"]
        )

    @staticmethod
    def _is_subscription_info_group(group: dict) -> bool:
        proxies = group.get("proxies")
        return (
            group.get("name") == FileProcessor.INFO_GROUP_NAME
            and group.get("type") == "select"
            and isinstance(proxies, list)
            and len(proxies) == len(FileProcessor.INFO_LABELS)
            and all(
                isinstance(proxy_name, str)
                and FileProcessor._is_subscription_info_name(proxy_name)
                for proxy_name in proxies
            )
        )

    @staticmethod
    def _build_subscription_info_names(
        result: CollectorResult, timestamp: str
    ) -> list[str]:
        values = {
            "更新时间": timestamp,
            "站点": result.site,
            "采集地址": result.today_page,
        }
        return [f"{label} {values[label]}" for label in FileProcessor.INFO_LABELS]

    @staticmethod
    def _remove_existing_subscription_info(data: dict) -> None:
        """删除旧的订阅信息，保证重复处理同一文件时结果稳定。"""
        if isinstance(data.get("proxies"), list):
            data["proxies"] = [
                proxy
                for proxy in data["proxies"]
                if not (
                    isinstance(proxy, dict)
                    and FileProcessor._is_subscription_info_proxy(proxy)
                )
            ]

        if isinstance(data.get("proxy-groups"), list):
            data["proxy-groups"] = [
                group
                for group in data["proxy-groups"]
                if not (
                    isinstance(group, dict)
                    and FileProcessor._is_subscription_info_group(group)
                )
            ]

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

        names = FileProcessor._build_subscription_info_names(result, timestamp)

        data = yaml.safe_load(content)
        if not isinstance(data, dict):
            logging.warning(f"[{result.site}] Unexpected YAML format, skipping timestamp injection")
            return content
        FileProcessor._remove_existing_subscription_info(data)

        for name in names:
            new_node = {"name": name, **FileProcessor.INFO_PROXY_TEMPLATE}
            if "proxies" in data:
                data["proxies"].insert(0, new_node)
        if "proxy-groups" in data:
            group = {
                "name": FileProcessor.INFO_GROUP_NAME,
                "proxies": names,
                "type": "select",
            }

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
