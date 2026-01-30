"""两步采集器测试 - CFMem 和 La85"""
import pytest
from unittest.mock import Mock

from collectors.sites.cfmem import CfmemCollector
from collectors.sites.la85 import La85Collector
from core.interfaces import HttpClient


class TestCfmemCollector:
    """CfmemCollector 测试类"""

    def test_get_today_url(self):
        """测试从首页获取今日链接"""
        mock_http_client = Mock(spec=HttpClient)
        collector = CfmemCollector(http_client=mock_http_client)

        home_html = """
        <html>
            <div id="Blog1">
                <div>
                    <article>
                        <div>
                            <h2><a href="https://www.cfmem.com/2026/01/today.html">Today's Post</a></h2>
                        </div>
                    </article>
                </div>
            </div>
        </html>
        """

        today_url = collector.get_today_url(home_html)
        assert today_url == "https://www.cfmem.com/2026/01/today.html"

    def test_get_today_url_not_found(self):
        """测试首页未找到链接的情况"""
        mock_http_client = Mock(spec=HttpClient)
        collector = CfmemCollector(http_client=mock_http_client)

        home_html = "<html><body>No links</body></html>"

        with pytest.raises(ValueError, match="No links found on homepage"):
            collector.get_today_url(home_html)

    def test_parse_download_urls(self):
        """测试解析下载链接"""
        mock_http_client = Mock(spec=HttpClient)
        collector = CfmemCollector(http_client=mock_http_client)

        today_html = """
        <html>
            <div id="post-body">
                <div>
                    <div></div>
                    <div></div>
                    <div></div>
                    <div>
                        <div><span>https://example.com/v2ray.txt</span></div>
                        <div><span>https://example.com/clash.yaml</span></div>
                    </div>
                </div>
            </div>
        </html>
        """

        urls = collector.parse_download_urls(today_html)

        assert len(urls) == 2
        assert ("clash.yaml", "https://example.com/clash.yaml") in urls
        assert ("v2ray.txt", "https://example.com/v2ray.txt") in urls

    def test_collector_name(self):
        """测试采集器名称"""
        mock_http_client = Mock(spec=HttpClient)
        collector = CfmemCollector(http_client=mock_http_client)

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

        with pytest.raises(ValueError, match="No links found on homepage"):
            collector.get_today_url(home_html)

    def test_parse_download_urls(self):
        """测试解析下载链接"""
        mock_http_client = Mock(spec=HttpClient)
        collector = La85Collector(http_client=mock_http_client)

        today_html = """
        <html>
            <body>
                <h3>V2ray 订阅地址</h3>
                <a href="https://example.com/v2ray.txt">V2Ray Link</a>
                <h3>Clash.meta 订阅地址</h3>
                <a href="https://example.com/clash.yaml">Clash Link</a>
            </body>
        </html>
        """

        urls = collector.parse_download_urls(today_html)

        assert len(urls) == 2
        assert ("v2ray.txt", "https://example.com/v2ray.txt") in urls
        assert ("clash.yaml", "https://example.com/clash.yaml") in urls

    def test_collector_name(self):
        """测试采集器名称"""
        mock_http_client = Mock(spec=HttpClient)
        collector = La85Collector(http_client=mock_http_client)

        assert collector.name == "85la"
        assert collector.home_page == "https://www.85la.com"
