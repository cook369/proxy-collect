"""ProxyService 单元测试"""

from unittest.mock import Mock

from services.proxy_service import ProxyValidator, ProxyService
from services.http_service import HttpService
from config.settings import ProxyConfig
from core.models import ProxyInfo, ProxyType


class TestProxyValidator:
    """ProxyValidator 测试类"""

    def test_validate_success(self):
        """测试验证成功"""
        mock_http = Mock(spec=HttpService)
        mock_http.get.return_value = '{"origin": "1.2.3.4"}'
        config = ProxyConfig()

        validator = ProxyValidator(mock_http, config)
        proxy = ProxyInfo(host="1.2.3.4", port=1080)
        success, response_time = validator.validate(proxy)

        assert success is True
        assert response_time > 0
        mock_http.get.assert_called_once()

    def test_validate_failure(self):
        """测试验证失败"""
        mock_http = Mock(spec=HttpService)
        mock_http.get.side_effect = Exception("Connection failed")
        config = ProxyConfig()

        validator = ProxyValidator(mock_http, config)
        proxy = ProxyInfo(host="1.2.3.4", port=1080)
        success, response_time = validator.validate(proxy)

        assert success is False
        assert response_time == 0.0

    def test_validate_batch_all_success(self):
        """测试批量验证全部成功"""
        mock_http = Mock(spec=HttpService)
        mock_http.get.return_value = '{"origin": "1.2.3.4"}'
        config = ProxyConfig(max_available=10, check_workers=2)

        validator = ProxyValidator(mock_http, config)
        proxies = [
            ProxyInfo(host="1.2.3.4", port=1080),
            ProxyInfo(host="5.6.7.8", port=1080),
        ]

        result = validator.validate_batch(proxies)

        assert len(result) == 2
        assert all(p.success_count == 1 for p in result)

    def test_validate_batch_partial_success(self):
        """测试批量验证部分成功"""
        mock_http = Mock(spec=HttpService)
        mock_http.get.side_effect = [
            '{"origin": "1.2.3.4"}',
            Exception("Failed"),
            '{"origin": "5.6.7.8"}',
        ]
        config = ProxyConfig(max_available=10, check_workers=1)

        validator = ProxyValidator(mock_http, config)
        proxies = [
            ProxyInfo(host="1.2.3.4", port=1080),
            ProxyInfo(host="5.6.7.8", port=1080),
            ProxyInfo(host="9.10.11.12", port=1080),
        ]

        result = validator.validate_batch(proxies)

        assert len(result) == 2


class TestProxyService:
    """ProxyService 测试类"""

    def test_fetch_proxies_success(self):
        """测试成功获取代理"""
        mock_http = Mock(spec=HttpService)
        mock_http.get.return_value = "1.2.3.4:1080\n5.6.7.8:1080\n"
        mock_validator = Mock(spec=ProxyValidator)
        config = ProxyConfig(
            proxy_sources=[{"url": "http://example.com/proxies.txt", "weight": 1.0}],
            base_sample_size=100,
        )

        service = ProxyService(mock_http, mock_validator, config)
        proxies = service.fetch_proxies()

        assert len(proxies) == 2
        assert all(isinstance(p, ProxyInfo) for p in proxies)

    def test_fetch_proxies_with_weight(self):
        """测试带权重的代理获取"""
        mock_http = Mock(spec=HttpService)
        # 返回足够多的代理以测试采样
        lines = "\n".join([f"1.2.3.{i}:1080" for i in range(300)])
        mock_http.get.return_value = lines
        mock_validator = Mock(spec=ProxyValidator)
        config = ProxyConfig(
            proxy_sources=[{"url": "url1", "weight": 2.0}], base_sample_size=100
        )

        service = ProxyService(mock_http, mock_validator, config)
        proxies = service.fetch_proxies()

        # weight=2.0, base=100, 所以采样 200 个
        assert len(proxies) == 200

    def test_fetch_proxies_deduplication(self):
        """测试代理去重"""
        mock_http = Mock(spec=HttpService)
        mock_http.get.return_value = "1.2.3.4:1080\n1.2.3.4:1080\n"
        mock_validator = Mock(spec=ProxyValidator)
        config = ProxyConfig(
            proxy_sources=[{"url": "url1", "weight": 1.0}], base_sample_size=100
        )

        service = ProxyService(mock_http, mock_validator, config)
        proxies = service.fetch_proxies()

        assert len(proxies) == 1

    def test_get_validated_proxies(self):
        """测试获取并验证代理"""
        mock_http = Mock(spec=HttpService)
        mock_http.get.return_value = "1.2.3.4:1080\n"
        mock_validator = Mock(spec=ProxyValidator)
        mock_validator.validate_batch.return_value = [
            ProxyInfo(host="1.2.3.4", port=1080)
        ]
        config = ProxyConfig(
            proxy_sources=[{"url": "url1", "weight": 1.0}], base_sample_size=100
        )

        service = ProxyService(mock_http, mock_validator, config)
        result = service.get_validated_proxies()

        assert len(result) == 1
        mock_validator.validate_batch.assert_called_once()

    def test_parse_proxy_sources_string_format(self):
        """测试解析字符串格式的代理源"""
        mock_http = Mock(spec=HttpService)
        mock_validator = Mock(spec=ProxyValidator)
        config = ProxyConfig(proxy_sources=["http://example.com/proxies.txt"])

        service = ProxyService(mock_http, mock_validator, config)
        sources = service._parse_proxy_sources()

        assert len(sources) == 1
        assert sources[0].url == "http://example.com/proxies.txt"
        assert sources[0].weight == 1.0

    def test_parse_proxy_sources_dict_format(self):
        """测试解析字典格式的代理源"""
        mock_http = Mock(spec=HttpService)
        mock_validator = Mock(spec=ProxyValidator)
        config = ProxyConfig(
            proxy_sources=[
                {"url": "url1", "weight": 2.0, "proxy_type": "http"},
                {"url": "url2", "weight": 1.5},
            ]
        )

        service = ProxyService(mock_http, mock_validator, config)
        sources = service._parse_proxy_sources()

        assert len(sources) == 2
        assert sources[0].weight == 2.0
        assert sources[0].proxy_type == ProxyType.HTTP
        assert sources[1].weight == 1.5
        assert sources[1].proxy_type == ProxyType.SOCKS5
