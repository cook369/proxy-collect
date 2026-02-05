"""通用内容提取器

提供可复用的内容提取函数，用于处理下载的原始内容。
"""

import re
import logging
from typing import Callable, Optional


def extract_by_regex(
    content: str,
    pattern: str,
    flags: int = re.DOTALL,
) -> Optional[str]:
    """使用正则表达式提取内容

    Args:
        content: 原始内容
        pattern: 正则表达式
        flags: 正则标志

    Returns:
        匹配的内容，未匹配返回 None
    """
    match = re.search(pattern, content, flags)
    return match.group(0) if match else None


def unescape_backslashes(content: str) -> str:
    """
    将常见的反斜杠转义还原为真实字符

    Args:
        content: 原始内容

    Returns:
        处理后的内容
    """
    return content.replace("\\n", "\n").replace('\\"', '"').replace("\\\\", "\\")


def create_regex_extractor(
    pattern: str,
    unescape: bool = True,
    flags: int = re.DOTALL,
) -> Callable[[str], str]:
    """创建正则提取器

    Args:
        pattern: 正则表达式
        unescape: 是否转换转义的换行符
        flags: 正则标志

    Returns:
        提取器函数
    """

    def extractor(content: str) -> str:
        result = extract_by_regex(content, pattern, flags)
        if result is None:
            logging.warning(f"Regex pattern not matched: {pattern[:50]}...")
            return content
        if unescape:
            result = unescape_backslashes(result)
        return result

    return extractor
