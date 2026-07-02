"""HTML 解析通用工具。"""

from lxml import etree


def extract_text_by_xpath(html: str, xpath: str) -> str | None:
    """从 HTML 中提取 XPath 对应的首个文本值。

    Args:
        html: HTML 内容
        xpath: XPath 表达式

    Returns:
        提取到的首个非空文本，失败或不存在时返回 None
    """
    try:
        tree = etree.HTML(html)
        if tree is None:
            return None

        result = tree.xpath(xpath)
        if not result:
            return None

        value = result[0] if isinstance(result, list) else result
        text = str(value).strip()
        return text or None
    except Exception:
        return None
