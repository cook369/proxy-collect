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
```

### 主要依赖

- `lxml`: HTML 解析
- `requests[socks]`: HTTP 请求和 SOCKS 代理支持
- `pycryptodome`: 加密功能
- `tabulate`: 报告生成
- `tqdm`: 进度条显示

## 核心架构

### 采集器模式 (Collector Pattern)

项目采用基于注册表的插件式架构，所有采集器继承自 `BaseCollector` 并通过装饰器自动注册：

```python
@register_collector
class CollectorExample(BaseCollector):
    name = "example"  # 采集器名称，用于命令行参数和输出目录
    home_page = "https://example.com"

    def get_download_urls(self) -> list[tuple[str, str]]:
        # 返回 (文件名, URL) 元组列表
        pass
```

### 关键组件

1. **BaseCollector** (`src/collectors/base.py`):
   - 提供 HTML 抓取、文件下载、代理管理等通用功能
   - 子类只需实现 `get_download_urls()` 方法
   - 自动处理下载记录、重试逻辑和错误处理

2. **ProxyManager** (`src/collectors/base.py:56`):
   - 管理代理池，支持并发请求
   - 动态调整代理优先级（成功+1，失败-1）
   - 自动选择最优代理进行请求

3. **DownloadRecord** (`src/collectors/base.py:28`):
   - 跟踪已下载的 URL，避免重复下载
   - 线程安全的记录管理
   - 持久化到 `dist/downloaded.json`

4. **采集器注册** (`src/collectors/__init__.py`):
   - 自动导入 `collectors/` 目录下所有模块
   - 通过 `@register_collector` 装饰器自动注册

### 工作流程

1. `main.py` 解析命令行参数，选择要运行的采集器
2. 如果启用 `--proxy`，从多个公开代理列表获取并测试可用代理
3. 使用 `ThreadPoolExecutor` 并发运行多个采集器
4. 每个采集器：
   - 访问目标网站首页
   - 解析出当日订阅链接
   - 下载 `clash.yaml` 和 `v2ray.txt` 文件到 `dist/{site}/` 目录
5. 生成下载报告到 `dist/report.txt`
6. 自动更新 `README.md` 中的订阅链接部分

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
```

## 添加新采集器

在 `src/collectors/` 目录创建新文件 `collector_newsite.py`：

```python
from lxml import etree
from .base import BaseCollector, register_collector

@register_collector
class CollectorNewSite(BaseCollector):
    name = "newsite"  # 必须唯一
    home_page = "https://newsite.com"

    def get_download_urls(self) -> list[tuple[str, str]]:
        # 1. 获取首页
        home_html = self.fetch_html(self.home_page)

        # 2. 解析页面，提取订阅链接
        tree = etree.HTML(home_html)
        clash_url = tree.xpath('//a[contains(@href, "clash")]/@href')[0]
        v2ray_url = tree.xpath('//a[contains(@href, "v2ray")]/@href')[0]

        # 3. 返回 (文件名, URL) 列表
        return [
            ("clash.yaml", clash_url),
            ("v2ray.txt", v2ray_url),
        ]
```

新采集器会自动被发现和注册，无需修改其他文件。

## GitHub Actions 自动化

- **触发条件**:
  - 推送到 main 分支
  - 定时任务（每天多次）
  - 手动触发
- **执行流程**: 安装依赖 → 运行采集 → 提交更新到 Git
- **输出**: 更新 `dist/` 目录和 `README.md`

## 项目结构

```
src/
├── main.py              # 主入口，命令行参数解析和并发控制
├── collectors/
│   ├── __init__.py      # 自动导入所有采集器模块
│   ├── base.py          # 基类和核心组件
│   ├── collector_*.py   # 各站点采集器实现
dist/                    # 输出目录
├── {site}/              # 每个站点一个子目录
│   ├── clash.yaml
│   └── v2ray.txt
├── downloaded.json      # 下载记录
└── report.txt           # 采集报告
```

## 注意事项

- 所有采集器必须使用 `@register_collector` 装饰器
- 采集器的 `name` 属性必须唯一，用于目录命名和命令行参数
- `fetch_html()` 方法已处理代理轮换和重试，直接使用即可
- 下载的文件会自动保存到 `dist/{name}/` 目录
- 项目工作目录在 `src/`，所有相对路径基于此目录
