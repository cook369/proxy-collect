"""采集器 Mixin 单元测试"""

import pytest

from collectors.mixins import (
    TwoStepCollectorMixin,
    HtmlParser,
)
from core.exceptions import ParseError
from core.models import DownloadTask


class TestTwoStepCollectorMixin:
    """TwoStepCollectorMixin 测试类"""

    def test_get_download_tasks_success(self):
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

            def parse_download_tasks(self, today_html):
                return [
                    DownloadTask(
                        filename="clash.yaml", url="http://example.com/clash.yaml"
                    )
                ]

        collector = TestCollector()
        tasks = collector.get_download_tasks()

        assert len(tasks) == 1
        assert tasks[0].filename == "clash.yaml"
        assert tasks[0].url == "http://example.com/clash.yaml"

    def test_get_download_tasks_no_today_url(self):
        """测试未找到今日链接的情况"""

        class TestCollector(TwoStepCollectorMixin):
            name = "test"
            home_page = "http://example.com"

            def fetch_html(self, url):
                return "<html>home</html>"

            def get_today_url(self, home_html):
                return None

            def parse_download_tasks(self, today_html):
                return []

        collector = TestCollector()

        with pytest.raises(ParseError, match="No today URL found"):
            collector.get_download_tasks()


class TestHtmlParser:
    """HtmlParser 测试类"""

    def test_xpath_success(self):
        """测试成功的 XPath 查询"""
        html = '<html><a href="http://example.com">Link</a></html>'
        parser = HtmlParser(html, "test")
        result = parser.xpath("//a/@href")
        assert result == "http://example.com"

    def test_xpath_not_found(self):
        """测试未找到元素返回默认值"""
        html = "<html><body>No links</body></html>"
        parser = HtmlParser(html, "test")
        result = parser.xpath("//a/@href", default="default")
        assert result == "default"

    def test_xpath_all_success(self):
        """测试 xpath_all 返回所有匹配结果"""
        html = """
        <html>
            <a href="http://example.com/1">Link1</a>
            <a href="http://example.com/2">Link2</a>
        </html>
        """
        parser = HtmlParser(html, "test")
        result = parser.xpath_all("//a/@href")
        assert len(result) == 2
        assert "http://example.com/1" in result
        assert "http://example.com/2" in result

    def test_multiple_queries_same_parser(self):
        """测试同一解析器多次查询（验证缓存）"""
        html = '<html><a href="url1">Link</a><div class="test">Content</div></html>'
        parser = HtmlParser(html, "test")
        url = parser.xpath("//a/@href")
        cls = parser.xpath("//div/@class")
        assert url == "url1"
        assert cls == "test"

    def test_invalid_html(self):
        """测试无效 HTML 返回默认值"""
        parser = HtmlParser(None, "test")
        result = parser.xpath("//a/@href", default="default")
        assert result == "default"
        result_all = parser.xpath_all("//a/@href")
        assert result_all == []
