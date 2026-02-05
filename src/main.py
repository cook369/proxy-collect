"""主入口"""

import argparse
import logging
import os
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

from config.settings import Config
from core.models import CollectorResult, ProxyInfo
from services.http_service import HttpService
from services.proxy_service import ProxyValidator, ProxyService
from services.proxy_cache_service import ProxyCacheService
from services.manifest_service import ManifestService
from services.file_processor import FileProcessor
from collectors.base import get_collector, list_collectors
from utils.logging_config import setup_logging


config = Config()

log_level = os.getenv("LOG_LEVEL", "INFO")
setup_logging(level=log_level)


def run_collector(
    collector_name: str,
    proxy_list: list[ProxyInfo],
    output_dir: Path,
) -> CollectorResult:
    """运行单个采集器"""
    collector_cls = get_collector(collector_name)
    collector = collector_cls(proxy_list)
    return collector.run(output_dir)


def update_readme(
    manifest: ManifestService,
    readme_file: Path,
    github_prefix: str,
    output_dir: Path,
):
    """更新 README.md"""
    lines = ["\n## 采集状态\n"]
    lines.append("| 站点 | 状态 | 更新时间 | 今日来源 |")
    lines.append("|------|------|----------|----------|")

    for site_name in sorted(manifest.sites.keys()):
        site = manifest.sites[site_name]
        status_icon = {"success": "✅", "partial": "⚠️", "failed": "❌"}.get(
            site.status, "❓"
        )
        updated = site.updated_at[:16] if site.updated_at else "-"
        source = f"[链接]({site.today_page})" if site.today_page else "-"
        lines.append(f"| {site_name} | {status_icon} | {updated} | {source} |")

    lines.append(f"\n**最后运行**: {manifest.last_run}\n")
    lines.append("\n---\n")
    lines.append("\n## 每日更新订阅\n")

    for site_name in sorted(manifest.sites.keys()):
        site = manifest.sites[site_name]
        if site.status == "failed":
            continue

        site_dir = output_dir / site_name
        status_suffix = " ⚠️" if site.status == "partial" else ""
        lines.append(f"### {site_name}{status_suffix}\n")
        lines.append("| 类型 | 订阅链接 |")
        lines.append("|:----:|----------|")

        clash_path = site_dir / "clash.yaml"
        v2ray_path = site_dir / "v2ray.txt"

        if clash_path.exists():
            url = f"{github_prefix}/https://raw.githubusercontent.com/cook369/proxy-collect/main/dist/{site_name}/clash.yaml"
            lines.append(f"| Clash | {url} |")

        if v2ray_path.exists():
            url = f"{github_prefix}/https://raw.githubusercontent.com/cook369/proxy-collect/main/dist/{site_name}/v2ray.txt"
            lines.append(f"| V2Ray | {url} |")

        lines.append("")

    lines.append("\n---\n")

    if readme_file.exists():
        content = readme_file.read_text(encoding="utf-8")
        if "## 采集状态" in content:
            content = content.split("## 采集状态")[0].rstrip()
        elif "## 每日更新订阅" in content:
            content = content.split("## 每日更新订阅")[0].rstrip()
        content += "\n" + "\n".join(lines)
    else:
        content = "\n".join(lines)

    readme_file.write_text(content, encoding="utf-8")


def print_report(results: list[CollectorResult]):
    """打印控制台报告"""
    print("\n" + "=" * 60)
    print("                    代理采集报告")
    print("=" * 60)

    success_count = sum(1 for r in results if r.status == "success")
    partial_count = sum(1 for r in results if r.status == "partial")
    failed_count = sum(1 for r in results if r.status == "failed")

    for r in sorted(results, key=lambda x: x.site):
        icon = {"success": "✓", "partial": "!", "failed": "✗"}.get(r.status, "?")
        files_str = "  ".join(
            f"{f} {'✓' if info.success else '✗'}" for f, info in r.files.items()
        )
        if not files_str and r.error:
            files_str = f"({r.error})"
        print(f"[{icon}] {r.site:12} │ {files_str}")

    print("-" * 60)
    print(
        f"总计: {len(results)} 站点 │ 成功: {success_count} │ 部分: {partial_count} │ 失败: {failed_count}"
    )
    print("=" * 60 + "\n")


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
    parser.add_argument(
        "--no-proxy-cache",
        action="store_true",
        help="Disable proxy cache and force refresh",
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
    manifest = ManifestService(config.app.manifest_file)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    # 获取代理列表
    proxy_list: list[ProxyInfo] = []
    cache_service = None

    if args.proxy:
        http_service = HttpService(verify_ssl=config.proxy.verify_ssl)
        validator = ProxyValidator(http_service, config.proxy)
        proxy_service = ProxyService(http_service, validator, config.proxy)

        # 初始化缓存服务
        cache_file = (
            Path(config.proxy.cache_file)
            if config.proxy.cache_file
            else config.app.output_dir / "proxy_cache.json"
        )
        cache_service = ProxyCacheService(
            cache_file, config.proxy.cache_ttl, config.proxy.min_cache_proxies
        )

        use_cache = config.proxy.cache_enabled and not args.no_proxy_cache

        if use_cache:
            cache_service.load()
            if cache_service.is_valid(config.proxy.min_health_score):
                proxy_list = cache_service.get_proxies(config.proxy.min_health_score)
                logging.info(f"Using {len(proxy_list)} proxies from cache")

        if not proxy_list:
            proxy_list = proxy_service.get_validated_proxies()
            if cache_service and use_cache:
                cache_service.update_proxies(proxy_list)
                cache_service.save()

    logging.info(f"Get available proxy: {len(proxy_list)}")

    # 使用 ThreadPoolExecutor 并发运行采集器
    results: list[CollectorResult] = []
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(
                run_collector, name, proxy_list, config.app.output_dir
            ): name
            for name in collectors_to_run
        }
        for future in as_completed(futures):
            name = futures[future]
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                logging.error(f"Collector {name} failed: {e}")
                results.append(
                    CollectorResult(
                        site=name,
                        today_page=None,
                        files={},
                        status="failed",
                        error=str(e),
                    )
                )

    # 更新 manifest 并注入时间戳
    for result in results:
        manifest.update_from_result(result)

        # 注入时间戳到 clash.yaml
        if result.status != "failed":
            clash_path = config.app.output_dir / result.site / "clash.yaml"
            FileProcessor.process_downloaded_file(clash_path, result, timestamp)

    # 保存 manifest
    manifest.save()

    # 打印控制台报告
    print_report(results)

    # 更新 README
    update_readme(
        manifest,
        config.app.readme_file,
        config.proxy.github_proxy,
        config.app.output_dir,
    )


if __name__ == "__main__":
    main()
