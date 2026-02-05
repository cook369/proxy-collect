"""采集器通用 Mixin

提取采集器中的通用模式，消除重复代码。
"""

from lxml import etree
import logging
from typing import Optional

from core.exceptions import ParseError
from core.models import DownloadTask


class HtmlParser:
    """HTML 解析器，缓存解析树避免重复解析

    当需要对同一 HTML 执行多次 XPath 查询时，使用此类可以提高性能。

    Example:
        parser = HtmlParser(html, "collector_name")
        url1 = parser.xpath('//a/@href')
        url2 = parser.xpath('//div/@class')
    """

    def __init__(self, html: str, collector_name: str | None = None):
        """初始化解析器

        Args:
            html: HTML 内容
            collector_name: 采集器名称（用于日志）
        """
        self.collector_name = collector_name
        self._tree = None
        try:
            self._tree = etree.HTML(html)
        except Exception as e:
            logging.warning(f"[{collector_name}] Failed to parse HTML: {e}")

    def xpath(self, xpath_expr: str, default: str | None = None) -> str | None:
        """执行 XPath 查询，返回第一个匹配结果

        Args:
            xpath_expr: XPath 表达式
            default: 默认值

        Returns:
            查询结果或默认值
        """
        if self._tree is None:
            return default

        try:
            result = self._tree.xpath(xpath_expr)
            if not result:
                return default
            if isinstance(result, list):
                return result[0] if result else default
            return str(result) if result else default
        except etree.XPathError as e:
            logging.warning(
                f"[{self.collector_name}] Invalid XPath '{xpath_expr}': {e}"
            )
            return default
        except Exception as e:
            logging.warning(f"[{self.collector_name}] XPath query failed: {e}")
            return default

    def xpath_all(self, xpath_expr: str) -> list:
        """执行 XPath 查询，返回所有匹配结果

        Args:
            xpath_expr: XPath 表达式

        Returns:
            查询结果列表（失败时返回空列表）
        """
        if self._tree is None:
            return []

        try:
            return self._tree.xpath(xpath_expr) or []
        except etree.XPathError as e:
            logging.warning(
                f"[{self.collector_name}] Invalid XPath '{xpath_expr}': {e}"
            )
            return []
        except Exception as e:
            logging.warning(f"[{self.collector_name}] XPath query failed: {e}")
            return []


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

    def parse_download_tasks(self, today_html: str) -> list[DownloadTask]:
        """从今日页面解析下载任务（子类实现）

        Args:
            today_html: 今日页面 HTML 内容

        Returns:
            DownloadTask 列表
        """
        raise NotImplementedError

    def get_download_tasks(self) -> list[DownloadTask]:
        """两步采集流程

        Returns:
            DownloadTask 列表

        Raises:
            ParseError: 无法获取今日链接或解析失败
        """
        collector_name = getattr(self, "name", "unknown")

        # 步骤1：获取首页
        home_html = self.fetch_html(self.home_page)

        # 步骤2：获取今日链接（带错误处理）
        try:
            today_url = self.get_today_url(home_html)
        except NotImplementedError:
            raise
        except Exception as e:
            raise ParseError(
                f"Failed to get today URL: {e}",
                self.home_page,
                collector_name,
            ) from e

        if not today_url:
            raise ParseError(
                "No today URL found on homepage",
                self.home_page,
                collector_name,
            )

        # 保存今日页面 URL
        self.today_page = today_url
        logging.info(f"[{collector_name}] Today URL: {today_url}")

        # 步骤3：获取今日页面
        today_html = self.fetch_html(today_url)

        # 步骤4：解析下载任务（带错误处理）
        try:
            tasks = self.parse_download_tasks(today_html)
        except NotImplementedError:
            raise
        except Exception as e:
            raise ParseError(
                f"Failed to parse download tasks: {e}",
                today_url,
                collector_name,
            ) from e

        if not tasks:
            logging.warning(f"[{collector_name}] No download tasks found on today page")

        return tasks
