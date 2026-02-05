"""采集器通用 Mixin

提取采集器中的通用模式，消除重复代码。
"""

from datetime import datetime
from lxml import etree
import logging
from typing import Optional

from core.exceptions import ParseError
from core.models import DownloadTask


def safe_xpath(
    html: str,
    xpath_expr: str,
    collector_name: str | None = None,
    default: str | None = None,
) -> str | None:
    """安全执行 XPath 查询

    Args:
        html: HTML 内容
        xpath_expr: XPath 表达式
        collector_name: 采集器名称（用于日志）
        default: 默认值

    Returns:
        查询结果或默认值
    """
    try:
        tree = etree.HTML(html)
        if tree is None:
            logging.warning(f"[{collector_name}] Failed to parse HTML")
            return default

        result = tree.xpath(xpath_expr)
        if not result:
            return default

        # 处理不同类型的返回值
        if isinstance(result, list):
            return result[0] if result else default
        return str(result) if result else default

    except etree.XPathError as e:
        logging.warning(f"[{collector_name}] Invalid XPath '{xpath_expr}': {e}")
        return default
    except Exception as e:
        logging.warning(f"[{collector_name}] XPath query failed: {e}")
        return default


def safe_xpath_all(
    html: str,
    xpath_expr: str,
    collector_name: str | None = None,
) -> list:
    """安全执行 XPath 查询，返回所有匹配结果

    Args:
        html: HTML 内容
        xpath_expr: XPath 表达式
        collector_name: 采集器名称（用于日志）

    Returns:
        查询结果列表（失败时返回空列表）
    """
    try:
        tree = etree.HTML(html)
        if tree is None:
            logging.warning(f"[{collector_name}] Failed to parse HTML")
            return []

        return tree.xpath(xpath_expr) or []

    except etree.XPathError as e:
        logging.warning(f"[{collector_name}] Invalid XPath '{xpath_expr}': {e}")
        return []
    except Exception as e:
        logging.warning(f"[{collector_name}] XPath query failed: {e}")
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


class DateBasedUrlMixin:
    """基于日期的 URL 构建 Mixin

    适用于 URL 中包含日期的采集器。
    """

    def build_date_tasks(
        self, base_url: str, date_format: str, extensions: dict[str, str]
    ) -> list[DownloadTask]:
        """构建基于日期的下载任务

        Args:
            base_url: 基础 URL
            date_format: 日期格式（strftime 格式）
            extensions: 文件扩展名字典 {文件名: 扩展名}

        Returns:
            DownloadTask 列表
        """
        date_str = datetime.now().strftime(date_format)

        return [
            DownloadTask(filename=filename, url=f"{base_url}/{date_str}{ext}")
            for filename, ext in extensions.items()
        ]
