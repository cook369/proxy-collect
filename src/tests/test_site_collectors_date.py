"""Nodefree 和 Oneclash 采集器测试"""

from unittest.mock import Mock

from collectors.sites.nodefree import NodefreeCollector
from collectors.sites.oneclash import OneclashCollector
from core.interfaces import HttpClient


class TestNodefreeCollector:
    """NodefreeCollector 测试类"""

    def test_get_today_url(self):
        """测试从首页获取今日链接"""
        mock_http_client = Mock(spec=HttpClient)
        collector = NodefreeCollector(http_client=mock_http_client)

        home_html = """
        <html>
            <body>
                <a href="https://nodefree.me/2026/01/today.html">订阅链接免费节点</a>
            </body>
        </html>
        """

        today_url = collector.get_today_url(home_html)
        assert today_url == "https://nodefree.me/2026/01/today.html"

    def test_get_today_url_not_found(self):
        """测试首页未找到链接的情况"""
        mock_http_client = Mock(spec=HttpClient)
        collector = NodefreeCollector(http_client=mock_http_client)

        home_html = "<html><body>No links</body></html>"

        result = collector.get_today_url(home_html)
        assert result is None

    def test_parse_download_tasks(self):
        """测试解析下载任务"""
        mock_http_client = Mock(spec=HttpClient)
        collector = NodefreeCollector(http_client=mock_http_client)

        today_html = """
        <html>
            <body>
                <h2>v2ray订阅链接</h2>
                <p>https://example.com/v2ray.txt</p>
                <h2>clash订阅链接</h2>
                <p>https://example.com/clash.yaml</p>
            </body>
        </html>
        """

        tasks = collector.parse_download_tasks(today_html)

        assert len(tasks) == 2
        filenames = [t.filename for t in tasks]
        urls = [t.url for t in tasks]
        assert "v2ray.txt" in filenames
        assert "clash.yaml" in filenames
        assert "https://example.com/v2ray.txt" in urls
        assert "https://example.com/clash.yaml" in urls

    def test_collector_name(self):
        """测试采集器名称"""
        mock_http_client = Mock(spec=HttpClient)
        collector = NodefreeCollector(http_client=mock_http_client)

        assert collector.name == "nodefree"
        assert collector.home_page == "https://nodefree.me"


class TestOneclashCollector:
    """OneclashCollector 测试类"""

    def test_get_today_url(self):
        """测试从首页获取今日链接"""
        mock_http_client = Mock(spec=HttpClient)
        collector = OneclashCollector(http_client=mock_http_client)

        home_html = """
        <html>
            <body>
                <a href="https://oneclash.cc/2026/01/today.html">免费节点高速订阅链接</a>
            </body>
        </html>
        """

        today_url = collector.get_today_url(home_html)
        assert today_url == "https://oneclash.cc/2026/01/today.html"

    def test_get_today_url_not_found(self):
        """测试首页未找到链接的情况"""
        mock_http_client = Mock(spec=HttpClient)
        collector = OneclashCollector(http_client=mock_http_client)

        home_html = "<html><body>No links</body></html>"

        result = collector.get_today_url(home_html)
        assert result is None

    def test_parse_download_tasks(self):
        """测试解析下载任务"""
        mock_http_client = Mock(spec=HttpClient)
        collector = OneclashCollector(http_client=mock_http_client)

        today_html = """
        <html>
            <body>
                <p>v2ray订阅链接</p>
                <p>https://example.com/v2ray.txt</p>
                <p>Clash订阅链接</p>
                <p>https://example.com/clash.yaml</p>
            </body>
        </html>
        """

        tasks = collector.parse_download_tasks(today_html)

        assert len(tasks) == 2
        filenames = [t.filename for t in tasks]
        urls = [t.url for t in tasks]
        assert "v2ray.txt" in filenames
        assert "clash.yaml" in filenames
        assert "https://example.com/v2ray.txt" in urls
        assert "https://example.com/clash.yaml" in urls

    def test_collector_name(self):
        """测试采集器名称"""
        mock_http_client = Mock(spec=HttpClient)
        collector = OneclashCollector(http_client=mock_http_client)

        assert collector.name == "oneclash"
        assert collector.home_page == "https://oneclash.cc"
