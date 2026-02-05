"""异常类单元测试"""

from core.exceptions import (
    CollectorError,
    NetworkError,
    ProxyError,
    ParseError,
    DownloadError,
    ValidationError,
)


class TestCollectorError:
    """CollectorError 测试类"""

    def test_basic_message(self):
        """测试基本消息"""
        error = CollectorError("Test error")
        assert str(error) == "Test error"
        assert error.message == "Test error"

    def test_with_collector_name(self):
        """测试带采集器名称"""
        error = CollectorError("Test error", collector_name="test_site")
        assert "[test_site]" in str(error)
        assert error.collector_name == "test_site"


class TestNetworkError:
    """NetworkError 测试类"""

    def test_with_url(self):
        """测试带 URL"""
        error = NetworkError("Connection failed", url="http://example.com")
        assert error.url == "http://example.com"

    def test_inheritance(self):
        """测试继承关系"""
        error = NetworkError("Test")
        assert isinstance(error, CollectorError)


class TestProxyError:
    """ProxyError 测试类"""

    def test_with_proxy(self):
        """测试带代理地址"""
        error = ProxyError("Proxy failed", proxy="socks5://1.2.3.4:1080")
        assert error.proxy == "socks5://1.2.3.4:1080"


class TestParseError:
    """ParseError 测试类"""

    def test_with_url(self):
        """测试带 URL"""
        error = ParseError("Parse failed", url="http://example.com")
        assert error.url == "http://example.com"


class TestDownloadError:
    """DownloadError 测试类"""

    def test_with_filename(self):
        """测试带文件名"""
        error = DownloadError(
            "Download failed", url="http://example.com/file", filename="clash.yaml"
        )
        assert error.url == "http://example.com/file"
        assert error.filename == "clash.yaml"


class TestValidationError:
    """ValidationError 测试类"""

    def test_with_filename(self):
        """测试带文件名"""
        error = ValidationError("Invalid content", filename="clash.yaml")
        assert error.filename == "clash.yaml"
