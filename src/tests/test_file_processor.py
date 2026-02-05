"""FileProcessor 单元测试"""

import tempfile
from pathlib import Path
from unittest.mock import patch

from services.file_processor import FileProcessor


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
            content, "test_site", "2026-01-30 10:00"
        )

        assert "更新时间 2026-01-30 10:00 | test_site" in result
        assert "type: vless" in result
        assert "server: 127.0.0.1" in result

    def test_inject_timestamp_no_proxies_section(self):
        """测试没有 proxies 部分的情况"""
        content = """port: 7890
rules:
  - DOMAIN,example.com,DIRECT
"""
        result = FileProcessor.inject_timestamp_to_clash(
            content, "test_site", "2026-01-30 10:00"
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
            result = FileProcessor.inject_timestamp_to_clash(content, "test_site")

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
            content, "test", "2026-01-30 10:00"
        )

        assert "port: 7890" in result
        assert "node1" in result
        assert "type: ss" in result


class TestProcessDownloadedFile:
    """process_downloaded_file 方法测试"""

    def test_process_yaml_file(self):
        """测试处理 YAML 文件"""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "clash.yaml"
            file_path.write_text("proxies:\n  - name: test\n", encoding="utf-8")

            FileProcessor.process_downloaded_file(
                file_path, "test_site", "2026-01-30 10:00"
            )

            content = file_path.read_text(encoding="utf-8")
            assert "更新时间 2026-01-30 10:00 | test_site" in content

    def test_process_yml_file(self):
        """测试处理 .yml 扩展名文件"""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "config.yml"
            file_path.write_text("proxies:\n  - name: test\n", encoding="utf-8")

            FileProcessor.process_downloaded_file(
                file_path, "test_site", "2026-01-30 10:00"
            )

            content = file_path.read_text(encoding="utf-8")
            assert "更新时间" in content

    def test_process_nonexistent_file(self):
        """测试处理不存在的文件"""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "nonexistent.yaml"

            # 不应该抛出异常
            FileProcessor.process_downloaded_file(file_path, "test_site")

    def test_process_non_yaml_file(self):
        """测试处理非 YAML 文件（不做处理）"""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "v2ray.txt"
            original_content = "vmess://xxxxx"
            file_path.write_text(original_content, encoding="utf-8")

            FileProcessor.process_downloaded_file(file_path, "test_site")

            # 内容应该保持不变
            assert file_path.read_text(encoding="utf-8") == original_content
