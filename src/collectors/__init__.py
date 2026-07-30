import importlib
import pkgutil

import collectors.sites

# 自动导入 sites 目录下的所有采集器
for _finder, modname, _ispkg in pkgutil.iter_modules(collectors.sites.__path__):
    importlib.import_module(f"collectors.sites.{modname}")
