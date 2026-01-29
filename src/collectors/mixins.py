"""采集器通用 Mixin

提取采集器中的通用模式，消除重复代码。
"""

from datetime import datetime
from lxml import etree
import logging
from typing import Optional

from core.exceptions import ParseError


class TwoStepCollectorMixin:
    """两步采集 Mixin：首页 -> 今日页面 -> 下载链接

    适用于需要先访问首页获取今日链接，再访问今日页面获取下载链接的采集器。
    """

    today_page: str | None = None  # 保存今日页面 URL

    def get_today_url(self, home_html: str) -> Optional[str]:
        """从首页获取今日链接（子类实现）

        Args:
            home_html: 首页 HTML 内容

        Returns:
            今日页面 URL，如果未找到返回 None
        """
        raise NotImplementedError

    def parse_download_urls(self, today_html: str) -> list[tuple[str, str]]:
        """从今日页面解析下载链接（子类实现）

        Args:
            today_html: 今日页面 HTML 内容

        Returns:
            (文件名, URL) 元组列表
        """
        raise NotImplementedError

    def get_download_urls(self) -> list[tuple[str, str]]:
        """两步采集流程

        Returns:
            (文件名, URL) 元组列表

        Raises:
            ParseError: 无法获取今日链接
        """
        # 步骤1：获取首页
        home_html = self.fetch_html(self.home_page)

        # 步骤2：获取今日链接
        today_url = self.get_today_url(home_html)
        if not today_url:
            raise ParseError(
                "No today URL found on homepage",
                self.home_page,
                getattr(self, "name", None),
            )

        # 保存今日页面 URL
        self.today_page = today_url
        logging.info(f"[{self.name}] Today URL: {today_url}")

        # 步骤3：获取今日页面
        today_html = self.fetch_html(today_url)

        # 步骤4：解析下载链接
        return self.parse_download_urls(today_html)


class XPathParserMixin:
    """XPath 解析 Mixin

    提供通用的 XPath 解析功能。
    """

    def parse_with_xpath(
        self, html: str, rules: dict[str, str]
    ) -> list[tuple[str, str]]:
        """使用 XPath 规则解析 HTML

        Args:
            html: HTML 内容
            rules: 解析规则字典 {文件名: XPath 表达式}

        Returns:
            (文件名, URL) 元组列表

        Raises:
            ParseError: XPath 解析失败
        """
        try:
            tree = etree.HTML(html)
        except Exception as e:
            raise ParseError(
                f"Failed to parse HTML: {e}",
                collector_name=getattr(self, "name", None),
            ) from e

        results = []
        for filename, xpath_expr in rules.items():
            try:
                hrefs = tree.xpath(xpath_expr)
                if hrefs:
                    results.append((filename, hrefs[0]))
            except Exception as e:
                logging.warning(
                    f"[{getattr(self, 'name', 'unknown')}] "
                    f"XPath failed for {filename}: {e}"
                )

        return results


class DateBasedUrlMixin:
    """基于日期的 URL 构建 Mixin

    适用于 URL 中包含日期的采集器。
    """

    def build_date_urls(
        self, base_url: str, date_format: str, extensions: dict[str, str]
    ) -> list[tuple[str, str]]:
        """构建基于日期的 URL

        Args:
            base_url: 基础 URL
            date_format: 日期格式（strftime 格式）
            extensions: 文件扩展名字典 {文件名: 扩展名}

        Returns:
            (文件名, URL) 元组列表
        """
        date_str = datetime.now().strftime(date_format)

        return [
            (filename, f"{base_url}/{date_str}{ext}")
            for filename, ext in extensions.items()
        ]
