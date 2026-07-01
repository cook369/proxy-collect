"""HttpService 单元测试"""

import threading
import time

import pytest
from unittest.mock import Mock, patch
import requests

from services.http_service import HttpService, ProxyHttpService, ProxyPool
from core.exceptions import ProxyError
from core.models import ProxyInfo, ProxyType
from utils.check import default_check_html


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


class _FakeHttpService:
    """可控的 HttpService 替身：按代理 URL 指定行为，记录调用。"""

    def __init__(self, behavior=None, *, direct=None):
        # behavior: proxy_url -> ("ok", content)
        #                      | ("fail",)
        #                      | ("slow", seconds, content)
        self.behavior = behavior or {}
        self.direct = direct
        self.calls: list[str | None] = []
        self._lock = threading.Lock()

    def _get(
        self, url, proxy=None, timeout=30, headers=None, check_html=default_check_html
    ):
        with self._lock:
            self.calls.append(proxy)
        action = self.behavior.get(proxy)
        if action is None:
            raise requests.ConnectionError(f"no route via {proxy}")
        kind = action[0]
        if kind == "ok":
            return action[1]
        if kind == "slow":
            time.sleep(action[1])
            return action[2]
        raise requests.ConnectionError(f"fail via {proxy}")

    def get(self, url, proxy=None, timeout=30, headers=None, check_html=default_check_html):
        if self.direct is not None:
            return self.direct
        # 委托给 _get（保持代理竞速测试兼容）
        return self._get(url, proxy=proxy, timeout=timeout, headers=headers, check_html=check_html)


class TestProxyHttpService:
    """ProxyHttpService 小批次竞速与线程池生命周期测试"""

    def _pool(self, n: int) -> tuple[list[ProxyInfo], ProxyPool]:
        proxies = [ProxyInfo(host=f"10.0.0.{i}", port=1000 + i) for i in range(n)]
        return proxies, ProxyPool(proxies)

    def test_returns_first_successful_proxy(self):
        """同一批内有代理成功时返回其响应"""
        proxies, pool = self._pool(3)
        fake = _FakeHttpService({proxies[0].url: ("ok", "winner")})
        svc = ProxyHttpService(fake, pool, batch_size=5)
        assert svc.fetch_with_proxies("http://x") == "winner"

    def test_advances_to_next_batch_when_batch_fails(self):
        """前面的批整批失败时，应继续尝试后续批次"""
        proxies, pool = self._pool(3)
        # batch_size=1 → 每个代理各成一批；只有最后一个成功
        fake = _FakeHttpService({proxies[2].url: ("ok", "third")})
        svc = ProxyHttpService(fake, pool, batch_size=1)
        assert svc.fetch_with_proxies("http://x") == "third"
        # 三个代理都被尝试过
        assert set(fake.calls) == {p.url for p in proxies}

    def test_first_proxy_win_short_circuits_later_batches(self):
        """首个代理就命中时，后续批次的代理不应被触达"""
        proxies, pool = self._pool(4)
        fake = _FakeHttpService({proxies[0].url: ("ok", "first")})
        svc = ProxyHttpService(fake, pool, batch_size=1)
        assert svc.fetch_with_proxies("http://x") == "first"
        assert fake.calls == [proxies[0].url]

    def test_all_proxies_fail_raises_proxyerror(self):
        """所有代理失败时抛 ProxyError"""
        _, pool = self._pool(4)
        fake = _FakeHttpService({})  # 全部失败
        svc = ProxyHttpService(fake, pool, batch_size=2)
        with pytest.raises(ProxyError):
            svc.fetch_with_proxies("http://x")

    def test_invalid_content_is_treated_as_failure(self):
        """通过校验失败的响应应记为失败，转而尝试其它代理"""
        proxies, pool = self._pool(2)
        fake = _FakeHttpService(
            {proxies[0].url: ("ok", "   "), proxies[1].url: ("ok", "good")}
        )
        svc = ProxyHttpService(fake, pool, batch_size=5)
        # 空白内容无法通过 default_check_html，应回退到第二个代理
        assert svc.fetch_with_proxies("http://x") == "good"

    def test_no_proxy_pool_falls_back_to_direct(self):
        """无代理池时走直连（带重试的 get）"""
        fake = _FakeHttpService(direct="direct-content")
        svc = ProxyHttpService(fake, None, batch_size=5)
        assert svc.fetch_with_proxies("http://x") == "direct-content"

    def test_empty_pool_raises_proxyerror(self):
        """代理池为空时抛 ProxyError"""
        fake = _FakeHttpService({})
        svc = ProxyHttpService(fake, ProxyPool(), batch_size=5)
        with pytest.raises(ProxyError):
            svc.fetch_with_proxies("http://x")

    def test_no_persistent_executor_or_shutdown(self):
        """不再持有长期线程池，也不再暴露 shutdown"""
        svc = ProxyHttpService(_FakeHttpService({}), ProxyPool(), batch_size=5)
        assert not hasattr(svc, "executor")
        assert not hasattr(svc, "shutdown")

    def test_batch_threads_released_after_success(self):
        """命中后批内线程池随 with 关闭，调用返回时无残留工作线程"""
        proxies, pool = self._pool(5)
        behavior = {proxies[0].url: ("ok", "w")}
        for p in proxies[1:]:
            behavior[p.url] = ("slow", 0.3, "late")
        fake = _FakeHttpService(behavior)
        svc = ProxyHttpService(fake, pool, batch_size=5)

        baseline = threading.active_count()
        assert svc.fetch_with_proxies("http://x") == "w"
        # with(wait=True) 已 join，工作线程应已退出，无泄漏
        assert threading.active_count() <= baseline
