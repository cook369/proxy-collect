# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

这是一个代理订阅链接采集工具，从多个公开网站自动采集免费代理订阅链接，并生成 Clash 和 V2Ray 格式的配置文件。项目使用 Python 3.13+ 开发，通过 GitHub Actions 定时自动运行。

## 开发环境设置

### 依赖管理

项目使用 `uv` 作为包管理器：

```bash
# 安装依赖
cd src
uv sync --locked

# 运行主程序
uv run main.py

# 使用代理模式运行
uv run main.py --proxy

# 运行测试
cd src && uv run pytest

# 运行测试（带覆盖率）
cd src && uv run pytest --cov=. --cov-report=term-missing
```

### 主要依赖

- `lxml`: HTML 解析
- `requests[socks]`: HTTP 请求和 SOCKS 代理支持
- `pydantic` / `pydantic-settings`: 配置管理和数据验证
- `tenacity`: 重试机制
- `tqdm`: 进度条显示
- `pyyaml`: YAML 文件处理
- `pytest`: 测试框架

## 核心架构

项目采用**分层架构**，职责清晰分离：

```
┌─────────────────────────────────────────────────────────┐
│                      main.py                            │
│                   (入口 & 编排)                          │
└─────────────────────────────────────────────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
┌───────────────┐  ┌───────────────┐  ┌───────────────┐
│  collectors/  │  │   services/   │  │    config/    │
│   (采集器)     │  │    (服务)     │  │    (配置)     │
└───────────────┘  └───────────────┘  └───────────────┘
        │                  │                  │
        └──────────────────┼──────────────────┘
                           ▼
                  ┌───────────────┐
                  │     core/     │
                  │ (核心模型/接口) │
                  └───────────────┘
```

### 1. 核心层 (`core/`)

定义基础数据结构和接口，不依赖其他模块：

- **`interfaces.py`**: Protocol 接口定义（`HttpClient`）
- **`models.py`**: 数据模型
  - `DownloadTask`: 下载任务（含可选的内容处理器）
  - `ProxyInfo`: 代理信息（含健康度评分算法）
  - `CollectorResult`: 采集结果
  - `FileManifest` / `SiteManifest`: 文件和站点清单
  - `ProxyCache`: 代理缓存
- **`exceptions.py`**: 自定义异常类
  - `CollectorError` → `NetworkError` / `ProxyError` / `ParseError` / `DownloadError` / `ValidationError`

### 2. 配置层 (`config/`)

使用 Pydantic 进行配置管理，支持环境变量和 `.env` 文件：

- **`settings.py`**: 配置类
  - `AppConfig`: 应用配置（输出目录、manifest 文件等）
  - `ProxyConfig`: 代理配置（代理源、缓存、健康度阈值等）
  - `CollectorConfig`: 采集器配置（超时、并发数等）
  - `Config`: 全局配置聚合

### 3. 服务层 (`services/`)

提供可复用的业务服务：

- **`http_service.py`**:
  - `HttpService`: 基础 HTTP 请求（带重试）
  - `ProxyPool`: 代理池管理（健康度排序）
  - `ProxyHttpService`: 支持代理池的并发请求
- **`proxy_service.py`**:
  - `ProxyValidator`: 代理验证器
  - `ProxyService`: 代理获取和验证服务
- **`proxy_cache_service.py`**: 代理缓存服务
- **`manifest_service.py`**: Manifest 管理服务
- **`file_processor.py`**: 文件后处理（注入时间戳等）

### 4. 采集器层 (`collectors/`)

插件式架构，通过装饰器自动注册：

- **`base.py`**: 基类和注册表
  - `BaseCollector`: 采集器基类
  - `register_collector`: 注册装饰器
  - `COLLECTOR_REGISTRY`: 采集器注册表
- **`mixins.py`**: 通用 Mixin 和辅助函数
  - `TwoStepCollectorMixin`: 两步采集（首页 → 今日页面 → 下载）
  - `DateBasedUrlMixin`: 基于日期的 URL 构建
  - `safe_xpath()` / `safe_xpath_all()`: 安全的 XPath 查询函数
- **`sites/`**: 具体站点采集器实现

### 5. 工具层 (`utils/`)

- **`logging_config.py`**: 日志配置
- **`extractors.py`**: 内容提取器
  - `extract_by_regex()`: 正则提取
  - `unescape_newlines()`: 转义换行符处理
  - `create_regex_extractor()`: 创建正则提取器（用于 DownloadTask.processor）

## 采集器模式

### 基础采集器

```python
from collectors.base import BaseCollector, register_collector
from core.models import DownloadTask

@register_collector
class SimpleCollector(BaseCollector):
    name = "simple"
    home_page = "https://example.com"

    def get_download_tasks(self) -> list[DownloadTask]:
        # 直接返回下载任务
        return [
            DownloadTask(filename="clash.yaml", url="https://example.com/clash.yaml"),
            DownloadTask(filename="v2ray.txt", url="https://example.com/v2ray.txt"),
        ]
```

### 两步采集器（推荐）

大多数站点需要先访问首页获取今日链接，再解析下载地址：

```python
from typing import Optional
from collectors.base import BaseCollector, register_collector
from collectors.mixins import TwoStepCollectorMixin, safe_xpath, safe_xpath_all
from core.models import DownloadTask

@register_collector
class TwoStepCollector(TwoStepCollectorMixin, BaseCollector):
    name = "twosite"
    home_page = "https://example.com"

    def get_today_url(self, home_html: str) -> Optional[str]:
        """从首页获取今日链接"""
        links = safe_xpath_all(home_html, '//a[contains(text(), "今日")]/@href', self.name)
        return links[0] if links else None

    def parse_download_tasks(self, today_html: str) -> list[DownloadTask]:
        """从今日页面解析下载任务"""
        tasks = []
        clash_url = safe_xpath(today_html, '//a[contains(@href, "clash")]/@href', self.name)
        if clash_url:
            tasks.append(DownloadTask(filename="clash.yaml", url=clash_url))
        v2ray_url = safe_xpath(today_html, '//a[contains(@href, "v2ray")]/@href', self.name)
        if v2ray_url:
            tasks.append(DownloadTask(filename="v2ray.txt", url=v2ray_url))
        return tasks
```

### 基于日期的采集器

```python
from collectors.base import BaseCollector, register_collector
from collectors.mixins import DateBasedUrlMixin
from core.models import DownloadTask

@register_collector
class DateCollector(DateBasedUrlMixin, BaseCollector):
    name = "datesite"
    home_page = "https://example.com"

    def get_download_tasks(self) -> list[DownloadTask]:
        return self.build_date_tasks(
            base_url="https://example.com/files",
            date_format="%Y%m%d",  # 生成如 20240101
            extensions={
                "clash.yaml": ".yaml",
                "v2ray.txt": ".txt",
            }
        )
```

### 带内容处理器的采集器

当下载的内容需要额外处理（如从 HTML 中提取 YAML）时，可以使用 `processor`：

```python
from collectors.base import BaseCollector, register_collector
from collectors.mixins import TwoStepCollectorMixin, safe_xpath
from core.models import DownloadTask
from utils.extractors import create_regex_extractor

# 创建正则提取器
CLASH_EXTRACTOR = create_regex_extractor(
    pattern=r"mixed-port.*rule-providers.*?",
    unescape=True,  # 将 \n 转换为真正的换行符
)

@register_collector
class ProcessorCollector(TwoStepCollectorMixin, BaseCollector):
    name = "processor_example"
    home_page = "https://example.com"

    def get_today_url(self, home_html: str) -> Optional[str]:
        return safe_xpath(home_html, '//a/@href', self.name)

    def parse_download_tasks(self, today_html: str) -> list[DownloadTask]:
        clash_url = safe_xpath(today_html, '//div[@class="clash"]', self.name)
        return [
            DownloadTask(
                filename="clash.yaml",
                url=clash_url,
                processor=CLASH_EXTRACTOR,  # 下载后自动应用处理器
            ),
        ]
```

## 常用命令

```bash
# 列出所有支持的采集器
cd src && uv run main.py --list

# 采集所有站点（不使用代理）
cd src && uv run main.py

# 使用代理采集所有站点
cd src && uv run main.py --proxy

# 采集指定站点
cd src && uv run main.py --site cfmeme nodefree

# 指定并发线程数
cd src && uv run main.py --workers 8

# 禁用代理缓存（强制刷新）
cd src && uv run main.py --proxy --no-proxy-cache

# 调试模式
cd src && LOG_LEVEL=DEBUG uv run main.py --proxy
```

## 添加新采集器

1. 在 `src/collectors/sites/` 目录创建新文件（如 `newsite.py`）
2. 继承 `BaseCollector` 并使用 `@register_collector` 装饰器
3. 根据站点特点选择合适的 Mixin
4. 实现必要的方法
5. 新采集器会自动被发现和注册，无需修改其他文件

## GitHub Actions 自动化

### collect.yml - 采集工作流

- **触发条件**:
  - 推送到 main 分支
  - 定时任务（每 2 小时整点 + 凌晨加密时段）
  - 手动触发
- **执行流程**: 安装依赖 → 运行采集（带代理）→ 智能提交
- **输出**: 更新 `dist/` 目录和 `README.md`

**智能 Commit 策略**：
- 检测上一个 commit 是否为 CI 提交（author: `github-actions[bot]`）
- 如果是，使用 `--amend` 合并到上一个 commit 并 `--force` 推送
- 避免产生大量重复的 CI commit

### clean.yml - 清理工作流

- **触发条件**: 每天 2:00 UTC / 手动触发
- **功能**: 删除超过 3 天的旧 workflow 运行记录，保留最少 20 条

## 项目结构

```
src/
├── main.py                    # 主入口，命令行参数解析和编排
├── core/                      # 核心层
│   ├── interfaces.py          # Protocol 接口定义
│   ├── models.py              # 数据模型
│   └── exceptions.py          # 自定义异常
├── config/                    # 配置层
│   └── settings.py            # Pydantic 配置管理
├── services/                  # 服务层
│   ├── http_service.py        # HTTP 请求和代理池
│   ├── proxy_service.py       # 代理获取和验证
│   ├── proxy_cache_service.py # 代理缓存
│   ├── manifest_service.py    # Manifest 管理
│   └── file_processor.py      # 文件后处理
├── collectors/                # 采集器层
│   ├── base.py                # 基类和注册表
│   ├── mixins.py              # 通用 Mixin
│   └── sites/                 # 具体站点采集器
│       ├── cfmem.py
│       ├── nodefree.py
│       └── ...
├── utils/                     # 工具层
│   ├── logging_config.py      # 日志配置
│   └── extractors.py          # 内容提取器
└── tests/                     # 测试
    ├── conftest.py            # pytest fixtures
    ├── test_collectors.py
    ├── test_http_service.py
    └── ...

dist/                          # 输出目录
├── {site}/                    # 每个站点一个子目录
│   ├── clash.yaml
│   └── v2ray.txt
├── manifest.json              # 采集状态清单
└── proxy_cache.json           # 代理缓存
```

## 配置说明

支持通过环境变量或 `.env` 文件配置：

```bash
# 应用配置
APP_OUTPUT_DIR=./dist          # 输出目录

# 代理配置
PROXY_GITHUB_PROXY=https://ghproxy.net  # GitHub 代理
PROXY_MAX_AVAILABLE=15         # 最大可用代理数
PROXY_CHECK_TIMEOUT=5          # 代理检查超时（秒）
PROXY_CHECK_WORKERS=20         # 代理检查并发数
PROXY_CACHE_ENABLED=true       # 启用代理缓存
PROXY_CACHE_TTL=3600           # 缓存有效期（秒）
PROXY_MIN_HEALTH_SCORE=30.0    # 最低健康度评分

# 日志级别
LOG_LEVEL=INFO                 # DEBUG / INFO / WARNING / ERROR
```

## 注意事项

- 所有采集器必须使用 `@register_collector` 装饰器
- 采集器的 `name` 属性必须唯一，用于目录命名和命令行参数
- `fetch_html()` 方法已处理代理轮换和重试，直接使用即可
- 下载的文件会自动保存到 `dist/{name}/` 目录
- 项目工作目录在 `src/`，所有相对路径基于此目录
- 使用 `TwoStepCollectorMixin` 时，`today_page` 属性会自动设置

## 待优化项（TODO）

以下是代码审查中发现的潜在优化点，供后续迭代参考：

### 1. 代理池并发策略优化

当前 `ProxyHttpService.fetch_with_proxies()` 会同时向所有代理发起请求，第一个成功后取消其他请求。这种策略在代理数量较多时可能造成资源浪费。

**建议**:
- 考虑分批次请求（如每批 3-5 个代理）
- 或采用优先级队列，优先使用健康度高的代理

### 2. 异步支持

当前项目使用 `ThreadPoolExecutor` 进行并发。对于 I/O 密集型任务，`asyncio` + `aiohttp` 可能提供更好的性能。

**建议**: 评估是否值得迁移到异步架构，需权衡改动成本和收益。

### 3. 测试覆盖

项目已有较完整的单元测试，但可以进一步增强：
- 添加更多的集成测试
- 添加采集器的端到端测试（使用 mock 数据）
- 考虑添加性能基准测试

### 4. 监控和可观测性

**建议**:
- 添加采集成功率、响应时间等指标收集
- 考虑集成 Prometheus 指标或简单的统计报告
- 添加告警机制（如连续失败时通知）
