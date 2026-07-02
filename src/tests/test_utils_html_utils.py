"""HTML 通用工具测试。"""

from utils.html_utils import extract_text_by_xpath


def test_extract_text_by_xpath_returns_title_text():
    html = "<html><head><title>Today Title</title></head><body></body></html>"

    assert extract_text_by_xpath(html, "//title/text()") == "Today Title"


def test_extract_text_by_xpath_supports_custom_xpath():
    html = "<html><body><h1>Custom Heading</h1></body></html>"

    assert extract_text_by_xpath(html, "//h1/text()") == "Custom Heading"


def test_extract_text_by_xpath_returns_none_when_missing():
    html = "<html><body>no title</body></html>"

    assert extract_text_by_xpath(html, "//title/text()") is None
