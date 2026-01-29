"""日志配置模块

提供灵活的日志配置，支持日志轮转和多级别日志文件。
"""

import logging


def setup_logging(
    level: str = "INFO",
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
        fmt="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    return root_logger
