"""CFMem 采集器"""

from typing import Optional

from collectors.base import BaseCollector, register_collector
from collectors.mixins import TwoStepCollectorMixin, HtmlParser
from core.models import DownloadTask
from utils.extractors import create_regex_extractor


# CFMem clash.yaml 内容提取器
CLASH_EXTRACTOR = create_regex_extractor(
    pattern=r'(?<=")mixed-port.*rule-providers(.*?)(?=")',
    unescape=True,
)


@register_collector
class CfmemeCollector(TwoStepCollectorMixin, BaseCollector):
    """CFMem 站点采集器"""

    name = "cfmeme"
    home_page = "https://www.cfmem.com"

    def get_today_url(self, home_html: str) -> Optional[str]:
        """从首页获取今日链接"""
        parser = HtmlParser(home_html, self.name)
        return parser.xpath('(//a[text()[contains(., "免费节点")]]/@href)[2]')

    def parse_download_tasks(self, today_html: str) -> list[DownloadTask]:
        """从今日页面解析下载任务"""
        parser = HtmlParser(today_html, self.name)
        rules = {
            "v2ray.txt": 'string(//a[text()[contains(., "V2Ray 订阅链接")]]/@href[1])',
            "clash.yaml": 'string(//a[text()[contains(., "Clash 订阅链接")]]/@href[1])',
        }

        tasks: list[DownloadTask] = []
        for filename, xpath_expr in rules.items():
            url = parser.xpath(xpath_expr)
            if url and url.strip():
                # clash.yaml 需要特殊处理
                processor = CLASH_EXTRACTOR if filename == "clash.yaml" else None
                tasks.append(
                    DownloadTask(
                        filename=filename,
                        url=url.strip(),
                        processor=processor,
                    )
                )

        return tasks
