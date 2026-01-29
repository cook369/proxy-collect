"""代理服务层

提供代理获取、验证和管理服务。
"""
import logging
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional
from tqdm import tqdm

from config.settings import ProxyConfig
from services.http_service import HttpService


class ProxyValidator:
    """代理验证器"""

    def __init__(self, http_service: HttpService, config: ProxyConfig):
        self.http_service = http_service
        self.config = config

    def validate(self, proxy: str) -> bool:
        """验证单个代理

        Args:
            proxy: 代理地址

        Returns:
            是否可用
        """
        try:
            self.http_service.get(
                self.config.test_url,
                proxy=proxy,
                timeout=self.config.check_timeout
            )
            return True
        except Exception:
            return False

    def validate_batch(self, proxies: list[str]) -> list[str]:
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
                        if future.result():
                            available.append(proxy)
                            if len(available) >= self.config.max_available:
                                # 取消剩余任务
                                for f in futures:
                                    if not f.done():
                                        f.cancel()
                                break
                    except Exception:
                        logging.debug(f"Proxy failed: {proxy}")

                    pbar.update(1)
                    pbar.set_postfix({
                        "Available": len(available),
                        "Checked": f"{pbar.n}/{total}"
                    })

        logging.info(f"Get available Proxy: {len(available)}")
        return available


class ProxyService:
    """代理服务：获取、验证、管理代理"""

    def __init__(
        self,
        http_service: HttpService,
        validator: ProxyValidator,
        config: ProxyConfig
    ):
        self.http_service = http_service
        self.validator = validator
        self.config = config

    def fetch_proxies(self) -> list[str]:
        """从多个源获取代理列表

        Returns:
            代理列表
        """
        all_proxies = []

        for source_url in self.config.proxy_sources:
            try:
                url = f"{self.config.github_proxy}/{source_url}"
                content = self.http_service.get(url, timeout=30)

                proxies = [
                    f"socks5h://{line.strip()}"
                    for line in content.splitlines()
                    if line.strip()
                ]

                logging.info(f"Fetched {len(proxies)} proxies from {source_url}")

                # 随机采样
                all_proxies.extend(random.sample(proxies, min(500, len(proxies))))

            except Exception as e:
                logging.error(f"Failed to fetch from {source_url}: {e}")

        # 去重
        return list(set(all_proxies))

    def get_validated_proxies(self) -> list[str]:
        """获取并验证代理

        Returns:
            可用的代理列表
        """
        proxies = self.fetch_proxies()
        logging.info(f"Total proxies fetched: {len(proxies)}")

        validated = self.validator.validate_batch(proxies)
        logging.info(f"Validated proxies: {len(validated)}")

        return validated
