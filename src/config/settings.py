"""配置管理模块

集中管理所有配置项，支持环境变量和默认值。
"""
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AppConfig:
    """应用配置"""

    # 输出目录
    output_dir: Path = Path("../dist/")

    # 记录文件
    record_file: Optional[Path] = None

    # 报告文件
    report_file: Optional[Path] = None

    # README 文件
    readme_file: Path = Path("../README.md")

    def __post_init__(self):
        """初始化后处理"""
        if self.record_file is None:
            self.record_file = self.output_dir / "downloaded.json"

        if self.report_file is None:
            self.report_file = self.output_dir / "report.txt"


@dataclass
class ProxyConfig:
    """代理配置"""

    # GitHub 代理
    github_proxy: str = "https://ghproxy.net"

    # 测试 URL
    test_url: str = "http://httpbin.org/ip"

    # 最大可用代理数
    max_available: int = 50

    # 代理检查超时（秒）
    check_timeout: int = 5

    # 代理检查并发数
    check_workers: int = 20

    # 代理源列表
    proxy_sources: list[str] = field(default_factory=lambda: [
        "https://raw.githubusercontent.com/hookzof/socks5_list/refs/heads/master/proxy.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/refs/heads/main/proxies/protocols/socks5/data.txt",
        "https://raw.githubusercontent.com/roosterkid/openproxylist/refs/heads/main/SOCKS5_RAW.txt",
        "https://raw.githubusercontent.com/sunny9577/proxy-scraper/refs/heads/master/generated/socks5_proxies.txt",
        "https://raw.githubusercontent.com/zloi-user/hideip.me/refs/heads/master/socks5.txt",
        "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/refs/heads/master/socks5.txt",
    ])


@dataclass
class CollectorConfig:
    """采集器配置"""

    # 下载超时（秒）
    download_timeout: int = 20

    # 最大并发采集器数
    max_workers: int = 4

    # 重试次数
    retry_times: int = 3

    # HTTP 请求超时（秒）
    http_timeout: int = 30


@dataclass
class Config:
    """全局配置"""

    app: AppConfig = field(default_factory=AppConfig)
    proxy: ProxyConfig = field(default_factory=ProxyConfig)
    collector: CollectorConfig = field(default_factory=CollectorConfig)


# 默认配置实例
default_config = Config()
