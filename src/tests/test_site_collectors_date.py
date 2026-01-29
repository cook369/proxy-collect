"""基于日期的站点采集器测试"""
import pytest
from unittest.mock import Mock, patch
from datetime import datetime

from collectors.sites.nodefree import NodefreeCollector
from collectors.sites.oneclash import OneclashCollector
from core.interfaces import HttpClient


class TestNodefreeCollector:
    """NodefreeCollector 测试类"""

    @patch('collectors.mixins.datetime')
    def test_get_download_urls(self, mock_datetime):
        """测试获取下载 URL"""
        # 模拟日期为 2026-01-29
        mock_now = Mock()
        mock_now.strftime.return_value = "2026/01/20260129"
        mock_datetime.now.return_value = mock_now

        mock_http_client = Mock(spec=HttpClient)
        collector = NodefreeCollector(http_client=mock_http_client)

        urls = collector.get_download_urls()

        assert len(urls) == 2
        assert ("clash.yaml", "https://nodefree.githubrowcontent.com/2026/01/20260129.yaml") in urls
        assert ("v2ray.txt", "https://nodefree.githubrowcontent.com/2026/01/20260129.txt") in urls

    def test_collector_name(self):
        """测试采集器名称"""
        mock_http_client = Mock(spec=HttpClient)
        collector = NodefreeCollector(http_client=mock_http_client)

        assert collector.name == "nodefree"
        assert collector.home_page == "https://nodefree.me"


class TestOneclashCollector:
    """OneclashCollector 测试类"""

    @patch('collectors.mixins.datetime')
    def test_get_download_urls(self, mock_datetime):
        """测试获取下载 URL"""
        # 模拟日期为 2026-01-29
        mock_now = Mock()
        mock_now.strftime.return_value = "2026/01/20260129"
        mock_datetime.now.return_value = mock_now

        mock_http_client = Mock(spec=HttpClient)
        collector = OneclashCollector(http_client=mock_http_client)

        urls = collector.get_download_urls()

        assert len(urls) == 2
        assert ("clash.yaml", "https://oneclash.githubrowcontent.com/2026/01/20260129.yaml") in urls
        assert ("v2ray.txt", "https://oneclash.githubrowcontent.com/2026/01/20260129.txt") in urls

    def test_collector_name(self):
        """测试采集器名称"""
        mock_http_client = Mock(spec=HttpClient)
        collector = OneclashCollector(http_client=mock_http_client)

        assert collector.name == "oneclash"
        assert collector.home_page == "https://oneclash.cc"
