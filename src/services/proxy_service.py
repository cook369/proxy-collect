"""代理服务层（异步版本）

提供代理获取、验证和管理服务。
"""

import asyncio
import logging
import random
import time
from typing import Optional
from tqdm import tqdm

from config.settings import ProxyConfig
from core.models import ProxyInfo, ProxyType, ProxySourceConfig
from services.http_service import HttpService


class ProxyValidator:
    """代理验证器（异步）"""

    def __init__(self, http_service: HttpService, config: ProxyConfig):
        self.http_service = http_service
        self.config = config

    async def validate(self, proxy: ProxyInfo) -> tuple[bool, float]:
        """验证单个代理

        Args:
            proxy: 代理信息

        Returns:
            (是否可用, 响应时间)
        """
        try:
            start_time = time.time()
            await self.http_service.get(
                self.config.test_url, proxy=proxy.url, timeout=self.config.check_timeout
            )
            response_time = time.time() - start_time
            return True, response_time
        except asyncio.CancelledError:
            return False, 0.0
        except Exception:
            return False, 0.0

    async def validate_batch(self, proxies: list[ProxyInfo]) -> list[ProxyInfo]:
        """批量验证代理

        Args:
            proxies: 代理列表

        Returns:
            可用的代理列表
        """
        available: list[ProxyInfo] = []
        total = len(proxies)
        target_available = self.config.max_available

        semaphore = asyncio.Semaphore(self.config.check_workers)
        stop_event = asyncio.Event()

        async def _validate_one(proxy: ProxyInfo) -> None:
            if stop_event.is_set():
                return
            async with semaphore:
                success, response_time = await self.validate(proxy)
                if success:
                    proxy.record_success(response_time)
                    if not stop_event.is_set():
                        available.append(proxy)
                        if len(available) >= self.config.max_available:
                            stop_event.set()
                else:
                    proxy.record_failure()

        # Create tasks for all proxies
        tasks = [asyncio.create_task(_validate_one(p)) for p in proxies]

        # Wait with progress tracking
        checked_count = 0
        last_reported_bucket = 0

        for coro in asyncio.as_completed(tasks):
            if stop_event.is_set():
                # Cancel remaining
                for t in tasks:
                    if not t.done():
                        t.cancel()
            try:
                await coro
            except asyncio.CancelledError:
                pass
            except Exception:
                pass

            checked_count += 1
            current_percent = (
                int(len(available) * 100 / target_available)
                if target_available
                else 100
            )
            current_bucket = current_percent // 10
            if current_bucket > last_reported_bucket:
                last_reported_bucket = current_bucket
                logging.debug(
                    f"Proxy checking: {len(available)}/{target_available} available, "
                    f"{checked_count}/{total} checked"
                )

        logging.info(f"Get available Proxy: {len(available)}")
        return available


class ProxyService:
    """代理服务：获取、验证、管理代理（异步）"""

    def __init__(
        self, http_service: HttpService, validator: ProxyValidator, config: ProxyConfig
    ):
        self.http_service = http_service
        self.validator = validator
        self.config = config

    def _parse_proxy_sources(self) -> list[ProxySourceConfig]:
        """解析代理源配置

        Returns:
            代理源配置列表
        """
        sources = []
        for item in self.config.proxy_sources:
            if isinstance(item, str):
                sources.append(ProxySourceConfig(url=item))
            elif isinstance(item, dict):
                sources.append(
                    ProxySourceConfig(
                        url=item["url"],
                        weight=item.get("weight", 1.0),
                        proxy_type=ProxyType(item.get("proxy_type", "socks5")),
                    )
                )
        return sources

    def _parse_proxy_line(
        self, line: str, proxy_type: ProxyType, source_url: str
    ) -> Optional[ProxyInfo]:
        """解析代理行

        Args:
            line: 代理行（格式: host:port）
            proxy_type: 代理类型
            source_url: 来源 URL

        Returns:
            ProxyInfo 或 None
        """
        line = line.strip()
        if not line:
            return None

        try:
            if ":" in line:
                lines = line.split(":")
                host, port_str = lines[0].strip(), lines[1].strip()
                port = int(port_str)
                return ProxyInfo(
                    host=host,
                    port=port,
                    proxy_type=proxy_type,
                    source_url=source_url,
                )
        except (ValueError, IndexError):
            pass
        return None

    async def fetch_proxies(self) -> list[ProxyInfo]:
        """从多个源获取代理列表

        Returns:
            代理列表
        """
        all_proxies: list[ProxyInfo] = []
        sources = self._parse_proxy_sources()

        for source in sources:
            try:
                url = f"{self.config.github_proxy.rstrip('/')}/{source.url.lstrip('/')}"
                content = await self.http_service.get(url, timeout=30)

                proxies = []
                for line in content.splitlines():
                    proxy = self._parse_proxy_line(line, source.proxy_type, source.url)
                    if proxy:
                        proxies.append(proxy)

                logging.info(f"Fetched {len(proxies)} proxies from {source.url}")

                # 按权重采样
                sample_size = int(self.config.base_sample_size * source.weight)
                sample_size = min(sample_size, len(proxies))
                all_proxies.extend(random.sample(proxies, sample_size))

            except Exception as e:
                logging.error(f"Failed to fetch from {source.url}: {e}")

        # 去重
        seen: set[str] = set()
        unique: list[ProxyInfo] = []
        for p in all_proxies:
            key = f"{p.host}:{p.port}"
            if key not in seen:
                seen.add(key)
                unique.append(p)

        return unique

    async def get_validated_proxies(self) -> list[ProxyInfo]:
        """获取并验证代理

        Returns:
            可用的代理列表
        """
        proxies = await self.fetch_proxies()
        logging.info(f"Total proxies fetched: {len(proxies)}")

        validated = await self.validator.validate_batch(proxies)
        logging.info(f"Validated proxies: {len(validated)}")

        return validated
