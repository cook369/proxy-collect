"""采集器 Mixin 单元测试（异步版本）"""

import pytest
from unittest.mock import AsyncMock, Mock

from collectors.mixins import (
    TwoStepCollectorMixin,
    HtmlParser,
)
from collectors.base import BaseCollector
from core.exceptions import ParseError
from core.models import DownloadTask, FileManifest, SiteManifest


class TestTwoStepCollectorMixin:
    """TwoStepCollectorMixin 测试类"""

    @pytest.mark.asyncio
    async def test_get_download_tasks_success(self):
        """测试成功的两步采集流程"""

        class TestCollector(TwoStepCollectorMixin):
            name = "test"
            home_page = "http://example.com"

            async def fetch_html(self, url):
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
        tasks = await collector.get_download_tasks()

        assert len(tasks) == 1
        assert tasks[0].filename == "clash.yaml"
        assert tasks[0].url == "http://example.com/clash.yaml"

    @pytest.mark.asyncio
    async def test_get_download_tasks_extracts_title(self):
        """测试从今日页面 <title> 提取采集标题"""

        class TestCollector(TwoStepCollectorMixin):
            name = "test"
            home_page = "http://example.com"

            async def fetch_html(self, url):
                if url == self.home_page:
                    return "<html><body>home</body></html>"
                return "<html><head><title>今日免费节点 2026-06-27</title></head><body>today</body></html>"

            def get_today_url(self, home_html):
                return "http://example.com/today"

            def parse_download_tasks(self, today_html):
                return [
                    DownloadTask(
                        filename="clash.yaml", url="http://example.com/clash.yaml"
                    )
                ]

        collector = TestCollector()
        await collector.get_download_tasks()

        assert collector.title == "今日免费节点 2026-06-27"

    @pytest.mark.asyncio
    async def test_get_download_tasks_title_none_when_absent(self):
        """测试今日页面无 <title> 时 title 为 None，不阻断采集"""

        class TestCollector(TwoStepCollectorMixin):
            name = "test"
            home_page = "http://example.com"

            async def fetch_html(self, url):
                if url == self.home_page:
                    return "<html><body>home</body></html>"
                return "<html><body>no title here</body></html>"

            def get_today_url(self, home_html):
                return "http://example.com/today"

            def parse_download_tasks(self, today_html):
                return [
                    DownloadTask(
                        filename="clash.yaml", url="http://example.com/clash.yaml"
                    )
                ]

        collector = TestCollector()
        tasks = await collector.get_download_tasks()

        assert collector.title is None
        assert len(tasks) == 1

    @pytest.mark.asyncio
    async def test_title_xpath_override_uses_custom_rule(self):
        """测试覆盖 title_xpath 时按站点自定义规则提取标题"""

        class TestCollector(TwoStepCollectorMixin):
            name = "test"
            home_page = "http://example.com"
            title_xpath = "//h1/text()"

            async def fetch_html(self, url):
                if url == self.home_page:
                    return "<html><body>home</body></html>"
                return (
                    "<html><head><title>站点品牌</title></head>"
                    "<body><h1>今日节点 0627</h1></body></html>"
                )

            def get_today_url(self, home_html):
                return "http://example.com/today"

            def parse_download_tasks(self, today_html):
                return [
                    DownloadTask(
                        filename="clash.yaml", url="http://example.com/clash.yaml"
                    )
                ]

        collector = TestCollector()
        await collector.get_download_tasks()

        assert collector.title == "今日节点 0627"

    @pytest.mark.asyncio
    async def test_title_xpath_none_disables_extraction(self):
        """测试 title_xpath=None 时禁用标题提取"""

        class TestCollector(TwoStepCollectorMixin):
            name = "test"
            home_page = "http://example.com"
            title_xpath = None

            async def fetch_html(self, url):
                if url == self.home_page:
                    return "<html><body>home</body></html>"
                return "<html><head><title>有标题但不取</title></head></html>"

            def get_today_url(self, home_html):
                return "http://example.com/today"

            def parse_download_tasks(self, today_html):
                return [
                    DownloadTask(
                        filename="clash.yaml", url="http://example.com/clash.yaml"
                    )
                ]

        collector = TestCollector()
        await collector.get_download_tasks()

        assert collector.title is None

    @pytest.mark.asyncio
    async def test_extract_title_override_custom_logic(self):
        """测试覆盖 extract_title() 实现任意自定义规则"""

        class TestCollector(TwoStepCollectorMixin):
            name = "test"
            home_page = "http://example.com"

            async def fetch_html(self, url):
                if url == self.home_page:
                    return "<html><body>home</body></html>"
                return "<html><head><title>raw - 站点</title></head></html>"

            def extract_title(self, today_html):
                raw = HtmlParser(today_html, self.name).xpath("//title/text()")
                return raw.split(" - ")[0] if raw else None

            def get_today_url(self, home_html):
                return "http://example.com/today"

            def parse_download_tasks(self, today_html):
                return [
                    DownloadTask(
                        filename="clash.yaml", url="http://example.com/clash.yaml"
                    )
                ]

        collector = TestCollector()
        await collector.get_download_tasks()

        assert collector.title == "raw"

    @pytest.mark.asyncio
    async def test_extract_title_failure_does_not_block_collection(self):
        """测试 extract_title 抛异常时 title 为 None 且不阻断采集"""

        class TestCollector(TwoStepCollectorMixin):
            name = "test"
            home_page = "http://example.com"

            async def fetch_html(self, url):
                if url == self.home_page:
                    return "<html><body>home</body></html>"
                return "<html><body>today</body></html>"

            def extract_title(self, today_html):
                raise ValueError("boom")

            def get_today_url(self, home_html):
                return "http://example.com/today"

            def parse_download_tasks(self, today_html):
                return [
                    DownloadTask(
                        filename="clash.yaml", url="http://example.com/clash.yaml"
                    )
                ]

        collector = TestCollector()
        tasks = await collector.get_download_tasks()

        assert collector.title is None
        assert len(tasks) == 1

    @pytest.mark.asyncio
    async def test_get_download_tasks_no_today_url(self):
        """测试未找到今日链接的情况"""

        class TestCollector(TwoStepCollectorMixin):
            name = "test"
            home_page = "http://example.com"

            async def fetch_html(self, url):
                return "<html>home</html>"

            def get_today_url(self, home_html):
                return None

            def parse_download_tasks(self, today_html):
                return []

        collector = TestCollector()

        with pytest.raises(ParseError, match="No today URL found"):
            await collector.get_download_tasks()

    @pytest.mark.asyncio
    async def test_run_skips_cached_today_page_before_fetching_today_html(
        self, tmp_path, monkeypatch
    ):
        """测试通用缓存跳过在获取今日页面前生效"""
        today_url = "http://example.com/today"
        site_dir = tmp_path / "test_cached"
        site_dir.mkdir()
        (site_dir / "clash.yaml").write_text(
            "proxies:\n  - name: test\n", encoding="utf-8"
        )

        class FakeManifest:
            sites = {
                "test_cached": SiteManifest(
                    today_page=today_url,
                    status="success",
                    updated_at="2026-05-18 12:00:00",
                    files={
                        "clash.yaml": FileManifest(
                            url="http://example.com/clash.yaml", success=True
                        )
                    },
                )
            }

            def __init__(self, manifest_file):
                pass

            def get_site(self, site):
                return self.sites.get(site)

        class TestCollector(TwoStepCollectorMixin, BaseCollector):
            name = "test_cached"
            home_page = "http://example.com"

            async def fetch_html(self, url):
                if url == today_url:
                    raise AssertionError("today page should be skipped")
                return "<html>home</html>"

            def get_today_url(self, home_html):
                return today_url

            def parse_download_tasks(self, today_html):
                raise AssertionError("tasks should be skipped")

        monkeypatch.setattr("services.manifest_service.ManifestService", FakeManifest)

        result = await TestCollector().run(tmp_path)

        assert result.status == "success"
        assert result.today_page == today_url
        assert result.from_cache is True


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
