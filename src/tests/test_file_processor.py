"""FileProcessor 单元测试"""

import tempfile
from pathlib import Path
from unittest.mock import patch

import yaml

from core.models import CollectorResult
from services.file_processor import FileProcessor


def make_result(site: str = "test_site") -> CollectorResult:
    return CollectorResult(
        site=site,
        today_page="http://example.com/today",
        files={},
        status="success",
    )


class TestInjectTimestampToClash:
    """inject_timestamp_to_clash 方法测试"""

    def test_inject_timestamp_success(self):
        """测试成功注入时间戳"""
        content = """port: 7890
proxies:
  - name: "node1"
    type: ss
    server: 1.2.3.4
    port: 443
"""
        result = FileProcessor.inject_timestamp_to_clash(
            content, make_result(), "2026-01-30 10:00"
        )

        assert "更新时间 2026-01-30 10:00" in result
        assert "站点 test_site" in result
        assert "采集地址 http://example.com/today" in result
        assert "type: vless" in result
        assert "server: 127.0.0.1" in result

    def test_inject_timestamp_no_proxies_section(self):
        """测试没有 proxies 部分的情况"""
        content = """port: 7890
rules:
  - DOMAIN,example.com,DIRECT
"""
        result = FileProcessor.inject_timestamp_to_clash(
            content, make_result(), "2026-01-30 10:00"
        )

        # 没有 proxies 部分时，不会注入时间戳节点
        assert "更新时间" not in result

    def test_inject_timestamp_default_time(self):
        """测试使用默认时间戳"""
        content = """proxies:
  - name: "node1"
"""
        with patch("services.file_processor.datetime") as mock_dt:
            mock_dt.now.return_value.strftime.return_value = "2026-01-30 12:00"
            result = FileProcessor.inject_timestamp_to_clash(content, make_result())

        assert "2026-01-30 12:00" in result

    def test_inject_preserves_original_content(self):
        """测试注入后保留原始内容"""
        content = """port: 7890
proxies:
  - name: "node1"
    type: ss
    server: 1.2.3.4
"""
        result = FileProcessor.inject_timestamp_to_clash(
            content, make_result("test"), "2026-01-30 10:00"
        )

        assert "port: 7890" in result
        assert "node1" in result
        assert "type: ss" in result

    def test_inject_replaces_existing_subscription_info(self):
        """重复注入时替换旧订阅信息而不是追加"""
        content = """proxies:
  - name: node1
    type: ss
    server: 1.2.3.4
proxy-groups:
  - name: Auto
    type: select
    proxies:
      - node1
"""

        first = FileProcessor.inject_timestamp_to_clash(
            content, make_result(), "2026-01-30 10:00"
        )
        second = FileProcessor.inject_timestamp_to_clash(
            first, make_result(), "2026-01-30 11:00"
        )
        data = yaml.safe_load(second)

        info_proxy_names = [
            proxy["name"]
            for proxy in data["proxies"]
            if proxy["name"].startswith(("更新时间 ", "站点 ", "采集地址 "))
        ]
        info_groups = [
            group for group in data["proxy-groups"] if group["name"] == "订阅信息"
        ]

        assert info_proxy_names == [
            "采集地址 http://example.com/today",
            "站点 test_site",
            "更新时间 2026-01-30 11:00",
        ]
        assert len(info_groups) == 1
        assert info_groups[0]["proxies"] == [
            "更新时间 2026-01-30 11:00",
            "站点 test_site",
            "采集地址 http://example.com/today",
        ]

    def test_inject_preserves_original_info_like_proxy_names(self):
        """清理旧订阅信息时不能删除同名模式的原始代理"""
        content = """proxies:
  - name: 更新时间 original-node
    type: ss
    server: 1.2.3.4
    port: 443
"""

        first = FileProcessor.inject_timestamp_to_clash(
            content, make_result(), "2026-01-30 10:00"
        )
        second = FileProcessor.inject_timestamp_to_clash(
            first, make_result(), "2026-01-30 11:00"
        )
        data = yaml.safe_load(second)

        original_nodes = [
            proxy
            for proxy in data["proxies"]
            if proxy["name"] == "更新时间 original-node"
        ]

        assert original_nodes == [
            {
                "name": "更新时间 original-node",
                "type": "ss",
                "server": "1.2.3.4",
                "port": 443,
            }
        ]

    def test_inject_removes_generated_info_nodes_outside_header(self):
        """清理旧订阅信息时删除所有带占位特征的生成节点"""
        content = """proxies:
  - name: node1
    type: ss
    server: 1.2.3.4
  - name: 更新时间 2026-01-30 10:00
    type: vless
    server: 127.0.0.1
    port: 0
    uuid: 00000000-0000-0000-0000-000000000000
    network: ws
    skip-cert-verify: true
    tls: false
proxy-groups:
  - name: Auto
    type: select
    proxies:
      - node1
  - name: 订阅信息
    type: select
    proxies:
      - 更新时间 2026-01-30 10:00
      - 站点 test_site
      - 采集地址 http://example.com/today
"""

        result = FileProcessor.inject_timestamp_to_clash(
            content, make_result(), "2026-01-30 11:00"
        )
        data = yaml.safe_load(result)

        generated_info_nodes = [
            proxy
            for proxy in data["proxies"]
            if proxy["name"] == "更新时间 2026-01-30 10:00"
        ]
        info_groups = [
            group for group in data["proxy-groups"] if group["name"] == "订阅信息"
        ]

        assert generated_info_nodes == []
        assert len(info_groups) == 1
        assert info_groups[0]["proxies"] == [
            "更新时间 2026-01-30 11:00",
            "站点 test_site",
            "采集地址 http://example.com/today",
        ]

    def test_inject_preserves_original_subscription_info_group(self):
        """清理旧订阅信息时不能删除同名原始分组"""
        content = """proxies:
  - name: node1
    type: ss
    server: 1.2.3.4
proxy-groups:
  - name: 订阅信息
    type: select
    proxies:
      - node1
"""

        first = FileProcessor.inject_timestamp_to_clash(
            content, make_result(), "2026-01-30 10:00"
        )
        second = FileProcessor.inject_timestamp_to_clash(
            first, make_result(), "2026-01-30 11:00"
        )
        data = yaml.safe_load(second)

        original_groups = [
            group
            for group in data["proxy-groups"]
            if group["name"] == "订阅信息" and group["proxies"] == ["node1"]
        ]

        assert original_groups == [
            {"name": "订阅信息", "type": "select", "proxies": ["node1"]}
        ]


class TestProcessDownloadedFile:
    """process_downloaded_file 方法测试"""

    def test_process_yaml_file(self):
        """测试处理 YAML 文件"""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "clash.yaml"
            file_path.write_text("proxies:\n  - name: test\n", encoding="utf-8")

            FileProcessor.process_downloaded_file(
                file_path, make_result(), "2026-01-30 10:00"
            )

            content = file_path.read_text(encoding="utf-8")
            assert "更新时间 2026-01-30 10:00" in content
            assert "站点 test_site" in content

    def test_process_yml_file(self):
        """测试处理 .yml 扩展名文件"""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "config.yml"
            file_path.write_text("proxies:\n  - name: test\n", encoding="utf-8")

            FileProcessor.process_downloaded_file(
                file_path, make_result(), "2026-01-30 10:00"
            )

            content = file_path.read_text(encoding="utf-8")
            assert "更新时间" in content

    def test_process_nonexistent_file(self):
        """测试处理不存在的文件"""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "nonexistent.yaml"

            # 不应该抛出异常
            FileProcessor.process_downloaded_file(file_path, make_result())

    def test_process_non_yaml_file(self):
        """测试处理非 YAML 文件（不做处理）"""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "v2ray.txt"
            original_content = "vmess://xxxxx"
            file_path.write_text(original_content, encoding="utf-8")

            FileProcessor.process_downloaded_file(file_path, make_result())

            # 内容应该保持不变
            assert file_path.read_text(encoding="utf-8") == original_content
