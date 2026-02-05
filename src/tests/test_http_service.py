"""HttpService 单元测试"""

import pytest
from unittest.mock import Mock, patch
import requests

from services.http_service import HttpService, ProxyPool
from core.models import ProxyInfo, ProxyType


class TestHttpService:
    """HttpService 测试类"""

    def test_create_session_with_ssl_verification(self):
        """测试创建带 SSL 验证的会话"""
        service = HttpService(verify_ssl=True)
        assert service.verify_ssl is True
        assert service.session.verify is True

    def test_create_session_without_ssl_verification(self):
        """测试创建不带 SSL 验证的会话"""
        service = HttpService(verify_ssl=False)
        assert service.verify_ssl is False
        assert service.session.verify is False

    @patch("services.http_service.requests.Session.get")
    def test_get_success(self, mock_get):
        """测试成功的 GET 请求"""
        mock_response = Mock()
        mock_response.text = "test content"
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        service = HttpService()
        result = service.get("http://example.com")

        assert result == "test content"
        mock_get.assert_called_once()

    @patch("services.http_service.requests.Session.get")
    def test_get_with_proxy(self, mock_get):
        """测试使用代理的 GET 请求"""
        mock_response = Mock()
        mock_response.text = "test content"
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        service = HttpService()
        result = service.get("http://example.com", proxy="socks5://proxy:1080")

        assert result == "test content"
        call_kwargs = mock_get.call_args[1]
        assert call_kwargs["proxies"] == {
            "http": "socks5://proxy:1080",
            "https": "socks5://proxy:1080",
        }

    @patch("services.http_service.requests.Session.get")
    def test_get_empty_response(self, mock_get):
        """测试空响应"""
        mock_response = Mock()
        mock_response.text = "   "
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        service = HttpService()
        with pytest.raises(ValueError, match="Empty response"):
            service.get("http://example.com")

    @patch("services.http_service.requests.Session.get")
    def test_get_http_error(self, mock_get):
        """测试 HTTP 错误"""
        mock_get.side_effect = requests.HTTPError("404 Not Found")

        service = HttpService()
        with pytest.raises(requests.HTTPError):
            service.get("http://example.com")


class TestProxyPool:
    """ProxyPool 测试类"""

    def test_init_empty(self):
        """测试空代理池初始化"""
        pool = ProxyPool()
        assert pool.get_sorted() == []

    def test_init_with_proxy_strings(self):
        """测试带代理字符串列表的初始化"""
        proxies = ["socks5h://1.2.3.4:1080", "socks5h://5.6.7.8:1080"]
        pool = ProxyPool(proxies)
        assert len(pool.get_sorted()) == 2

    def test_init_with_proxy_info(self):
        """测试带 ProxyInfo 列表的初始化"""
        proxies = [
            ProxyInfo(host="1.2.3.4", port=1080),
            ProxyInfo(host="5.6.7.8", port=1080),
        ]
        pool = ProxyPool(proxies)
        assert len(pool.get_sorted()) == 2

    def test_add_proxy_string(self):
        """测试添加代理字符串"""
        pool = ProxyPool()
        pool.add("socks5h://1.2.3.4:1080")
        sorted_proxies = pool.get_sorted()
        assert len(sorted_proxies) == 1
        assert sorted_proxies[0].host == "1.2.3.4"

    def test_add_proxy_info(self):
        """测试添加 ProxyInfo"""
        pool = ProxyPool()
        pool.add(ProxyInfo(host="1.2.3.4", port=1080))
        sorted_proxies = pool.get_sorted()
        assert len(sorted_proxies) == 1
        assert sorted_proxies[0].host == "1.2.3.4"

    def test_health_score_sorting(self):
        """测试按健康度排序"""
        p1 = ProxyInfo(host="1.2.3.4", port=1080)
        p2 = ProxyInfo(host="5.6.7.8", port=1080)
        p3 = ProxyInfo(host="9.10.11.12", port=1080)

        # p1: 1次成功，响应时间 3.0s
        p1.record_success(3.0)
        # p2: 3次成功，响应时间 0.5s（更快）
        p2.record_success(0.5)
        p2.record_success(0.5)
        p2.record_success(0.5)
        # p3: 只有失败
        p3.record_failure()

        pool = ProxyPool([p1, p2, p3])
        sorted_proxies = pool.get_sorted()

        # p2 有更高的健康度（更多成功 + 更快响应）
        assert sorted_proxies[0].host == "5.6.7.8"
        # p3 最低（只有失败）
        assert sorted_proxies[2].host == "9.10.11.12"

    def test_record_success(self):
        """测试记录成功"""
        proxy = ProxyInfo(host="1.2.3.4", port=1080)
        pool = ProxyPool([proxy])

        pool.record_success(proxy, 1.5)

        sorted_proxies = pool.get_sorted()
        assert sorted_proxies[0].success_count == 1
        assert sorted_proxies[0].total_response_time == 1.5

    def test_record_failure(self):
        """测试记录失败"""
        proxy = ProxyInfo(host="1.2.3.4", port=1080)
        pool = ProxyPool([proxy])

        pool.record_failure(proxy)

        sorted_proxies = pool.get_sorted()
        assert sorted_proxies[0].fail_count == 1

    def test_backward_compatibility(self):
        """测试向后兼容的 increase/decrease_priority"""
        pool = ProxyPool(["socks5h://1.2.3.4:1080"])

        pool.increase_priority("socks5h://1.2.3.4:1080")
        sorted_proxies = pool.get_sorted()
        assert sorted_proxies[0].success_count == 1

        pool.decrease_priority("socks5h://1.2.3.4:1080")
        sorted_proxies = pool.get_sorted()
        assert sorted_proxies[0].fail_count == 1

    def test_get_proxy_urls(self):
        """测试获取代理 URL 列表"""
        proxies = [
            ProxyInfo(host="1.2.3.4", port=1080),
            ProxyInfo(host="5.6.7.8", port=8080, proxy_type=ProxyType.HTTP),
        ]
        pool = ProxyPool(proxies)

        urls = pool.get_proxy_urls()
        assert "socks5h://1.2.3.4:1080" in urls
        assert "http://5.6.7.8:8080" in urls
