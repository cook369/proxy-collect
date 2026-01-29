"""简单日期URL采集器测试"""
import pytest
from unittest.mock import Mock, patch
from datetime import datetime

from collectors.sites.datia import DatiaCollector
from collectors.sites.jichangx import JichangxCollector
from core.interfaces import HttpClient


class TestDatiaCollector:
    """DatiaCollector 测试类"""

    @patch('collectors.mixins.datetime')
    def test_get_download_urls(self, mock_datetime):
        """测试获取下载 URL"""
        # 模拟日期为 2026-01-29
        mock_now = Mock()
        mock_now.strftime.return_value = "20260129"
        mock_datetime.now.return_value = mock_now

        mock_http_client = Mock(spec=HttpClient)
        collector = DatiaCollector(http_client=mock_http_client)

        urls = collector.get_download_urls()

        assert len(urls) == 2
        assert ("clash.yaml", "https://free.datiya.com/uploads/20260129-clash.yaml") in urls
        assert ("v2ray.txt", "https://free.datiya.com/uploads/20260129-v2ray.txt") in urls

    def test_collector_name(self):
        """测试采集器名称"""
        mock_http_client = Mock(spec=HttpClient)
        collector = DatiaCollector(http_client=mock_http_client)

        assert collector.name == "datiya"
        assert collector.home_page == "https://free.datiya.com"


class TestJichangxCollector:
    """JichangxCollector 测试类"""

    @patch('collectors.sites.jichangx.datetime')
    def test_get_download_urls(self, mock_datetime):
        """测试获取下载 URL"""
        # 模拟日期为 2026-01-29
        mock_now = Mock()
        mock_now.strftime.return_value = "20260129"
        mock_datetime.now.return_value = mock_now

        mock_http_client = Mock(spec=HttpClient)
        collector = JichangxCollector(http_client=mock_http_client)

        urls = collector.get_download_urls()

        assert len(urls) == 1
        assert urls[0] == ("v2ray.txt", "https://jichangx.com/nodes/v2ray-20260129-01")

    def test_collector_name(self):
        """测试采集器名称"""
        mock_http_client = Mock(spec=HttpClient)
        collector = JichangxCollector(http_client=mock_http_client)

        assert collector.name == "jichangx"
        assert collector.home_page == "https://jichangx.com"
