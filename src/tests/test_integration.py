"""集成测试

测试多个组件协同工作的场景。
"""

import tempfile
from pathlib import Path
from unittest.mock import Mock

from collectors.base import BaseCollector
from core.models import CollectorResult, FileManifest, DownloadTask
from services.manifest_service import ManifestService
from services.file_processor import FileProcessor


class TestCollectorWithManifest:
    """采集器与 Manifest 服务集成测试"""

    def test_collector_result_updates_manifest(self):
        """测试采集结果更新 manifest"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_file = Path(tmpdir) / "manifest.json"
            manifest = ManifestService(manifest_file)

            # 模拟采集结果
            result = CollectorResult(
                site="test_site",
                today_page="http://example.com/today",
                files={
                    "clash.yaml": FileManifest(
                        url="http://example.com/clash.yaml", success=True
                    )
                },
                status="success",
            )

            manifest.update_from_result(result)
            manifest.save()

            # 重新加载验证
            manifest2 = ManifestService(manifest_file)
            assert "test_site" in manifest2.sites
            assert manifest2.sites["test_site"].status == "success"

    def test_manifest_skip_downloaded(self):
        """测试 manifest 跳过已下载文件"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_file = Path(tmpdir) / "manifest.json"
            manifest = ManifestService(manifest_file)

            # 添加已下载记录
            result = CollectorResult(
                site="test_site",
                today_page="http://example.com/today",
                files={
                    "clash.yaml": FileManifest(
                        url="http://example.com/clash.yaml", success=True
                    )
                },
                status="success",
            )
            manifest.update_from_result(result)

            # 验证不需要重新下载
            should = manifest.should_download(
                "test_site", "http://example.com/clash.yaml"
            )
            assert should is False


class TestCollectorWithFileProcessor:
    """采集器与文件处理器集成测试"""

    def test_download_and_process_yaml(self):
        """测试下载并处理 YAML 文件"""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            site_dir = output_dir / "test_site"
            site_dir.mkdir()

            # 创建测试文件
            clash_file = site_dir / "clash.yaml"
            clash_file.write_text("proxies:\n  - name: node1\n", encoding="utf-8")

            # 处理文件
            FileProcessor.process_downloaded_file(
                clash_file, "test_site", "2026-01-30 10:00"
            )

            content = clash_file.read_text(encoding="utf-8")
            assert "更新时间 2026-01-30 10:00 | test_site" in content


class TestEndToEndCollector:
    """端到端采集器测试"""

    def test_full_collector_flow(self):
        """测试完整采集流程"""
        mock_http = Mock()
        # 返回足够长的内容通过验证
        mock_http.get.return_value = "x" * 200

        class TestCollector(BaseCollector):
            name = "e2e_test"
            home_page = "http://example.com"

            def get_download_tasks(self):
                return [
                    DownloadTask(filename="test.txt", url="http://example.com/test.txt")
                ]

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            collector = TestCollector(http_client=mock_http)
            result = collector.run(output_dir)

            assert result.status == "success"
            assert result.site == "e2e_test"
            assert (output_dir / "e2e_test" / "test.txt").exists()

    def test_collector_with_validation_failure(self):
        """测试内容验证失败的情况"""
        mock_http = Mock()
        mock_http.get.return_value = "too short"  # 小于 100 bytes

        class TestCollector(BaseCollector):
            name = "validation_test"
            home_page = "http://example.com"

            def get_download_tasks(self):
                return [
                    DownloadTask(filename="test.txt", url="http://example.com/test.txt")
                ]

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            collector = TestCollector(http_client=mock_http)
            result = collector.run(output_dir)

            # 验证失败应该标记为 failed
            assert result.files["test.txt"].success is False
