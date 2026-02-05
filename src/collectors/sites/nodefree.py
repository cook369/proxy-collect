"""NodeFree 采集器"""

from typing import Optional
from collectors.base import BaseCollector, register_collector
from collectors.mixins import TwoStepCollectorMixin, safe_xpath, safe_xpath_all
from core.models import DownloadTask


@register_collector
class NodefreeCollector(TwoStepCollectorMixin, BaseCollector):
    """NodeFree 站点采集器"""

    name = "nodefree"
    home_page = "https://nodefree.me"

    def get_today_url(self, home_html: str) -> Optional[str]:
        """从首页获取今日链接"""
        links = safe_xpath_all(
            home_html,
            '//a[text()[contains(., "订阅链接免费节点")]]/@href',
            self.name,
        )
        if not links:
            return None
        return links[0]

    def parse_download_tasks(self, today_html: str) -> list[DownloadTask]:
        """从今日页面解析下载任务"""
        rules = {
            "v2ray.txt": 'string(//h2[contains(., "v2ray订阅链接")]/following-sibling::p[1])',
            "clash.yaml": 'string(//h2[contains(., "clash订阅链接")]/following-sibling::p[1])',
        }

        tasks: list[DownloadTask] = []
        for filename, xpath_expr in rules.items():
            url = safe_xpath(today_html, xpath_expr, self.name)
            if url and url.strip():
                tasks.append(DownloadTask(filename=filename, url=url.strip()))

        return tasks
