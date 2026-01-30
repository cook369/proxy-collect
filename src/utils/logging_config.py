"""日志配置模块

提供灵活的日志配置，支持日志轮转和多级别日志文件。
"""
import logging
import logging.handlers
import os
from pathlib import Path
from typing import Optional


def get_log_dir() -> Path:
    """获取日志目录"""
    log_dir = Path(os.getenv("LOG_DIR", "./logs"))
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def setup_logging(
    level: str = "INFO",
    log_file: Optional[str] = None,
    enable_rotation: bool = True,
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5
):
    """配置日志系统

    Args:
        level: 日志级别（DEBUG, INFO, WARNING, ERROR, CRITICAL）
        log_file: 日志文件名（可选，默认为 app.log）
        enable_rotation: 是否启用日志轮转
        max_bytes: 单个日志文件最大大小（字节）
        backup_count: 保留的备份文件数量
    """
    # 获取日志级别
    log_level = getattr(logging, level.upper(), logging.INFO)

    # 创建根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # 清除现有的处理器
    root_logger.handlers.clear()

    # 日志格式
    formatter = logging.Formatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # 文件处理器（如果指定了日志文件）
    if log_file:
        log_dir = get_log_dir()
        log_path = log_dir / log_file

        if enable_rotation:
            # 使用轮转文件处理器
            file_handler = logging.handlers.RotatingFileHandler(
                filename=log_path,
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding="utf-8"
            )
        else:
            # 使用普通文件处理器
            file_handler = logging.FileHandler(
                filename=log_path,
                encoding="utf-8"
            )

        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    return root_logger


def setup_multi_level_logging(
    base_level: str = "INFO",
    enable_rotation: bool = True
):
    """配置多级别日志文件

    为不同级别的日志创建单独的文件：
    - app.log: 所有日志（INFO 及以上）
    - error.log: 错误日志（ERROR 及以上）

    Args:
        base_level: 基础日志级别
        enable_rotation: 是否启用日志轮转
    """
    log_dir = get_log_dir()
    log_level = getattr(logging, base_level.upper(), logging.INFO)

    # 创建根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.handlers.clear()

    # 日志格式
    formatter = logging.Formatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # 通用日志文件（INFO 及以上）
    if enable_rotation:
        info_handler = logging.handlers.RotatingFileHandler(
            filename=log_dir / "app.log",
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding="utf-8"
        )
    else:
        info_handler = logging.FileHandler(
            filename=log_dir / "app.log",
            encoding="utf-8"
        )
    info_handler.setLevel(logging.INFO)
    info_handler.setFormatter(formatter)
    root_logger.addHandler(info_handler)

    # 错误日志文件（ERROR 及以上）
    if enable_rotation:
        error_handler = logging.handlers.RotatingFileHandler(
            filename=log_dir / "error.log",
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding="utf-8"
        )
    else:
        error_handler = logging.FileHandler(
            filename=log_dir / "error.log",
            encoding="utf-8"
        )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    root_logger.addHandler(error_handler)

    return root_logger
