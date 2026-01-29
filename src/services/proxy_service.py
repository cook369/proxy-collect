"""代理服务层

提供代理获取、验证和管理服务。
"""

import logging
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional
from tqdm import tqdm

from config.settings import ProxyConfig
from core.models import ProxyInfo, ProxyType, ProxySourceConfig
from services.http_service import HttpService


class ProxyValidator:
    """代理验证器"""

    def __init__(self, http_service: HttpService, config: ProxyConfig):
        self.http_service = http_service
        self.config = config

    def validate(self, proxy: ProxyInfo) -> tuple[bool, float]:
        """验证单个代理

        Args:
            proxy: 代理信息

        Returns:
            (是否可用, 响应时间)
        """
        try:
            start_time = time.time()
            self.http_service.get(
                self.config.test_url, proxy=proxy.url, timeout=self.config.check_timeout
            )
            response_time = time.time() - start_time
            return True, response_time
        except Exception:
            return False, 0.0

    def validate_batch(self, proxies: list[ProxyInfo]) -> list[ProxyInfo]:
        """批量验证代理

        Args:
            proxies: 代理列表

        Returns:
            可用的代理列表
        """
        available = []
        total = len(proxies)

        with ThreadPoolExecutor(max_workers=self.config.check_workers) as executor:
            futures = {executor.submit(self.validate, p): p for p in proxies}

            with tqdm(total=total, desc="Proxy Checking", unit="proxy") as pbar:
                for future in as_completed(futures):
                    proxy = futures[future]
                    try:
                        success, response_time = future.result()
                        if success:
                            proxy.record_success(response_time)
                            available.append(proxy)
                            if len(available) >= self.config.max_available:
                                for f in futures:
                                    if not f.done():
                                        f.cancel()
                                break
                        else:
                            proxy.record_failure()
                    except Exception:
                        proxy.record_failure()
                        logging.debug(f"Proxy failed: {proxy.url}")

                    pbar.update(1)
                    pbar.set_postfix(
                        {"Available": len(available), "Checked": f"{pbar.n}/{total}"}
                    )

        logging.info(f"Get available Proxy: {len(available)}")
        return available


class ProxyService:
    """代理服务：获取、验证、管理代理"""

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
                host, port_str = line.rsplit(":", 1)
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

    def fetch_proxies(self) -> list[ProxyInfo]:
        """从多个源获取代理列表

        Returns:
            代理列表
        """
        all_proxies: list[ProxyInfo] = []
        sources = self._parse_proxy_sources()

        for source in sources:
            try:
                url = f"{self.config.github_proxy}/{source.url}"
                content = self.http_service.get(url, timeout=30)

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
        seen = set()
        unique = []
        for p in all_proxies:
            key = f"{p.host}:{p.port}"
            if key not in seen:
                seen.add(key)
                unique.append(p)

        return unique

    def get_validated_proxies(self) -> list[ProxyInfo]:
        """获取并验证代理

        Returns:
            可用的代理列表
        """
        proxies = self.fetch_proxies()
        logging.info(f"Total proxies fetched: {len(proxies)}")

        validated = self.validator.validate_batch(proxies)
        logging.info(f"Validated proxies: {len(validated)}")

        return validated
