"""采集器 Mixin 单元测试"""

import pytest
from unittest.mock import Mock, patch

from collectors.mixins import (
    TwoStepCollectorMixin,
    DateBasedUrlMixin,
    safe_xpath,
    safe_xpath_all,
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


class TestSafeXpath:
    """safe_xpath 函数测试类"""

    def test_safe_xpath_success(self):
        """测试成功的 XPath 查询"""
        html = '<html><a href="http://example.com">Link</a></html>'
        result = safe_xpath(html, "//a/@href", "test")
        assert result == "http://example.com"

    def test_safe_xpath_not_found(self):
        """测试未找到元素返回默认值"""
        html = "<html><body>No links</body></html>"
        result = safe_xpath(html, "//a/@href", "test", default="default")
        assert result == "default"

    def test_safe_xpath_invalid_xpath(self):
        """测试无效的 XPath 表达式返回默认值"""
        html = "<html><body>Test</body></html>"
        result = safe_xpath(html, "//invalid[[[xpath", "test", default="default")
        assert result == "default"

    def test_safe_xpath_string_function(self):
        """测试 string() 函数"""
        html = '<html><p id="test">Hello World</p></html>'
        result = safe_xpath(html, 'string(//p[@id="test"])', "test")
        assert result == "Hello World"


class TestSafeXpathAll:
    """safe_xpath_all 函数测试类"""

    def test_safe_xpath_all_success(self):
        """测试成功的 XPath 查询返回列表"""
        html = """
        <html>
            <a href="http://example.com/1">Link1</a>
            <a href="http://example.com/2">Link2</a>
        </html>
        """
        result = safe_xpath_all(html, "//a/@href", "test")
        assert len(result) == 2
        assert "http://example.com/1" in result
        assert "http://example.com/2" in result

    def test_safe_xpath_all_not_found(self):
        """测试未找到元素返回空列表"""
        html = "<html><body>No links</body></html>"
        result = safe_xpath_all(html, "//a/@href", "test")
        assert result == []

    def test_safe_xpath_all_invalid_xpath(self):
        """测试无效的 XPath 表达式返回空列表"""
        html = "<html><body>Test</body></html>"
        result = safe_xpath_all(html, "//invalid[[[xpath", "test")
        assert result == []


class TestDateBasedUrlMixin:
    """DateBasedUrlMixin 测试类"""

    @patch("collectors.mixins.datetime")
    def test_build_date_tasks(self, mock_datetime):
        """测试基于日期的下载任务构建"""
        # 模拟当前日期
        mock_now = Mock()
        mock_now.strftime.return_value = "20260129"
        mock_datetime.now.return_value = mock_now

        class TestCollector(DateBasedUrlMixin):
            name = "test"

        collector = TestCollector()

        tasks = collector.build_date_tasks(
            base_url="http://example.com",
            date_format="%Y%m%d",
            extensions={"clash.yaml": ".yaml", "v2ray.txt": ".txt"},
        )

        assert len(tasks) == 2
        filenames = [t.filename for t in tasks]
        urls = [t.url for t in tasks]
        assert "clash.yaml" in filenames
        assert "v2ray.txt" in filenames
        assert "http://example.com/20260129.yaml" in urls
        assert "http://example.com/20260129.txt" in urls

    @patch("collectors.mixins.datetime")
    def test_build_date_tasks_different_format(self, mock_datetime):
        """测试不同的日期格式"""
        mock_now = Mock()
        mock_now.strftime.return_value = "2026-01-29"
        mock_datetime.now.return_value = mock_now

        class TestCollector(DateBasedUrlMixin):
            name = "test"

        collector = TestCollector()

        tasks = collector.build_date_tasks(
            base_url="http://example.com",
            date_format="%Y-%m-%d",
            extensions={"clash.yaml": ".yaml"},
        )

        assert len(tasks) == 1
        assert tasks[0].filename == "clash.yaml"
        assert tasks[0].url == "http://example.com/2026-01-29.yaml"
