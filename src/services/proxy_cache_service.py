"""代理缓存服务

提供代理缓存的加载、保存和统计更新功能。
"""

import json
import logging
import time
from pathlib import Path
from typing import Optional

from core.models import ProxyInfo, ProxyCache


class ProxyCacheService:
    """代理缓存服务"""

    def __init__(self, cache_file: Path, ttl: int = 3600):
        """初始化缓存服务

        Args:
            cache_file: 缓存文件路径
            ttl: 缓存有效期（秒）
        """
        self.cache_file = cache_file
        self.ttl = ttl
        self._cache: Optional[ProxyCache] = None

    @property
    def cache(self) -> ProxyCache:
        """获取缓存实例"""
        if self._cache is None:
            self._cache = ProxyCache()
        return self._cache

    def load(self) -> ProxyCache:
        """加载缓存

        Returns:
            缓存实例
        """
        if not self.cache_file.exists():
            logging.info(f"Cache file not found: {self.cache_file}")
            self._cache = ProxyCache(created_at=time.time())
            return self._cache

        try:
            with open(self.cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._cache = ProxyCache.from_dict(data)
            logging.info(f"Loaded {len(self._cache.proxies)} proxies from cache")
            return self._cache
        except (json.JSONDecodeError, KeyError) as e:
            logging.warning(f"Failed to load cache: {e}")
            self._cache = ProxyCache(created_at=time.time())
            return self._cache

    def save(self) -> None:
        """保存缓存"""
        if self._cache is None:
            return

        self._cache.updated_at = time.time()
        if self._cache.created_at is None:
            self._cache.created_at = time.time()

        self.cache_file.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(self._cache.to_dict(), f, indent=2)
            logging.info(f"Saved {len(self._cache.proxies)} proxies to cache")
        except IOError as e:
            logging.error(f"Failed to save cache: {e}")

    def is_valid(self, min_health_score: float = 30.0) -> bool:
        """检查缓存是否有效

        Args:
            min_health_score: 最低健康度评分

        Returns:
            缓存是否有效可用
        """
        if self._cache is None:
            self._cache = self.load()

        if self._cache.is_expired(self.ttl):
            logging.info("Cache expired")
            return False

        healthy = self._cache.get_healthy_proxies(min_health_score)
        if len(healthy) < 10:
            logging.info(f"Not enough healthy proxies: {len(healthy)}")
            return False

        return True

    def get_proxies(self, min_health_score: float = 30.0) -> list[ProxyInfo]:
        """获取健康的代理列表

        Args:
            min_health_score: 最低健康度评分

        Returns:
            健康代理列表
        """
        if self._cache is None:
            self._cache = self.load()

        return self._cache.get_healthy_proxies(min_health_score)

    def update_proxies(self, proxies: list[ProxyInfo]) -> None:
        """更新缓存中的代理列表

        Args:
            proxies: 新的代理列表
        """
        if self._cache is None:
            self._cache = ProxyCache(created_at=time.time())

        # 合并现有代理和新代理
        existing = {f"{p.host}:{p.port}": p for p in self._cache.proxies}

        for proxy in proxies:
            key = f"{proxy.host}:{proxy.port}"
            if key in existing:
                # 合并统计信息
                old = existing[key]
                proxy.success_count += old.success_count
                proxy.fail_count += old.fail_count
                proxy.total_response_time += old.total_response_time
            existing[key] = proxy

        self._cache.proxies = list(existing.values())
        self._cache.updated_at = time.time()

    def update_proxy_stats(
        self, proxy: ProxyInfo, success: bool, response_time: float = 0.0
    ) -> None:
        """更新单个代理的统计信息

        Args:
            proxy: 代理信息
            success: 是否成功
            response_time: 响应时间（秒）
        """
        if success:
            proxy.record_success(response_time)
        else:
            proxy.record_failure()

    def clear(self) -> None:
        """清空缓存"""
        self._cache = ProxyCache(created_at=time.time())
        if self.cache_file.exists():
            self.cache_file.unlink()
            logging.info("Cache cleared")
