import pkgutil
import importlib
import collectors

for _, modname, _ in pkgutil.iter_modules(collectors.__path__):
    importlib.import_module(f"collectors.{modname}")
