"""两步采集器测试 - CFMem 和 La85"""

from unittest.mock import Mock

from collectors.sites.cfmeme import CfmemeCollector
from collectors.sites.la85 import La85Collector
from core.interfaces import HttpClient


class TestCfmemeCollector:
    """CfmemeCollector 测试类"""

    def test_get_today_url(self):
        """测试从首页获取今日链接"""
        mock_http_client = Mock(spec=HttpClient)
        collector = CfmemeCollector(http_client=mock_http_client)

        home_html = """
        <html>
            <body>
                <a href="https://www.cfmem.com/other.html">免费节点更新</a>
                <a href="https://www.cfmem.com/2026/01/today.html">免费节点更新</a>
            </body>
        </html>
        """

        today_url = collector.get_today_url(home_html)
        assert today_url == "https://www.cfmem.com/2026/01/today.html"

    def test_get_today_url_not_found(self):
        """测试首页未找到链接的情况"""
        mock_http_client = Mock(spec=HttpClient)
        collector = CfmemeCollector(http_client=mock_http_client)

        home_html = "<html><body>No links</body></html>"

        # 现在返回 None 而不是抛出异常
        result = collector.get_today_url(home_html)
        assert result is None

    def test_parse_download_tasks(self):
        """测试解析下载任务"""
        mock_http_client = Mock(spec=HttpClient)
        collector = CfmemeCollector(http_client=mock_http_client)

        today_html = """
        <html>
            <body>
                <div>V2Ray / XRay</div>
                <div>https://example.com/v2ray.txt</div>
                <div>Clash/Mihomo</div>
                <div>https://example.com/clash.yaml</div>
            </body>
        </html>
        """

        tasks = collector.parse_download_tasks(today_html)

        assert len(tasks) == 2
        filenames = [t.filename for t in tasks]
        urls = [t.url for t in tasks]
        assert "clash.yaml" in filenames
        assert "v2ray.txt" in filenames
        assert "https://example.com/clash.yaml" in urls
        assert "https://example.com/v2ray.txt" in urls

    def test_collector_name(self):
        """测试采集器名称"""
        mock_http_client = Mock(spec=HttpClient)
        collector = CfmemeCollector(http_client=mock_http_client)

        assert collector.name == "cfmeme"
        assert collector.home_page == "https://www.cfmem.com"


class TestLa85Collector:
    """La85Collector 测试类"""

    def test_get_today_url(self):
        """测试从首页获取今日链接"""
        mock_http_client = Mock(spec=HttpClient)
        collector = La85Collector(http_client=mock_http_client)

        home_html = """
        <html>
            <body>
                <a href="https://www.85la.com/2026/01/today.html">免费节点 高速节点</a>
            </body>
        </html>
        """

        today_url = collector.get_today_url(home_html)
        assert today_url == "https://www.85la.com/2026/01/today.html"

    def test_get_today_url_not_found(self):
        """测试首页未找到链接的情况"""
        mock_http_client = Mock(spec=HttpClient)
        collector = La85Collector(http_client=mock_http_client)

        home_html = "<html><body>No links</body></html>"

        # 现在返回 None 而不是抛出异常
        result = collector.get_today_url(home_html)
        assert result is None

    def test_parse_download_tasks(self):
        """测试解析下载任务"""
        mock_http_client = Mock(spec=HttpClient)
        collector = La85Collector(http_client=mock_http_client)

        today_html = """
        <html>
            <body>
                <h3>V2ray 订阅地址</h3>
                <a href="https://example.com/v2ray.txt">V2Ray Link</a>
                <h3>Clash.Mihomo 订阅地址</h3>
                <a href="https://example.com/clash.yaml">Clash Link</a>
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
        collector = La85Collector(http_client=mock_http_client)

        assert collector.name == "85la"
        assert collector.home_page == "https://www.85la.com"
