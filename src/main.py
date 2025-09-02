import argparse
import datetime
import logging
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import random
import requests
from tabulate import tabulate
from tqdm import tqdm


from collectors.base import (
    CollectorResult,
    DownloadRecord,
    get_collector,
    list_collectors,
)

OUTPUT_DIR = Path("../dist/")
RECORD_FILE = OUTPUT_DIR / "downloaded.json"
REPORT_FILE = OUTPUT_DIR / "report.txt"
README_FILE = Path("../README.md")
GITHUB_PROXY = "https://ghproxy.net"
PROXY_URLS = [
    "https://raw.githubusercontent.com/hookzof/socks5_list/refs/heads/master/proxy.txt",
    "https://raw.githubusercontent.com/proxifly/free-proxy-list/refs/heads/main/proxies/protocols/socks5/data.txt",
    "https://raw.githubusercontent.com/roosterkid/openproxylist/refs/heads/main/SOCKS5_RAW.txt",
    "https://raw.githubusercontent.com/sunny9577/proxy-scraper/refs/heads/master/generated/socks5_proxies.txt",
    "https://raw.githubusercontent.com/zloi-user/hideip.me/refs/heads/master/socks5.txt",
    "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/refs/heads/master/socks5.txt",
]
TEST_URL = "http://httpbin.org/ip"
MAX_AVAILABLE_PROXIES = 50


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def test_proxy_head(url: str, proxy: str, timeout: int = 5) -> bool:
    session = requests.Session()
    session.verify = False
    proxies = {"http": proxy, "https": proxy}
    try:
        resp = session.head(url, proxies=proxies, timeout=timeout)
        resp.raise_for_status()
        return True
    except Exception:
        return False


def check_proxy(proxies: list[str]) -> list[str]:
    available_proxies: list[str] = []
    total = len(proxies)
    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = {executor.submit(test_proxy_head, TEST_URL, p): p for p in proxies}
        with tqdm(
            total=total,
            desc="Proxy Checking",
            unit="proxy",
        ) as pbar:
            for future in as_completed(futures):
                proxy = futures[future]
                try:
                    future.result()
                    available_proxies.append(proxy)
                    if len(available_proxies) >= MAX_AVAILABLE_PROXIES:
                        for f in futures:
                            if not f.done():
                                f.cancel()
                        break
                except Exception:
                    logging.debug(f"Proxy failed: {proxy}")
                pbar.update(1)
                pbar.set_postfix(
                    {
                        "Available": len(available_proxies),
                        "Checked": f"{pbar.n}/{total}",
                    }
                )

    logging.info(f"Get avaliable Proxy: {len(available_proxies)}")
    return available_proxies


def get_proxy_list() -> list[str]:
    proxies = []
    for PROXY_URL in PROXY_URLS:
        PROXY_URL = f"{GITHUB_PROXY}/{PROXY_URL}"
        resp = requests.get(PROXY_URL, timeout=30)
        resp.raise_for_status()
        proxy = [
            f"socks5h://{line.strip()}"
            for line in resp.text.splitlines()
            if line.strip()
        ]
        logging.info(f"Fetching proxies from: {PROXY_URL}, {len(proxy)}")
        proxies.extend(random.sample(proxy, min(500, len(proxy))))
    proxies = list(set(proxies))
    logging.info(f"Get All Proxy: {len(proxies)}")
    return check_proxy(proxies)


def run_collector(
    collector_name: str, proxy_list: list[str], output_dir: Path, record: DownloadRecord
):
    """运行单个采集器"""
    collector_cls = get_collector(collector_name)
    collector = collector_cls(proxy_list)
    return collector.run(output_dir, record)


def write_download_report(results: list[CollectorResult], report_file: Path):
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
    report_file.write_text("\n".join(report_lines), encoding="utf-8")
    print("\n".join(report_lines))


def update_readme(
    output_dir: Path, readme_file: Path, github_prefix: str = GITHUB_PROXY
):
    """
    更新 README.md 中每日更新订阅部分
    """
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
    record = DownloadRecord(RECORD_FILE)
    args = parser.parse_args()
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

    proxy_list = get_proxy_list()

    logging.info(f"Get avaliable proxy: {len(proxy_list)}")

    # 使用 ThreadPoolExecutor 并发运行采集器
    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(run_collector, name, proxy_list, OUTPUT_DIR, record): name
            for name in collectors_to_run
        }
        for future in as_completed(futures):
            name = futures[future]
            try:
                result = future.result()  # 返回 run_collector 的字典
                results.append(result)
            except Exception:
                results.append(
                    {
                        "site": name,
                        "total_urls": 0,
                        "new_urls": [],
                        "result": "failed",
                    }
                )
    write_download_report(results, REPORT_FILE)
    update_readme(OUTPUT_DIR, README_FILE, GITHUB_PROXY)


if __name__ == "__main__":
    main()
