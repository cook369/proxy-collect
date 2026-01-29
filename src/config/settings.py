"""配置管理模块 - 使用 Pydantic

集中管理所有配置项，支持环境变量、.env 文件和配置验证。
"""

from pathlib import Path
from typing import Optional, Union
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def get_project_root() -> Path:
    """获取项目根目录（src 的父目录）"""
    return Path(__file__).parent.parent.parent.resolve()


class AppConfig(BaseSettings):
    """应用配置"""

    model_config = SettingsConfigDict(
        env_prefix="APP_", env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # 输出目录
    output_dir: Path = Field(
        default_factory=lambda: get_project_root() / "dist", description="输出目录"
    )

    # Manifest 文件
    manifest_file: Optional[Path] = Field(default=None, description="Manifest 文件路径")

    # README 文件
    readme_file: Path = Field(
        default_factory=lambda: get_project_root() / "README.md",
        description="README 文件路径",
    )

    @field_validator("output_dir", "readme_file", mode="after")
    @classmethod
    def resolve_path(cls, v: Path) -> Path:
        """确保路径是绝对路径"""
        return v.resolve()

    @model_validator(mode="after")
    def set_default_files(self):
        """设置默认的 manifest 文件路径"""
        if self.manifest_file is None:
            self.manifest_file = self.output_dir / "manifest.json"
        else:
            self.manifest_file = self.manifest_file.resolve()

        # 创建输出目录
        self.output_dir.mkdir(parents=True, exist_ok=True)

        return self


class ProxyConfig(BaseSettings):
    """代理配置"""

    model_config = SettingsConfigDict(
        env_prefix="PROXY_", env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # GitHub 代理
    github_proxy: str = Field(
        default="https://ghproxy.net", description="GitHub 代理地址"
    )

    # 测试 URL
    test_url: str = Field(default="http://httpbin.org/ip", description="代理测试 URL")

    # 最大可用代理数
    max_available: int = Field(
        default=15, ge=1, le=1000, description="最大可用代理数量"
    )

    # 代理检查超时（秒）
    check_timeout: int = Field(
        default=5, ge=1, le=60, description="代理检查超时时间（秒）"
    )

    # 代理检查并发数
    check_workers: int = Field(default=20, ge=1, le=100, description="代理检查并发数")

    # SSL 验证
    verify_ssl: bool = Field(default=False, description="是否验证 SSL 证书")

    # 缓存配置
    cache_enabled: bool = Field(default=True, description="是否启用代理缓存")

    cache_ttl: int = Field(
        default=3600, ge=60, le=86400, description="缓存有效期（秒）"
    )

    cache_file: Optional[str] = Field(default=None, description="缓存文件路径")

    # 健康度配置
    min_health_score: float = Field(
        default=30.0, ge=0.0, le=100.0, description="最低健康度评分"
    )

    # 采样配置
    base_sample_size: int = Field(
        default=200, ge=50, le=1000, description="基础采样数量"
    )

    # 代理源列表（支持字符串或字典格式）
    proxy_sources: list[Union[str, dict]] = Field(
        default_factory=lambda: [
            {
                "url": "https://raw.githubusercontent.com/hookzof/socks5_list/refs/heads/master/proxy.txt",
                "weight": 2.0,
            },
            {
                "url": "https://raw.githubusercontent.com/proxifly/free-proxy-list/refs/heads/main/proxies/protocols/socks5/data.txt",
                "weight": 1.5,
            },
            {
                "url": "https://raw.githubusercontent.com/roosterkid/openproxylist/refs/heads/main/SOCKS5_RAW.txt",
                "weight": 1.0,
            },
            {
                "url": "https://raw.githubusercontent.com/sunny9577/proxy-scraper/refs/heads/master/generated/socks5_proxies.txt",
                "weight": 1.0,
            },
            {
                "url": "https://raw.githubusercontent.com/zloi-user/hideip.me/refs/heads/master/socks5.txt",
                "weight": 1.5,
            },
            {
                "url": "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/refs/heads/master/socks5.txt",
                "weight": 2.0,
            },
        ],
        description="代理源配置列表",
    )


class CollectorConfig(BaseSettings):
    """采集器配置"""

    model_config = SettingsConfigDict(
        env_prefix="COLLECTOR_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # 下载超时（秒）
    download_timeout: int = Field(
        default=30, ge=5, le=300, description="下载超时时间（秒）"
    )

    # 最大并发采集器数
    max_workers: int = Field(default=4, ge=1, le=20, description="最大并发采集器数量")

    # 重试次数
    retry_times: int = Field(default=3, ge=0, le=10, description="请求重试次数")

    # HTTP 请求超时（秒）
    http_timeout: int = Field(
        default=30, ge=5, le=300, description="HTTP 请求超时时间（秒）"
    )


class Config(BaseSettings):
    """全局配置"""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    app: AppConfig = Field(default_factory=AppConfig)
    proxy: ProxyConfig = Field(default_factory=ProxyConfig)
    collector: CollectorConfig = Field(default_factory=CollectorConfig)


# 默认配置实例
default_config = Config()
