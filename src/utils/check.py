from typing import Callable


def default_check_html(html: str) -> bool:
    """默认 HTML 内容检查函数"""
    return bool(html and html.strip())


def check_html_contains(keyword: str) -> Callable[[str], bool]:
    """检查 HTML 内容是否包含指定关键字"""

    def _check(html: str) -> bool:
        return keyword in html

    return _check
