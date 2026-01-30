# 代理池改进重构文档

## 概述

本次重构全面改进了代理池功能，包括：
1. 代理缓存机制 - 避免重复验证
2. 代理源权重配置 - 高质量源采样更多
3. 多代理类型支持 - HTTP/HTTPS/SOCKS4/SOCKS5
4. 代理健康度评分 - 优先使用高分代理

---

## 文件修改清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `src/core/models.py` | 修改 | 增强 ProxyInfo，新增 ProxyType、ProxySourceConfig、ProxyCache |
| `src/config/settings.py` | 修改 | 扩展 ProxyConfig，添加缓存和权重配置 |
| `src/services/proxy_service.py` | 修改 | 改进 ProxyValidator 和 ProxyService |
| `src/services/proxy_cache_service.py` | 新增 | 代理缓存服务 |
| `src/services/http_service.py` | 修改 | 改进 ProxyPool |
| `src/collectors/base.py` | 修改 | 兼容新的 ProxyInfo |
| `src/main.py` | 修改 | 集成缓存服务 |
| `src/tests/test_proxy_cache_service.py` | 新增 | 缓存服务测试 |
| `src/tests/test_proxy_service.py` | 修改 | 更新代理服务测试 |
| `src/tests/test_http_service.py` | 修改 | 更新 HTTP 服务测试 |

---

## 详细修改内容

### 1. 数据模型 (`src/core/models.py`)

#### 新增 ProxyType 枚举

```python
class ProxyType(Enum):
    """代理类型枚举"""
    HTTP = "http"
    HTTPS = "https"
    SOCKS4 = "socks4"
    SOCKS5 = "socks5"
```

#### 重构 ProxyInfo 数据类

**新字段：**
- `host: str` - 代理主机
- `port: int` - 代理端口
- `proxy_type: ProxyType` - 代理类型
- `success_count: int` - 成功次数
- `fail_count: int` - 失败次数
- `total_response_time: float` - 总响应时间
- `last_check_time: Optional[float]` - 最后检查时间
- `last_success_time: Optional[float]` - 最后成功时间
- `source_url: Optional[str]` - 来源 URL

**新属性：**
- `url` - 生成代理 URL
- `total_count` - 总请求次数
- `success_rate` - 成功率 (0-100)
- `avg_response_time` - 平均响应时间
- `health_score` - 健康度评分 (0-100)

**新方法：**
- `record_success(response_time)` - 记录成功请求
- `record_failure()` - 记录失败请求
- `to_dict()` - 序列化为字典
- `from_dict(data)` - 从字典反序列化

#### 新增 ProxySourceConfig 数据类

```python
@dataclass
class ProxySourceConfig:
    """代理源配置"""
    url: str
    weight: float = 1.0
    proxy_type: ProxyType = ProxyType.SOCKS5
```

#### 新增 ProxyCache 数据类

```python
@dataclass
class ProxyCache:
    """代理缓存"""
    proxies: list[ProxyInfo]
    created_at: Optional[float]
    updated_at: Optional[float]

    def is_expired(self, ttl: int) -> bool
    def get_healthy_proxies(self, min_score: float) -> list[ProxyInfo]
```

---

### 2. 配置扩展 (`src/config/settings.py`)

#### ProxyConfig 新增字段

```python
# 缓存配置
cache_enabled: bool = True          # 是否启用代理缓存
cache_ttl: int = 3600               # 缓存有效期（秒）
cache_file: Optional[str] = None    # 缓存文件路径

# 健康度配置
min_health_score: float = 30.0      # 最低健康度评分

# 采样配置
base_sample_size: int = 200         # 基础采样数量

# 代理源配置（支持权重）
proxy_sources: list[Union[str, dict]] = [
    {"url": "...", "weight": 2.0},
    {"url": "...", "weight": 1.5},
    ...
]
```

---

### 3. 缓存服务 (`src/services/proxy_cache_service.py`)

#### ProxyCacheService 类

```python
class ProxyCacheService:
    def __init__(self, cache_file: Path, ttl: int = 3600)

    def load(self) -> ProxyCache
        """加载缓存"""

    def save(self) -> None
        """保存缓存"""

    def is_valid(self, min_health_score: float = 30.0) -> bool
        """检查缓存是否有效"""

    def get_proxies(self, min_health_score: float = 30.0) -> list[ProxyInfo]
        """获取健康的代理列表"""

    def update_proxies(self, proxies: list[ProxyInfo]) -> None
        """更新缓存中的代理列表（合并统计）"""

    def update_proxy_stats(self, proxy, success, response_time) -> None
        """更新单个代理的统计信息"""

    def clear(self) -> None
        """清空缓存"""
```

---

### 4. 代理服务改进 (`src/services/proxy_service.py`)

#### ProxyValidator 改进

```python
def validate(self, proxy: ProxyInfo) -> tuple[bool, float]:
    """验证单个代理，返回 (是否可用, 响应时间)"""

def validate_batch(self, proxies: list[ProxyInfo]) -> list[ProxyInfo]:
    """批量验证代理，更新统计信息"""
```

#### ProxyService 改进

```python
def _parse_proxy_sources(self) -> list[ProxySourceConfig]:
    """解析代理源配置（支持字符串和字典格式）"""

def _parse_proxy_line(self, line, proxy_type, source_url) -> Optional[ProxyInfo]:
    """解析代理行"""

def fetch_proxies(self) -> list[ProxyInfo]:
    """从多个源获取代理列表（按权重采样）"""
```

---

### 5. HTTP 服务改进 (`src/services/http_service.py`)

#### ProxyPool 改进

```python
class ProxyPool:
    def __init__(self, proxies: Optional[Union[list[str], list[ProxyInfo]]] = None)

    def add(self, proxy: Union[str, ProxyInfo], priority: int = 0)
        """添加代理（支持字符串和 ProxyInfo）"""

    def get_sorted(self) -> list[ProxyInfo]
        """获取按健康度排序的代理列表"""

    def get_proxy_urls(self) -> list[str]
        """获取代理 URL 列表（向后兼容）"""

    def record_success(self, proxy, response_time: float)
        """记录成功请求"""

    def record_failure(self, proxy)
        """记录失败请求"""

    # 向后兼容方法
    def increase_priority(self, proxy: str)
    def decrease_priority(self, proxy: str)
```

#### ProxyHttpService 改进

```python
def fetch_with_proxies(self, url: str, timeout: int = 30) -> str:
    """使用代理池并发请求，记录响应时间"""

def _try_fetch(self, url, proxy: ProxyInfo, timeout) -> tuple[str, float]:
    """尝试获取，返回 (内容, 响应时间)"""

def get(self, url: str, timeout: int = 30) -> str:
    """兼容 HttpService 接口"""
```

---

### 6. 采集器兼容 (`src/collectors/base.py`)

```python
def __init__(
    self,
    proxies_list: Optional[Union[list[str], list[ProxyInfo]]] = None,
    http_client: Optional[HttpClient] = None,
):
    """支持字符串列表和 ProxyInfo 列表"""
```

---

### 7. 主入口集成 (`src/main.py`)

#### 新增命令行参数

```python
parser.add_argument(
    "--no-proxy-cache",
    action="store_true",
    help="Disable proxy cache and force refresh",
)
```

#### 缓存集成逻辑

```python
if args.proxy:
    # 初始化缓存服务
    cache_service = ProxyCacheService(cache_file, config.proxy.cache_ttl)

    use_cache = config.proxy.cache_enabled and not args.no_proxy_cache

    if use_cache:
        cache_service.load()
        if cache_service.is_valid(config.proxy.min_health_score):
            proxy_list = cache_service.get_proxies(config.proxy.min_health_score)

    if not proxy_list:
        proxy_list = proxy_service.get_validated_proxies()
        if cache_service and use_cache:
            cache_service.update_proxies(proxy_list)
            cache_service.save()
```

---

## 健康度评分算法

```
health_score = 成功率得分 + 响应时间得分 + 活跃度得分

成功率得分 (0-60):
  success_rate * 0.6

响应时间得分 (0-30):
  <= 1s:  30分
  <= 3s:  20分
  <= 5s:  10分
  > 5s:   5分
  无数据: 0分

活跃度得分 (0-10):
  <= 1h:  10分
  <= 6h:  7分
  <= 24h: 4分
  > 24h:  1分
  无数据: 0分
```

---

## 缓存策略

```
1. 检查缓存是否存在且未过期
2. 过滤健康度 >= min_health_score 的代理
3. 若有效代理 >= 10 个，使用缓存
4. 否则从源获取新代理并更新缓存
```

---

## 权重采样

```
sample_size = base_sample_size * weight

例: base=200, weight=2.0 → 采样 400 个
```

---

## 向后兼容

1. `proxy_sources` 支持字符串列表（旧格式）和字典列表（新格式）
2. `ProxyPool` 保留 `increase_priority()` / `decrease_priority()` 方法
3. `BaseCollector` 兼容 `list[str]` 和 `list[ProxyInfo]`

---

## 测试覆盖

### 新增测试文件
- `test_proxy_cache_service.py` - 10 个测试用例

### 更新测试文件
- `test_proxy_service.py` - 10 个测试用例
- `test_http_service.py` - 16 个测试用例

### 测试结果
```
============================= 126 passed in 8.80s =============================
```

---

## 使用方法

```bash
# 运行测试
cd src && uv run pytest tests/ -v

# 测试缓存功能
uv run main.py --proxy --site cfmem  # 首次运行，创建缓存
uv run main.py --proxy --site cfmem  # 再次运行，使用缓存

# 检查缓存文件
cat dist/proxy_cache.json

# 强制刷新（禁用缓存）
uv run main.py --proxy --no-proxy-cache
```

---

## 缓存文件格式

```json
{
  "proxies": [
    {
      "host": "1.2.3.4",
      "port": 1080,
      "proxy_type": "socks5",
      "success_count": 5,
      "fail_count": 1,
      "total_response_time": 3.5,
      "last_check_time": 1706600000.0,
      "last_success_time": 1706600000.0,
      "source_url": "https://..."
    }
  ],
  "created_at": 1706590000.0,
  "updated_at": 1706600000.0
}
```

---

## 配置示例

```python
# 环境变量配置
PROXY_CACHE_ENABLED=true
PROXY_CACHE_TTL=3600
PROXY_MIN_HEALTH_SCORE=30.0
PROXY_BASE_SAMPLE_SIZE=200

# 代码配置
proxy_sources = [
    {"url": "https://example.com/socks5.txt", "weight": 2.0},
    {"url": "https://example.com/http.txt", "weight": 1.0, "proxy_type": "http"},
]
```
