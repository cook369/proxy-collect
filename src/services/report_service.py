"""报告生成服务

生成采集报告和更新 README。
"""
import datetime
from pathlib import Path
from tabulate import tabulate

from core.models import CollectorResult


class ReportService:
    """报告生成服务"""

    def generate(self, results: list[CollectorResult]) -> str:
        """生成报告内容

        Args:
            results: 采集结果列表

        Returns:
            报告内容
        """
        report_lines = []
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        report_lines.append(f"\n# Collect Time: {now}\n")

        for r in results:
            report_lines.append(f"\n## Site: {r.site}\n")
            table = []
            for url in r.all_urls:
                status = r.url_status.get(url)
                tried = "Yes" if url in r.tried_urls else "No"
                success = "Yes" if status else "No"
                table.append([url, tried, success])

            headers = ["URL", "Tried", "Success"]
            report_lines.append(tabulate(table, headers, tablefmt="github"))
            report_lines.append(
                f"\n采集成功: {len(r.success_urls)} / 采集失败: {len(r.failed_urls)}\n"
            )

        return "\n".join(report_lines)

    def save(self, content: str, file_path: Path):
        """保存报告到文件

        Args:
            content: 报告内容
            file_path: 文件路径
        """
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")

    def print_report(self, content: str):
        """打印报告到控制台

        Args:
            content: 报告内容
        """
        print(content)
