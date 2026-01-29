"""自定义异常类"""


class CollectorError(Exception):
    """采集器基础异常"""
    pass


class NetworkError(CollectorError):
    """网络请求异常"""
    pass


class ProxyError(CollectorError):
    """代理相关异常"""
    pass


class ParseError(CollectorError):
    """解析异常"""
    pass


class DownloadError(CollectorError):
    """下载异常"""
    pass
