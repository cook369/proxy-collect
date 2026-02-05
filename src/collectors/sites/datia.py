"""Datia 采集器"""

from typing import Optional
from collectors.base import BaseCollector, register_collector
from collectors.mixins import TwoStepCollectorMixin, HtmlParser
from core.models import DownloadTask


@register_collector
class DatiaCollector(TwoStepCollectorMixin, BaseCollector):
    """Datia 站点采集器"""

    name = "datiya"
    home_page = "https://free.datiya.com"

    def get_today_url(self, home_html: str) -> Optional[str]:
        """从首页获取今日链接"""
        parser = HtmlParser(home_html, self.name)
        path = parser.xpath('//a[text()[contains(., "高速免费节点")]]/@href')
        return self.home_page + path if path else None

    def parse_download_tasks(self, today_html: str) -> list[DownloadTask]:
        """从今日页面解析下载任务"""
        parser = HtmlParser(today_html, self.name)
        rules = {
            "v2ray.txt": 'string(//ol[contains(., "V2ray配置")]/following-sibling::pre[1])',
            "clash.yaml": 'string(//ol[contains(., "Clash配置")]/following-sibling::pre[1])',
        }

        tasks: list[DownloadTask] = []
        for filename, xpath_expr in rules.items():
            url = parser.xpath(xpath_expr)
            if url and url.strip():
                tasks.append(DownloadTask(filename=filename, url=url.strip()))

        return tasks
