"""主入口 - 简化版本

使用服务层和配置模块，保持命令行接口不变。
"""
import argparse
import logging
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# 导入配置
from config.settings import Config

# 导入核心模型
from core.models import CollectorResult

# 导入服务
from services.http_service import HttpService, ProxyPool, ProxyHttpService
from services.proxy_service import ProxyValidator, ProxyService
from services.record_service import RecordService
from services.report_service import ReportService

# 导入采集器
from collectors.base import get_collector, list_collectors


# 初始化配置
config = Config()

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)


def run_collector(
    collector_name: str,
    proxy_list: list[str],
    output_dir: Path,
    record: RecordService
) -> CollectorResult:
    """运行单个采集器"""
    collector_cls = get_collector(collector_name)
    collector = collector_cls(proxy_list, record_storage=record)
    return collector.run(output_dir)


def update_readme(
    output_dir: Path,
    readme_file: Path,
    github_prefix: str
):
    """更新 README.md 中每日更新订阅部分"""
    sites = [d.name for d in output_dir.iterdir() if d.is_dir()]

    # 构建每日更新订阅内容
    lines = ["\n## 每日更新订阅\n"]

    for site in sorted(sites):
        site_dir = output_dir / site
        clash_path = site_dir / "clash.yaml"
        v2ray_path = site_dir / "v2ray.txt"

        lines.append(f"### {site} 订阅链接\n")

        if clash_path.exists():
            lines.append("```shell")
            lines.append(
                f"{github_prefix}/https://raw.githubusercontent.com/cook369/proxy-collect/main/dist/{site}/clash.yaml"
            )
            lines.append("```")

        if v2ray_path.exists():
            lines.append("```shell")
            lines.append(
                f"{github_prefix}/https://raw.githubusercontent.com/cook369/proxy-collect/main/dist/{site}/v2ray.txt"
            )
            lines.append("```")

    lines.append("\n---\n")

    # 读取原 README 内容
    if readme_file.exists():
        content = readme_file.read_text(encoding="utf-8")
        # 删除原有每日更新订阅部分
        if "## 每日更新订阅" in content:
            content = content.split("## 每日更新订阅")[0].rstrip()
        content += "\n" + "\n".join(lines)
    else:
        content = "\n".join(lines)

    # 写入 README.md
    readme_file.write_text(content, encoding="utf-8")


def main():
    """主入口函数"""
    parser = argparse.ArgumentParser(description="Run a collector")
    parser.add_argument(
        "--site",
        nargs="*",
        choices=list_collectors(),
        help="Choose which site(s) to collect from. If empty, all sites are collected",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all supported collectors and exit",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Number of threads for concurrent collectors",
    )
    parser.add_argument(
        "--proxy",
        action="store_true",
        help="Use proxy collect",
    )

    args = parser.parse_args()

    # 列出采集器
    if args.list:
        print("Supported collectors:")
        for name in list_collectors():
            print(f"  - {name}")
        return

    # 选择采集器列表
    if args.site and len(args.site) > 0:
        collectors_to_run = args.site
    else:
        collectors_to_run = list_collectors()

    logging.info(f"Collectors to run: {collectors_to_run}")

    # 初始化服务
    record = RecordService(config.app.record_file)
    report_service = ReportService()

    # 获取代理列表
    if args.proxy:
        http_service = HttpService()
        validator = ProxyValidator(http_service, config.proxy)
        proxy_service = ProxyService(http_service, validator, config.proxy)
        proxy_list = proxy_service.get_validated_proxies()
    else:
        proxy_list = [None]

    logging.info(f"Get available proxy: {len(proxy_list)}")

    # 使用 ThreadPoolExecutor 并发运行采集器
    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(run_collector, name, proxy_list, config.app.output_dir, record): name
            for name in collectors_to_run
        }
        for future in as_completed(futures):
            name = futures[future]
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                logging.error(f"Collector {name} failed: {e}")
                # 创建失败结果
                results.append(
                    CollectorResult(
                        site=name,
                        all_urls=[],
                        tried_urls=[],
                        success_urls=[],
                        failed_urls=[],
                        url_status={},
                        result="failed"
                    )
                )

    # 生成报告
    report_content = report_service.generate(results)
    report_service.save(report_content, config.app.report_file)
    report_service.print_report(report_content)

    # 更新 README
    update_readme(config.app.output_dir, config.app.readme_file, config.proxy.github_proxy)


if __name__ == "__main__":
    main()

