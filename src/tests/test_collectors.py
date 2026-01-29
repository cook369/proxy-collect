"""采集器基类单元测试"""
import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
import tempfile

from collectors.base import BaseCollector, register_collector
from core.models import CollectorResult
from core.interfaces import HttpClient
from core.exceptions import NetworkError


class TestBaseCollector:
    """BaseCollector 测试类"""

    def test_init_with_http_client(self):
        """测试使用 HTTP 客户端初始化"""
        mock_http_client = Mock(spec=HttpClient)

        class TestCollector(BaseCollector):
            name = "test"
            home_page = "http://example.com"

            def get_download_urls(self):
                return []

        collector = TestCollector(http_client=mock_http_client)
        assert collector.http_client == mock_http_client

    def test_init_without_http_client(self):
        """测试不提供 HTTP 客户端时的初始化（向后兼容）"""
        class TestCollector(BaseCollector):
            name = "test"
            home_page = "http://example.com"

            def get_download_urls(self):
                return []

        collector = TestCollector()
        # 应该自动创建 HttpService
        assert collector.http_client is not None

    def test_fetch_html_success(self):
        """测试成功获取 HTML"""
        mock_http_client = Mock(spec=HttpClient)
        mock_http_client.get.return_value = "<html>test</html>"

        class TestCollector(BaseCollector):
            name = "test"
            home_page = "http://example.com"

            def get_download_urls(self):
                return []

        collector = TestCollector(http_client=mock_http_client)
        html = collector.fetch_html("http://example.com")

        assert html == "<html>test</html>"
        mock_http_client.get.assert_called_once_with("http://example.com", timeout=20)

    def test_fetch_html_no_client(self):
        """测试未初始化 HTTP 客户端时的错误"""
        class TestCollector(BaseCollector):
            name = "test"
            home_page = "http://example.com"

            def get_download_urls(self):
                return []

        collector = TestCollector(http_client=Mock())
        collector.http_client = None

        with pytest.raises(NetworkError, match="HTTP client not initialized"):
            collector.fetch_html("http://example.com")

    def test_download_file_success(self):
        """测试成功下载文件"""
        mock_http_client = Mock(spec=HttpClient)
        # 返回足够长的内容以通过验证（MIN_FILE_SIZE = 100）
        mock_http_client.get.return_value = "x" * 200

        class TestCollector(BaseCollector):
            name = "test"
            home_page = "http://example.com"

            def get_download_urls(self):
                return []

        collector = TestCollector(http_client=mock_http_client)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            success = collector.download_file("test.txt", "http://example.com/test.txt", output_dir)

            assert success is True
            file_path = output_dir / "test" / "test.txt"
            assert file_path.exists()
            assert file_path.read_text(encoding="utf-8") == "x" * 200

    def test_download_file_failure(self):
        """测试下载文件失败"""
        mock_http_client = Mock(spec=HttpClient)
        mock_http_client.get.side_effect = Exception("Network error")

        class TestCollector(BaseCollector):
            name = "test"
            home_page = "http://example.com"

            def get_download_urls(self):
                return []

        collector = TestCollector(http_client=mock_http_client)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            success = collector.download_file("test.txt", "http://example.com/test.txt", output_dir)

            assert success is False


class TestCollectorRun:
    """采集器 run 方法测试类"""

    def test_run_success(self):
        """测试成功的采集流程"""
        mock_http_client = Mock(spec=HttpClient)
        # 返回足够长的内容以通过验证
        mock_http_client.get.return_value = "x" * 200

        class TestCollector(BaseCollector):
            name = "test"
            home_page = "http://example.com"

            def get_download_urls(self):
                return [("test.txt", "http://example.com/test.txt")]

        collector = TestCollector(http_client=mock_http_client)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            result = collector.run(output_dir)

            assert isinstance(result, CollectorResult)
            assert result.site == "test"
            assert result.status == "success"
            assert len(result.files) == 1
            assert result.files["test.txt"].success is True

    def test_run_failure(self):
        """测试采集失败的情况"""
        mock_http_client = Mock(spec=HttpClient)

        class TestCollector(BaseCollector):
            name = "test"
            home_page = "http://example.com"

            def get_download_urls(self):
                raise Exception("Failed to get URLs")

        collector = TestCollector(http_client=mock_http_client)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            result = collector.run(output_dir)

            assert result.status == "failed"
            assert len(result.files) == 0
            assert result.error is not None


class TestCollectorRegistry:
    """采集器注册表测试类"""

    def test_register_collector(self):
        """测试采集器注册"""
        from collectors.base import COLLECTOR_REGISTRY

        @register_collector
        class TestCollector(BaseCollector):
            name = "test_registry"
            home_page = "http://example.com"

            def get_download_urls(self):
                return []

        assert "test_registry" in COLLECTOR_REGISTRY
        assert COLLECTOR_REGISTRY["test_registry"] == TestCollector
