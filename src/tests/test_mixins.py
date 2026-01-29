"""采集器 Mixin 单元测试"""
import pytest
from datetime import datetime
from unittest.mock import Mock, patch

from collectors.mixins import TwoStepCollectorMixin, XPathParserMixin, DateBasedUrlMixin
from core.exceptions import ParseError


class TestTwoStepCollectorMixin:
    """TwoStepCollectorMixin 测试类"""

    def test_get_download_urls_success(self):
        """测试成功的两步采集流程"""
        # 创建测试类
        class TestCollector(TwoStepCollectorMixin):
            name = "test"
            home_page = "http://example.com"

            def fetch_html(self, url):
                if url == self.home_page:
                    return "<html>home</html>"
                return "<html>today</html>"

            def get_today_url(self, home_html):
                return "http://example.com/today"

            def parse_download_urls(self, today_html):
                return [("clash.yaml", "http://example.com/clash.yaml")]

        collector = TestCollector()
        urls = collector.get_download_urls()

        assert len(urls) == 1
        assert urls[0] == ("clash.yaml", "http://example.com/clash.yaml")

    def test_get_download_urls_no_today_url(self):
        """测试未找到今日链接的情况"""
        class TestCollector(TwoStepCollectorMixin):
            name = "test"
            home_page = "http://example.com"

            def fetch_html(self, url):
                return "<html>home</html>"

            def get_today_url(self, home_html):
                return None

            def parse_download_urls(self, today_html):
                return []

        collector = TestCollector()

        with pytest.raises(ParseError, match="No today URL found"):
            collector.get_download_urls()


class TestXPathParserMixin:
    """XPathParserMixin 测试类"""

    def test_parse_with_xpath_success(self):
        """测试成功的 XPath 解析"""
        class TestCollector(XPathParserMixin):
            name = "test"

        collector = TestCollector()
        html = """
        <html>
            <a id="clash" href="http://example.com/clash.yaml">Clash</a>
            <a id="v2ray" href="http://example.com/v2ray.txt">V2Ray</a>
        </html>
        """

        rules = {
            "clash.yaml": '//a[@id="clash"]/@href',
            "v2ray.txt": '//a[@id="v2ray"]/@href'
        }

        urls = collector.parse_with_xpath(html, rules)

        assert len(urls) == 2
        assert ("clash.yaml", "http://example.com/clash.yaml") in urls
        assert ("v2ray.txt", "http://example.com/v2ray.txt") in urls

    def test_parse_with_xpath_not_found(self):
        """测试 XPath 未找到元素的情况"""
        class TestCollector(XPathParserMixin):
            name = "test"

        collector = TestCollector()
        html = "<html><body>No links</body></html>"

        rules = {
            "clash.yaml": '//a[@id="clash"]/@href'
        }

        urls = collector.parse_with_xpath(html, rules)

        assert urls == []

    def test_parse_with_xpath_invalid_xpath(self):
        """测试无效的 XPath 表达式"""
        class TestCollector(XPathParserMixin):
            name = "test"

        collector = TestCollector()
        html = "<html><body>Test</body></html>"

        rules = {
            "clash.yaml": '//invalid[[[xpath'
        }

        # 应该捕获异常并返回空列表
        urls = collector.parse_with_xpath(html, rules)

        assert urls == []


class TestDateBasedUrlMixin:
    """DateBasedUrlMixin 测试类"""

    @patch('collectors.mixins.datetime')
    def test_build_date_urls(self, mock_datetime):
        """测试基于日期的 URL 构建"""
        # 模拟当前日期
        mock_now = Mock()
        mock_now.strftime.return_value = "20260129"
        mock_datetime.now.return_value = mock_now

        class TestCollector(DateBasedUrlMixin):
            name = "test"

        collector = TestCollector()

        urls = collector.build_date_urls(
            base_url="http://example.com",
            date_format="%Y%m%d",
            extensions={
                "clash.yaml": ".yaml",
                "v2ray.txt": ".txt"
            }
        )

        assert len(urls) == 2
        assert ("clash.yaml", "http://example.com/20260129.yaml") in urls
        assert ("v2ray.txt", "http://example.com/20260129.txt") in urls

    @patch('collectors.mixins.datetime')
    def test_build_date_urls_different_format(self, mock_datetime):
        """测试不同的日期格式"""
        mock_now = Mock()
        mock_now.strftime.return_value = "2026-01-29"
        mock_datetime.now.return_value = mock_now

        class TestCollector(DateBasedUrlMixin):
            name = "test"

        collector = TestCollector()

        urls = collector.build_date_urls(
            base_url="http://example.com",
            date_format="%Y-%m-%d",
            extensions={"clash.yaml": ".yaml"}
        )

        assert len(urls) == 1
        assert urls[0] == ("clash.yaml", "http://example.com/2026-01-29.yaml")
