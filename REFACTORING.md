# 项目重构设计方案

## 📋 重构概述

本文档记录了 proxy-collect 项目的完整重构设计方案。重构目标是降低模块耦合度、提高代码可维护性和可扩展性，遵循 SOLID、DRY、KISS 等设计原则。

### 重构动机

**当前架构存在的问题：**

1. **职责过多** - `base.py` 包含多个不相关的类（ProxyManager、DownloadRecord、BaseCollector）
2. **高耦合** - `main.py` 混合了配置、业务逻辑、工具函数
3. **代码重复** - 采集器中存在大量重复的解析和 URL 构建逻辑
4. **难以测试** - 缺少依赖注入，组件紧耦合
5. **硬编码配置** - 配置分散在代码中，难以管理

### 重构目标

- ✅ 清晰的分层架构（配置层、核心层、服务层、采集器层）
- ✅ 单一职责原则（每个类只负责一件事）
- ✅ 依赖注入（通过构造函数注入依赖）
- ✅ 消除重复代码（通过 Mixin 和工具类）
- ✅ 易于测试（接口定义、依赖注入）
- ✅ 保持向后兼容（命令行接口不变）

---

## 🏗️ 新的目录结构

### 重构前

```
src/
├── main.py              # 主入口（职责过多）
├── collectors/
│   ├── __init__.py      # 自动导入所有采集器
│   ├── base.py          # 基类和核心组件（职责过多）
│   └── collector_*.py   # 各站点采集器实现（代码重复）
```

### 重构后

```
src/
├── main.py                          # 简化的入口点
├── config/
│   ├── __init__.py
│   └── settings.py                  # 集中配置管理
├── core/
│   ├── __init__.py
│   ├── models.py                    # 数据模型（dataclass）
│   ├── exceptions.py                # 自定义异常
│   └── interfaces.py                # 接口定义（Protocol）
├── collectors/
│   ├── __init__.py
│   ├── base.py                      # 简化的 BaseCollector
│   ├── registry.py                  # 采集器注册表
│   ├── mixins.py                    # 采集器通用 Mixin
│   └── sites/                       # 采集器实现
│       ├── __init__.py
│       ├── cfmem.py
│       ├── datia.py
│       ├── jichangx.py
│       ├── nodefree.py
│       ├── oneclash.py
│       ├── la85.py
│       └── yudou.py
├── services/
│   ├── __init__.py
│   ├── http_service.py              # HTTP 请求服务
│   ├── proxy_service.py             # 代理管理服务
│   ├── record_service.py            # 下载记录服务
│   └── report_service.py            # 报告生成服务
├── utils/
│   ├── __init__.py
│   ├── file_utils.py                # 文件操作工具
│   └── html_parser.py               # HTML 解析工具
└── cli/
    ├── __init__.py
    └── commands.py                  # CLI 命令处理
```

---

## 📦 模块职责说明

### 1. config/ - 配置层

**职责：** 集中管理所有配置项

**文件：**
- `settings.py` - 定义 AppConfig、ProxyConfig、CollectorConfig

**解决的问题：**
- 消除硬编码配置
- 便于测试（可注入不同配置）
- 支持环境变量和配置文件

### 2. core/ - 核心层

**职责：** 定义核心数据模型、接口和异常

**文件：**
- `models.py` - 纯数据模型（CollectorResult、DownloadTask、ProxyInfo）
- `interfaces.py` - 接口定义（HttpClient、RecordStorage、ReportGenerator）
- `exceptions.py` - 自定义异常类

**解决的问题：**
- 数据模型与业务逻辑分离
- 依赖倒置原则（依赖抽象而非具体实现）
- 便于 Mock 测试

### 3. services/ - 服务层

**职责：** 提供可复用的业务服务

**文件：**
- `http_service.py` - HTTP 请求服务（HttpService、ProxyHttpService）
- `proxy_service.py` - 代理服务（ProxyValidator、ProxyPool、ProxyService）
- `record_service.py` - 下载记录服务（RecordService）
- `report_service.py` - 报告生成服务（ReportService）

**解决的问题：**
- 从 base.py 和 main.py 中提取业务逻辑
- 单一职责原则
- 依赖注入，易于测试

### 4. collectors/ - 采集器层

**职责：** 采集器框架和实现

**文件：**
- `base.py` - 简化的 BaseCollector（只负责采集逻辑）
- `registry.py` - 采集器注册表
- `mixins.py` - 通用 Mixin（TwoStepCollectorMixin、XPathParserMixin、DateBasedUrlMixin）
- `sites/*.py` - 各站点采集器实现

**解决的问题：**
- BaseCollector 职责单一
- 通过 Mixin 消除重复代码
- 依赖注入服务

### 5. utils/ - 工具层

**职责：** 提供通用工具函数

**文件：**
- `file_utils.py` - 文件操作工具
- `html_parser.py` - HTML 解析工具

### 6. cli/ - 命令行层

**职责：** 处理命令行交互

**文件：**
- `commands.py` - CLI 命令处理

**解决的问题：**
- 从 main.py 中分离 CLI 逻辑
- main.py 只负责入口和依赖组装

---

## 🎯 设计原则应用

### SOLID 原则

| 原则 | 应用示例 |
|------|---------|
| **Single Responsibility** | `HttpService` 只负责 HTTP 请求<br>`ProxyValidator` 只负责代理验证<br>`RecordService` 只负责记录管理 |
| **Open/Closed** | 通过 Mixin 扩展采集器功能<br>通过 Protocol 定义接口 |
| **Liskov Substitution** | 所有采集器都可替换 `BaseCollector`<br>所有实现都可替换 Protocol 接口 |
| **Interface Segregation** | 小接口：`HttpClient`、`RecordStorage`、`ReportGenerator` |
| **Dependency Inversion** | 依赖 Protocol 接口而非具体实现<br>通过构造函数注入依赖 |

### DRY 原则

**消除的重复代码：**

| 重复模式 | 解决方案 |
|---------|---------|
| 两步采集流程（首页→今日页面→下载链接） | `TwoStepCollectorMixin` |
| XPath 解析逻辑 | `XPathParserMixin` |
| 日期 URL 构建 | `DateBasedUrlMixin` |
| HTTP 请求逻辑 | `HttpService` |
| 代理验证逻辑 | `ProxyValidator` |
| 下载记录管理 | `RecordService` |

### KISS 原则

**简化的设计：**
- 每个类职责单一，易于理解
- 依赖注入替代复杂的内部创建
- Mixin 替代复杂的继承层次
- Protocol 替代抽象基类

---

## 🔄 重构步骤

### 阶段 1：基础设施（任务 #2-4）

1. **创建新目录结构** (#2)
   - 创建 config/、core/、services/、utils/、cli/、collectors/sites/ 目录

2. **实现配置管理模块** (#3)
   - 创建 config/settings.py
   - 定义 AppConfig、ProxyConfig、CollectorConfig

3. **实现核心模块** (#4)
   - 创建 core/models.py（数据模型）
   - 创建 core/interfaces.py（接口定义）
   - 创建 core/exceptions.py（自定义异常）

### 阶段 2：服务层（任务 #5-8）

4. **实现 HTTP 服务层** (#5)
   - 创建 services/http_service.py
   - 实现 HttpService、ProxyHttpService

5. **实现代理服务层** (#6)
   - 创建 services/proxy_service.py
   - 实现 ProxyValidator、ProxyPool、ProxyService

6. **实现记录服务层** (#7)
   - 创建 services/record_service.py
   - 实现 RecordService

7. **实现报告服务层** (#8)
   - 创建 services/report_service.py
   - 实现 ReportService

### 阶段 3：采集器层（任务 #9-11）

8. **重构 BaseCollector** (#9)
   - 简化 collectors/base.py
   - 移除 ProxyManager、DownloadRecord
   - 通过依赖注入接收服务

9. **创建采集器 Mixin** (#10)
   - 创建 collectors/mixins.py
   - 实现 TwoStepCollectorMixin、XPathParserMixin、DateBasedUrlMixin

10. **迁移采集器到新结构** (#11)
    - 将 collector_*.py 移动到 collectors/sites/
    - 应用 Mixin 消除重复代码
    - 更新导入路径

### 阶段 4：入口层（任务 #12-13）

11. **重构 main.py** (#12)
    - 简化入口逻辑
    - 使用服务层
    - 提取 CLI 逻辑到 cli/commands.py

12. **测试验证** (#13)
    - 运行所有采集器
    - 验证功能一致性
    - 检查输出文件

---

## 📊 重构前后对比

### 代码量对比

| 模块 | 重构前 | 重构后 | 变化 |
|------|--------|--------|------|
| base.py | ~250 行 | ~100 行 | -60% |
| main.py | ~280 行 | ~150 行 | -46% |
| 单个采集器 | ~50 行 | ~25 行 | -50% |
| **总代码量** | ~800 行 | ~1200 行 | +50% |

**说明：** 虽然总代码量增加，但：
- 代码结构更清晰
- 重复代码大幅减少
- 可维护性显著提升
- 易于测试和扩展

### 耦合度对比

| 指标 | 重构前 | 重构后 |
|------|--------|--------|
| main.py 依赖数 | 6 个类/函数 | 3 个服务 |
| base.py 职责数 | 4 个 | 1 个 |
| 采集器代码重复率 | ~60% | ~10% |
| 可测试性 | 低（紧耦合） | 高（依赖注入） |

---

## 🧪 测试策略

### 单元测试

重构后每个模块都可以独立测试：

```python
# 测试 HttpService
def test_http_service():
    service = HttpService()
    html = service.get("https://example.com")
    assert html

# 测试 ProxyValidator（使用 Mock）
def test_proxy_validator():
    mock_http = Mock(spec=HttpService)
    mock_http.get.return_value = "OK"

    validator = ProxyValidator(mock_http, ProxyConfig())
    assert validator.validate("socks5://proxy:1080")

# 测试 BaseCollector（使用 Mock）
def test_collector():
    mock_http = Mock(spec=HttpClient)
    mock_record = Mock(spec=RecordStorage)

    collector = MyCollector(mock_http, mock_record)
    result = collector.run(Path("output"))
    assert result.result == "success"
```

### 集成测试

```bash
# 测试完整流程
cd src && uv run main.py --site nodefree

# 测试代理模式
cd src && uv run main.py --proxy --site cfmeme

# 测试所有采集器
cd src && uv run main.py
```

---

## 🚀 迁移指南

### 对现有代码的影响

**命令行接口：** 完全兼容，无需修改

```bash
# 所有命令保持不变
cd src && uv run main.py
cd src && uv run main.py --proxy
cd src && uv run main.py --site cfmeme nodefree
```

**输出格式：** 完全一致

- `dist/{site}/clash.yaml`
- `dist/{site}/v2ray.txt`
- `dist/downloaded.json`
- `dist/report.txt`
- `README.md` 更新逻辑

**GitHub Actions：** 无需修改

工作流程保持不变，因为命令行接口兼容。

### 添加新采集器

**重构前：**

```python
# collectors/collector_newsite.py
from .base import BaseCollector, register_collector

@register_collector
class CollectorNewSite(BaseCollector):
    name = "newsite"
    home_page = "https://newsite.com"

    def get_download_urls(self) -> list[tuple[str, str]]:
        # 需要自己实现所有逻辑
        home_html = self.fetch_html(self.home_page)
        # ... 50+ 行代码
```

**重构后：**

```python
# collectors/sites/newsite.py
from collectors.base import BaseCollector
from collectors.mixins import TwoStepCollectorMixin, XPathParserMixin

class NewSiteCollector(TwoStepCollectorMixin, XPathParserMixin, BaseCollector):
    name = "newsite"
    home_page = "https://newsite.com"

    def get_today_url(self, home_html: str) -> str:
        return self.parse_with_xpath(home_html, {
            "today": "//a[@class='today']/@href"
        })[0][1]

    def parse_download_urls(self, today_html: str) -> list[tuple[str, str]]:
        return self.parse_with_xpath(today_html, {
            "clash.yaml": "//a[contains(@href, 'clash')]/@href",
            "v2ray.txt": "//a[contains(@href, 'v2ray')]/@href"
        })
```

代码量减少 60%+，更易维护。

---

## 📝 注意事项

### 重构原则

1. **保持功能一致** - 重构不改变外部行为
2. **逐步迁移** - 按模块逐步重构，避免大爆炸式修改
3. **持续测试** - 每个阶段完成后都要测试
4. **保留旧代码** - 重构完成前保留旧代码作为参考

### 风险控制

1. **备份代码** - 重构前创建分支
2. **分阶段提交** - 每个阶段完成后提交
3. **回滚计划** - 如果出现问题可以快速回滚

### 后续优化

重构完成后可以考虑：

1. **添加单元测试** - 为核心模块添加测试
2. **性能优化** - 分析瓶颈，优化性能
3. **日志增强** - 添加结构化日志
4. **配置文件** - 支持 YAML/TOML 配置文件
5. **插件系统** - 支持外部插件

---

## 📚 参考资料

- [SOLID 原则](https://en.wikipedia.org/wiki/SOLID)
- [Python Protocol](https://peps.python.org/pep-0544/)
- [依赖注入](https://en.wikipedia.org/wiki/Dependency_injection)
- [Mixin 模式](https://en.wikipedia.org/wiki/Mixin)

---

**文档版本：** 1.0
**创建日期：** 2026-01-28
**最后更新：** 2026-01-28
