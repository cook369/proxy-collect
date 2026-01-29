"""配置模块单元测试"""
import os
import pytest
from pathlib import Path
from pydantic import ValidationError

from config.settings import AppConfig, ProxyConfig, CollectorConfig, Config


class TestAppConfig:
    """AppConfig 测试类"""

    def test_default_values(self):
        """测试默认值"""
        config = AppConfig()
        assert config.output_dir.name == "dist"
        assert config.output_dir.is_absolute()
        assert config.readme_file.name == "README.md"

    def test_output_dir_creation(self):
        """测试输出目录自动创建"""
        config = AppConfig()
        # output_dir 应该在初始化时被创建
        assert config.output_dir.exists()

    def test_manifest_file_default(self):
        """测试 manifest 文件默认路径"""
        config = AppConfig()
        assert config.manifest_file.name == "manifest.json"
        assert config.manifest_file.parent == config.output_dir


class TestProxyConfig:
    """ProxyConfig 测试类"""

    def test_default_values(self):
        """测试默认值"""
        config = ProxyConfig()
        assert config.github_proxy == "https://ghproxy.net"
        assert config.test_url == "http://httpbin.org/ip"
        assert config.max_available == 50
        assert config.check_timeout == 5
        assert config.check_workers == 20
        assert config.verify_ssl is False
        assert len(config.proxy_sources) == 6

    def test_max_available_validation(self):
        """测试 max_available 字段验证"""
        # 有效值
        config = ProxyConfig(max_available=100)
        assert config.max_available == 100

        # 无效值（小于 1）
        with pytest.raises(ValidationError):
            ProxyConfig(max_available=0)

        # 无效值（大于 1000）
        with pytest.raises(ValidationError):
            ProxyConfig(max_available=1001)

    def test_check_timeout_validation(self):
        """测试 check_timeout 字段验证"""
        # 有效值
        config = ProxyConfig(check_timeout=10)
        assert config.check_timeout == 10

        # 无效值（小于 1）
        with pytest.raises(ValidationError):
            ProxyConfig(check_timeout=0)

        # 无效值（大于 60）
        with pytest.raises(ValidationError):
            ProxyConfig(check_timeout=61)

    def test_check_workers_validation(self):
        """测试 check_workers 字段验证"""
        # 有效值
        config = ProxyConfig(check_workers=50)
        assert config.check_workers == 50

        # 无效值（小于 1）
        with pytest.raises(ValidationError):
            ProxyConfig(check_workers=0)

        # 无效值（大于 100）
        with pytest.raises(ValidationError):
            ProxyConfig(check_workers=101)


class TestCollectorConfig:
    """CollectorConfig 测试类"""

    def test_default_values(self):
        """测试默认值"""
        config = CollectorConfig()
        assert config.download_timeout == 20
        assert config.max_workers == 4
        assert config.retry_times == 3
        assert config.http_timeout == 30

    def test_download_timeout_validation(self):
        """测试 download_timeout 字段验证"""
        # 有效值
        config = CollectorConfig(download_timeout=60)
        assert config.download_timeout == 60

        # 无效值（小于 5）
        with pytest.raises(ValidationError):
            CollectorConfig(download_timeout=4)

        # 无效值（大于 300）
        with pytest.raises(ValidationError):
            CollectorConfig(download_timeout=301)

    def test_max_workers_validation(self):
        """测试 max_workers 字段验证"""
        # 有效值
        config = CollectorConfig(max_workers=10)
        assert config.max_workers == 10

        # 无效值（小于 1）
        with pytest.raises(ValidationError):
            CollectorConfig(max_workers=0)

        # 无效值（大于 20）
        with pytest.raises(ValidationError):
            CollectorConfig(max_workers=21)

    def test_retry_times_validation(self):
        """测试 retry_times 字段验证"""
        # 有效值
        config = CollectorConfig(retry_times=5)
        assert config.retry_times == 5

        # 无效值（小于 0）
        with pytest.raises(ValidationError):
            CollectorConfig(retry_times=-1)

        # 无效值（大于 10）
        with pytest.raises(ValidationError):
            CollectorConfig(retry_times=11)


class TestConfig:
    """Config 测试类"""

    def test_default_config(self):
        """测试默认配置"""
        config = Config()
        assert isinstance(config.app, AppConfig)
        assert isinstance(config.proxy, ProxyConfig)
        assert isinstance(config.collector, CollectorConfig)

    def test_nested_config_access(self):
        """测试嵌套配置访问"""
        config = Config()
        assert config.app.output_dir.name == "dist"
        assert config.proxy.max_available == 50
        assert config.collector.max_workers == 4


class TestEnvironmentVariables:
    """环境变量测试类"""

    def test_app_env_prefix(self, monkeypatch):
        """测试 APP_ 前缀的环境变量"""
        monkeypatch.setenv("APP_OUTPUT_DIR", "D:\\test\\output")
        config = AppConfig()
        assert str(config.output_dir) == "D:\\test\\output"

    def test_proxy_env_prefix(self, monkeypatch):
        """测试 PROXY_ 前缀的环境变量"""
        monkeypatch.setenv("PROXY_MAX_AVAILABLE", "100")
        monkeypatch.setenv("PROXY_VERIFY_SSL", "true")
        config = ProxyConfig()
        assert config.max_available == 100
        assert config.verify_ssl is True

    def test_collector_env_prefix(self, monkeypatch):
        """测试 COLLECTOR_ 前缀的环境变量"""
        monkeypatch.setenv("COLLECTOR_MAX_WORKERS", "8")
        monkeypatch.setenv("COLLECTOR_RETRY_TIMES", "5")
        config = CollectorConfig()
        assert config.max_workers == 8
        assert config.retry_times == 5
