"""自定义异常类"""


class CollectorError(Exception):
    """采集器基础异常"""

    def __init__(self, message: str, collector_name: str | None = None):
        self.collector_name = collector_name
        self.message = message
        super().__init__(f"[{collector_name}] {message}" if collector_name else message)


class NetworkError(CollectorError):
    """网络请求异常"""

    def __init__(
        self,
        message: str,
        url: str | None = None,
        collector_name: str | None = None,
    ):
        self.url = url
        super().__init__(message, collector_name)


class ProxyError(CollectorError):
    """代理相关异常"""

    def __init__(
        self,
        message: str,
        proxy: str | None = None,
        collector_name: str | None = None,
    ):
        self.proxy = proxy
        super().__init__(message, collector_name)


class ParseError(CollectorError):
    """解析异常"""

    def __init__(
        self,
        message: str,
        url: str | None = None,
        collector_name: str | None = None,
    ):
        self.url = url
        super().__init__(message, collector_name)


class DownloadError(CollectorError):
    """下载异常"""

    def __init__(
        self,
        message: str,
        url: str | None = None,
        filename: str | None = None,
        collector_name: str | None = None,
    ):
        self.url = url
        self.filename = filename
        super().__init__(message, collector_name)


class ValidationError(CollectorError):
    """内容验证异常"""

    def __init__(
        self,
        message: str,
        filename: str | None = None,
        collector_name: str | None = None,
    ):
        self.filename = filename
        super().__init__(message, collector_name)
