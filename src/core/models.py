"""核心数据模型

纯数据模型，不包含业务逻辑。
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Callable
import time


@dataclass
class DownloadTask:
    """下载任务"""

    filename: str
    url: str
    processor: Optional[Callable[[str], str]] = None


@dataclass
class FileManifest:
    """文件清单"""

    url: str
    success: bool
    error: Optional[str] = None


@dataclass
class SiteManifest:
    """站点清单"""

    today_page: Optional[str]
    status: str  # "success" / "partial" / "failed"
    updated_at: Optional[str]
    files: dict[str, FileManifest] = field(default_factory=dict)
    error: Optional[str] = None


@dataclass
class CollectorResult:
    """采集器执行结果"""

    site: str
    today_page: Optional[str]
    files: dict[str, FileManifest]
    status: str  # "success" / "partial" / "failed"
    error: Optional[str] = None


class ProxyType(Enum):
    """代理类型枚举"""

    HTTP = "http"
    HTTPS = "https"
    SOCKS4 = "socks4"
    SOCKS5 = "socks5"


@dataclass
class ProxyInfo:
    """代理信息（增强版）"""

    host: str
    port: int
    proxy_type: ProxyType = ProxyType.SOCKS5
    success_count: int = 0
    fail_count: int = 0
    total_response_time: float = 0.0
    last_check_time: Optional[float] = None
    last_success_time: Optional[float] = None
    source_url: Optional[str] = None

    @property
    def url(self) -> str:
        """生成代理 URL"""
        scheme = self.proxy_type.value
        if self.proxy_type == ProxyType.SOCKS5:
            scheme = "socks5h"
        return f"{scheme}://{self.host}:{self.port}"

    @property
    def total_count(self) -> int:
        """总请求次数"""
        return self.success_count + self.fail_count

    @property
    def success_rate(self) -> float:
        """成功率 (0-100)"""
        if self.total_count == 0:
            return 0.0
        return (self.success_count / self.total_count) * 100

    @property
    def avg_response_time(self) -> float:
        """平均响应时间（秒）"""
        if self.success_count == 0:
            return float("inf")
        return self.total_response_time / self.success_count

    @property
    def health_score(self) -> float:
        """健康度评分 (0-100)

        算法:
        - 成功率权重: 60%
        - 响应时间权重: 30%
        - 活跃度权重: 10%
        """
        # 成功率得分 (0-60)
        success_score = self.success_rate * 0.6

        # 响应时间得分 (0-30)
        avg_time = self.avg_response_time
        if avg_time <= 1.0:
            time_score = 30.0
        elif avg_time <= 3.0:
            time_score = 20.0
        elif avg_time <= 5.0:
            time_score = 10.0
        elif avg_time == float("inf"):
            time_score = 0.0
        else:
            time_score = 5.0

        # 活跃度得分 (0-10)
        if self.last_success_time is None:
            activity_score = 0.0
        else:
            hours_since_success = (time.time() - self.last_success_time) / 3600
            if hours_since_success <= 1:
                activity_score = 10.0
            elif hours_since_success <= 6:
                activity_score = 7.0
            elif hours_since_success <= 24:
                activity_score = 4.0
            else:
                activity_score = 1.0

        return success_score + time_score + activity_score

    def record_success(self, response_time: float):
        """记录成功请求"""
        self.success_count += 1
        self.total_response_time += response_time
        self.last_check_time = time.time()
        self.last_success_time = time.time()

    def record_failure(self):
        """记录失败请求"""
        self.fail_count += 1
        self.last_check_time = time.time()

    def to_dict(self) -> dict:
        """转换为字典（用于序列化）"""
        return {
            "host": self.host,
            "port": self.port,
            "proxy_type": self.proxy_type.value,
            "success_count": self.success_count,
            "fail_count": self.fail_count,
            "total_response_time": self.total_response_time,
            "last_check_time": self.last_check_time,
            "last_success_time": self.last_success_time,
            "source_url": self.source_url,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ProxyInfo":
        """从字典创建实例"""
        return cls(
            host=data["host"],
            port=data["port"],
            proxy_type=ProxyType(data.get("proxy_type", "socks5")),
            success_count=data.get("success_count", 0),
            fail_count=data.get("fail_count", 0),
            total_response_time=data.get("total_response_time", 0.0),
            last_check_time=data.get("last_check_time"),
            last_success_time=data.get("last_success_time"),
            source_url=data.get("source_url"),
        )


@dataclass
class ProxySourceConfig:
    """代理源配置"""

    url: str
    weight: float = 1.0
    proxy_type: ProxyType = ProxyType.SOCKS5

    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "weight": self.weight,
            "proxy_type": self.proxy_type.value,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ProxySourceConfig":
        return cls(
            url=data["url"],
            weight=data.get("weight", 1.0),
            proxy_type=ProxyType(data.get("proxy_type", "socks5")),
        )


@dataclass
class ProxyCache:
    """代理缓存"""

    proxies: list[ProxyInfo] = field(default_factory=list)
    created_at: Optional[float] = None
    updated_at: Optional[float] = None

    def is_expired(self, ttl: int) -> bool:
        """检查缓存是否过期"""
        if self.updated_at is None:
            return True
        return (time.time() - self.updated_at) > ttl

    def get_healthy_proxies(self, min_score: float = 30.0) -> list[ProxyInfo]:
        """获取健康度达标的代理"""
        return [p for p in self.proxies if p.health_score >= min_score]

    def to_dict(self) -> dict:
        return {
            "proxies": [p.to_dict() for p in self.proxies],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ProxyCache":
        return cls(
            proxies=[ProxyInfo.from_dict(p) for p in data.get("proxies", [])],
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )
