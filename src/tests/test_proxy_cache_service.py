"""ProxyCacheService 单元测试"""
import json
import time
import pytest
from pathlib import Path
from unittest.mock import patch

from services.proxy_cache_service import ProxyCacheService
from core.models import ProxyInfo, ProxyCache, ProxyType


class TestProxyCacheService:
    """ProxyCacheService 测试类"""

    def test_init(self, tmp_path):
        """测试初始化"""
        cache_file = tmp_path / "cache.json"
        service = ProxyCacheService(cache_file, ttl=3600)

        assert service.cache_file == cache_file
        assert service.ttl == 3600

    def test_load_nonexistent_file(self, tmp_path):
        """测试加载不存在的缓存文件"""
        cache_file = tmp_path / "cache.json"
        service = ProxyCacheService(cache_file)

        cache = service.load()

        assert cache is not None
        assert len(cache.proxies) == 0

    def test_load_existing_file(self, tmp_path):
        """测试加载已存在的缓存文件"""
        cache_file = tmp_path / "cache.json"
        data = {
            "proxies": [
                {"host": "1.2.3.4", "port": 1080, "proxy_type": "socks5"}
            ],
            "created_at": time.time(),
            "updated_at": time.time(),
        }
        cache_file.write_text(json.dumps(data))

        service = ProxyCacheService(cache_file)
        cache = service.load()

        assert len(cache.proxies) == 1
        assert cache.proxies[0].host == "1.2.3.4"

    def test_save(self, tmp_path):
        """测试保存缓存"""
        cache_file = tmp_path / "cache.json"
        service = ProxyCacheService(cache_file)

        service.load()
        service.update_proxies([ProxyInfo(host="1.2.3.4", port=1080)])
        service.save()

        assert cache_file.exists()
        data = json.loads(cache_file.read_text())
        assert len(data["proxies"]) == 1

    def test_is_valid_expired(self, tmp_path):
        """测试缓存过期"""
        cache_file = tmp_path / "cache.json"
        data = {
            "proxies": [
                {"host": "1.2.3.4", "port": 1080, "success_count": 5}
            ],
            "created_at": time.time() - 7200,
            "updated_at": time.time() - 7200,
        }
        cache_file.write_text(json.dumps(data))

        service = ProxyCacheService(cache_file, ttl=3600)

        assert service.is_valid() is False

    def test_is_valid_not_enough_healthy(self, tmp_path):
        """测试健康代理不足"""
        cache_file = tmp_path / "cache.json"
        data = {
            "proxies": [
                {"host": "1.2.3.4", "port": 1080, "fail_count": 10}
            ],
            "created_at": time.time(),
            "updated_at": time.time(),
        }
        cache_file.write_text(json.dumps(data))

        service = ProxyCacheService(cache_file, ttl=3600)

        assert service.is_valid(min_health_score=50.0) is False

    def test_get_proxies(self, tmp_path):
        """测试获取健康代理"""
        cache_file = tmp_path / "cache.json"
        service = ProxyCacheService(cache_file)

        p1 = ProxyInfo(host="1.2.3.4", port=1080)
        p1.record_success(1.0)
        p2 = ProxyInfo(host="5.6.7.8", port=1080)
        p2.record_failure()

        service.load()
        service.update_proxies([p1, p2])

        healthy = service.get_proxies(min_health_score=30.0)
        assert len(healthy) == 1
        assert healthy[0].host == "1.2.3.4"

    def test_update_proxies_merge(self, tmp_path):
        """测试更新代理时合并统计"""
        cache_file = tmp_path / "cache.json"
        service = ProxyCacheService(cache_file)

        p1 = ProxyInfo(host="1.2.3.4", port=1080, success_count=5)
        service.load()
        service.update_proxies([p1])

        p2 = ProxyInfo(host="1.2.3.4", port=1080, success_count=3)
        service.update_proxies([p2])

        proxies = service.cache.proxies
        assert len(proxies) == 1
        assert proxies[0].success_count == 8

    def test_update_proxy_stats(self, tmp_path):
        """测试更新单个代理统计"""
        cache_file = tmp_path / "cache.json"
        service = ProxyCacheService(cache_file)

        proxy = ProxyInfo(host="1.2.3.4", port=1080)

        service.update_proxy_stats(proxy, success=True, response_time=1.5)
        assert proxy.success_count == 1
        assert proxy.total_response_time == 1.5

        service.update_proxy_stats(proxy, success=False)
        assert proxy.fail_count == 1

    def test_clear(self, tmp_path):
        """测试清空缓存"""
        cache_file = tmp_path / "cache.json"
        cache_file.write_text('{"proxies": []}')

        service = ProxyCacheService(cache_file)
        service.load()
        service.clear()

        assert len(service.cache.proxies) == 0
        assert not cache_file.exists()
