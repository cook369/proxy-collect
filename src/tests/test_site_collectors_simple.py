"""简单采集器测试 - Datia 和 Jichangx"""

from unittest.mock import Mock, patch

from collectors.sites.datia import DatiaCollector
from collectors.sites.jichangx import JichangxCollector
from core.interfaces import HttpClient


class TestDatiaCollector:
    """DatiaCollector 测试类"""

    def test_get_today_url(self):
        """测试从首页获取今日链接"""
        mock_http_client = Mock(spec=HttpClient)
        collector = DatiaCollector(http_client=mock_http_client)

        home_html = """
        <html>
            <body>
                <a href="/2026/01/today.html">高速免费节点</a>
            </body>
        </html>
        """

        today_url = collector.get_today_url(home_html)
        assert today_url == "https://free.datiya.com/2026/01/today.html"

    def test_get_today_url_not_found(self):
        """测试首页未找到链接的情况"""
        mock_http_client = Mock(spec=HttpClient)
        collector = DatiaCollector(http_client=mock_http_client)

        home_html = "<html><body>No links</body></html>"

        result = collector.get_today_url(home_html)
        assert result is None

    def test_parse_download_tasks(self):
        """测试解析下载任务"""
        mock_http_client = Mock(spec=HttpClient)
        collector = DatiaCollector(http_client=mock_http_client)

        today_html = """
        <html>
            <body>
                <ol>V2ray配置</ol>
                <pre>https://example.com/v2ray.txt</pre>
                <ol>Clash配置</ol>
                <pre>https://example.com/clash.yaml</pre>
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
        collector = DatiaCollector(http_client=mock_http_client)

        assert collector.name == "datiya"
        assert collector.home_page == "https://free.datiya.com"


class TestJichangxCollector:
    """JichangxCollector 测试类"""

    @patch("collectors.sites.jichangx.datetime")
    def test_get_download_tasks(self, mock_datetime):
        """测试获取下载任务"""
        # 模拟日期为 2026-01-29
        mock_now = Mock()
        mock_now.strftime.return_value = "20260129"
        mock_datetime.now.return_value = mock_now

        mock_http_client = Mock(spec=HttpClient)
        collector = JichangxCollector(http_client=mock_http_client)

        tasks = collector.get_download_tasks()

        assert len(tasks) == 1
        assert tasks[0].filename == "v2ray.txt"
        assert tasks[0].url == "https://jichangx.com/nodes/v2ray-20260129-01"

    def test_collector_name(self):
        """测试采集器名称"""
        mock_http_client = Mock(spec=HttpClient)
        collector = JichangxCollector(http_client=mock_http_client)

        assert collector.name == "jichangx"
        assert collector.home_page == "https://jichangx.com"
