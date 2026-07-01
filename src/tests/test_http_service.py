"""HttpService 单元测试（异步版本）"""

import asyncio
import pytest
from unittest.mock import AsyncMock, Mock, patch

from services.http_service import HttpService, ProxyHttpService, ProxyPool
from core.exceptions import ProxyError
from core.models import ProxyInfo, ProxyType
from utils.check import default_check_html


class TestHttpService:
    """HttpService 测试类"""

    def test_create_session_holds_verify_setting(self):
        """测试创建带 SSL 验证的配置"""
        service = HttpService(verify_ssl=True)
        assert service.verify_ssl is True
        assert service._session is None  # 延迟初始化

    def test_create_session_without_ssl_verification(self):
        """测试创建不带 SSL 验证的会话"""
        service = HttpService(verify_ssl=False)
        assert service.verify_ssl is False
        assert service._session is None  # 延迟初始化

    @pytest.mark.asyncio
    async def test_get_success(self):
        """测试成功的 GET 请求"""
        from unittest.mock import AsyncMock, MagicMock

        with patch("aiohttp.ClientSession.get") as mock_get:
            mock_resp = AsyncMock()
            mock_resp.text = AsyncMock(return_value="test content")
            mock_resp.raise_for_status = Mock()
            mock_get.return_value.__aenter__ = AsyncMock(return_value=mock_resp)
            mock_get.return_value.__aexit__ = AsyncMock(return_value=False)

            service = HttpService()
            result = await service.get("http://example.com")

            assert result == "test content"

    @pytest.mark.asyncio
    async def test_get_empty_response(self):
        """测试空响应"""
        with patch("aiohttp.ClientSession.get") as mock_get:
            mock_resp = AsyncMock()
            mock_resp.text = AsyncMock(return_value="   ")
            mock_resp.raise_for_status = Mock()
            mock_get.return_value.__aenter__ = AsyncMock(return_value=mock_resp)
            mock_get.return_value.__aexit__ = AsyncMock(return_value=False)

            service = HttpService()
            with pytest.raises(ValueError, match="Empty response"):
                await service.get("http://example.com")


class TestProxyPool:
    """ProxyPool 测试类"""

    @pytest.mark.asyncio
    async def test_init_empty(self):
        """测试空代理池初始化"""
        pool = ProxyPool()
        assert await pool.get_sorted() == []

    @pytest.mark.asyncio
    async def test_init_with_proxy_strings(self):
        """测试带代理字符串列表的初始化"""
        proxies = ["socks5h://1.2.3.4:1080", "socks5h://5.6.7.8:1080"]
        pool = ProxyPool(proxies)
        assert len(await pool.get_sorted()) == 2

    @pytest.mark.asyncio
    async def test_init_with_proxy_info(self):
        """测试带 ProxyInfo 列表的初始化"""
        proxies = [
            ProxyInfo(host="1.2.3.4", port=1080),
            ProxyInfo(host="5.6.7.8", port=1080),
        ]
        pool = ProxyPool(proxies)
        assert len(await pool.get_sorted()) == 2

    @pytest.mark.asyncio
    async def test_add_proxy_string(self):
        """测试添加代理字符串"""
        pool = ProxyPool()
        await pool.add("socks5h://1.2.3.4:1080")
        sorted_proxies = await pool.get_sorted()
        assert len(sorted_proxies) == 1
        assert sorted_proxies[0].host == "1.2.3.4"

    @pytest.mark.asyncio
    async def test_add_proxy_info(self):
        """测试添加 ProxyInfo"""
        pool = ProxyPool()
        await pool.add(ProxyInfo(host="1.2.3.4", port=1080))
        sorted_proxies = await pool.get_sorted()
        assert len(sorted_proxies) == 1
        assert sorted_proxies[0].host == "1.2.3.4"

    @pytest.mark.asyncio
    async def test_health_score_sorting(self):
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
        sorted_proxies = await pool.get_sorted()

        # p2 有更高的健康度（更多成功 + 更快响应）
        assert sorted_proxies[0].host == "5.6.7.8"
        # p3 最低（只有失败）
        assert sorted_proxies[2].host == "9.10.11.12"

    @pytest.mark.asyncio
    async def test_record_success(self):
        """测试记录成功"""
        proxy = ProxyInfo(host="1.2.3.4", port=1080)
        pool = ProxyPool([proxy])

        await pool.record_success(proxy, 1.5)

        sorted_proxies = await pool.get_sorted()
        assert sorted_proxies[0].success_count == 1
        assert sorted_proxies[0].total_response_time == 1.5

    @pytest.mark.asyncio
    async def test_record_failure(self):
        """测试记录失败"""
        proxy = ProxyInfo(host="1.2.3.4", port=1080)
        pool = ProxyPool([proxy])

        await pool.record_failure(proxy)

        sorted_proxies = await pool.get_sorted()
        assert sorted_proxies[0].fail_count == 1

    @pytest.mark.asyncio
    async def test_backward_compatibility(self):
        """测试向后兼容的 increase/decrease_priority"""
        pool = ProxyPool(["socks5h://1.2.3.4:1080"])

        await pool.increase_priority("socks5h://1.2.3.4:1080")
        sorted_proxies = await pool.get_sorted()
        assert sorted_proxies[0].success_count == 1

        await pool.decrease_priority("socks5h://1.2.3.4:1080")
        sorted_proxies = await pool.get_sorted()
        assert sorted_proxies[0].fail_count == 1

    @pytest.mark.asyncio
    async def test_get_proxy_urls(self):
        """测试获取代理 URL 列表"""
        proxies = [
            ProxyInfo(host="1.2.3.4", port=1080),
            ProxyInfo(host="5.6.7.8", port=8080, proxy_type=ProxyType.HTTP),
        ]
        pool = ProxyPool(proxies)

        urls = await pool.get_proxy_urls()
        assert "socks5h://1.2.3.4:1080" in urls
        assert "http://5.6.7.8:8080" in urls


class TestProxyHttpService:
    """ProxyHttpService 测试类"""

    @pytest.mark.asyncio
    async def test_no_proxy_pool_falls_back_to_direct(self):
        """无代理池时走直连"""
        mock_http = Mock(spec=HttpService)
        mock_http.get = AsyncMock(return_value="direct-content")
        svc = ProxyHttpService(mock_http, None, batch_size=5)
        result = await svc.fetch_with_proxies("http://x")
        assert result == "direct-content"

    @pytest.mark.asyncio
    async def test_empty_pool_raises_proxyerror(self):
        """代理池为空时抛 ProxyError"""
        mock_http = Mock(spec=HttpService)
        svc = ProxyHttpService(mock_http, ProxyPool(), batch_size=5)
        with pytest.raises(ProxyError):
            await svc.fetch_with_proxies("http://x")

    @pytest.mark.asyncio
    async def test_no_persistent_executor_or_shutdown(self):
        """不再持有长期线程池，也不再暴露 shutdown"""
        mock_http = Mock(spec=HttpService)
        svc = ProxyHttpService(mock_http, ProxyPool(), batch_size=5)
        assert not hasattr(svc, "executor")
        assert not hasattr(svc, "shutdown")
