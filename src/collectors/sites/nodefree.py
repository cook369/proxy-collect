"""NodeFree 采集器"""

from typing import Optional
from collectors.base import BaseCollector, register_collector
from collectors.mixins import TwoStepCollectorMixin, HtmlParser
from core.models import DownloadTask


@register_collector
class NodefreeCollector(TwoStepCollectorMixin, BaseCollector):
    """NodeFree 站点采集器"""

    name = "nodefree"
    home_page = "https://nodefree.me"

    def get_today_url(self, home_html: str) -> Optional[str]:
        """从首页获取今日链接"""
        parser = HtmlParser(home_html, self.name)
        return parser.xpath('//a[text()[contains(., "订阅链接免费节点")]]/@href')

    def parse_download_tasks(self, today_html: str) -> list[DownloadTask]:
        """从今日页面解析下载任务"""
        parser = HtmlParser(today_html, self.name)
        rules = {
            "v2ray.txt": 'string(//h2[contains(., "v2ray订阅链接")]/following-sibling::p[1])',
            "clash.yaml": 'string(//h2[contains(., "clash订阅链接")]/following-sibling::p[1])',
        }

        tasks: list[DownloadTask] = []
        for filename, xpath_expr in rules.items():
            url = parser.xpath(xpath_expr)
            if url and url.strip():
                tasks.append(DownloadTask(filename=filename, url=url.strip()))

        return tasks
