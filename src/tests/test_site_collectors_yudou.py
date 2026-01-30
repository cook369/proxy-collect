"""Yudou 采集器测试 - 包含 AES 解密功能"""
import pytest
from unittest.mock import Mock
import base64

from collectors.sites.yudou import YudouCollector
from core.interfaces import HttpClient


class TestYudouCollector:
    """YudouCollector 测试类"""

    def test_evp_bytes_to_key(self):
        """测试密钥和 IV 生成"""
        mock_http_client = Mock(spec=HttpClient)
        collector = YudouCollector(http_client=mock_http_client)

        password = "1234"
        salt = b"12345678"
        key, iv = collector.evp_bytes_to_key(password, salt)

        assert len(key) == 32  # 256-bit key
        assert len(iv) == 16   # 128-bit IV
        assert isinstance(key, bytes)
        assert isinstance(iv, bytes)

    def test_decrypt_invalid_ciphertext(self):
        """测试解密无效的密文"""
        mock_http_client = Mock(spec=HttpClient)
        collector = YudouCollector(http_client=mock_http_client)

        # 测试无效的密文格式（有效的 base64 但不包含 "Salted__"）
        # "test" 的 base64 编码
        with pytest.raises(ValueError, match="Ciphertext missing 'Salted__'"):
            collector.decrypt("dGVzdA==", "1234")

    def test_get_today_url(self):
        """测试从首页获取今日链接"""
        mock_http_client = Mock(spec=HttpClient)
        collector = YudouCollector(http_client=mock_http_client)

        home_html = """
        <html>
            <body>
                <a href="https://www.yudou789.top/2026/01/today.html">免费精选节点</a>
            </body>
        </html>
        """

        today_url = collector.get_today_url(home_html)
        assert today_url == "https://www.yudou789.top/2026/01/today.html"

    def test_get_today_url_not_found(self):
        """测试首页未找到链接的情况"""
        mock_http_client = Mock(spec=HttpClient)
        collector = YudouCollector(http_client=mock_http_client)

        home_html = "<html><body>No links</body></html>"

        with pytest.raises(ValueError, match="No links found on homepage"):
            collector.get_today_url(home_html)

    def test_parse_download_urls(self):
        """测试解析下载链接"""
        mock_http_client = Mock(spec=HttpClient)
        collector = YudouCollector(http_client=mock_http_client)

        today_html = """
        <html>
            <body>
                <div>
                    <p>免费节点订阅链接</p>
                    <p>Clash: https://example.com/clash.yaml</p>
                    <p>V2Ray: https://example.com/v2ray.txt</p>
                </div>
            </body>
        </html>
        """

        urls = collector.parse_download_urls(today_html)

        assert len(urls) == 2
        assert ("clash.yaml", "https://example.com/clash.yaml") in urls
        assert ("v2ray.txt", "https://example.com/v2ray.txt") in urls

    def test_parse_download_urls_not_found(self):
        """测试未找到下载链接的情况"""
        mock_http_client = Mock(spec=HttpClient)
        collector = YudouCollector(http_client=mock_http_client)

        today_html = "<html><body>No content</body></html>"

        with pytest.raises(ValueError, match="No elements found"):
            collector.parse_download_urls(today_html)

    def test_collector_name(self):
        """测试采集器名称"""
        mock_http_client = Mock(spec=HttpClient)
        collector = YudouCollector(http_client=mock_http_client)

        assert collector.name == "yudou"
        assert collector.home_page == "https://www.yudou789.top/"

    def test_aes_pattern(self):
        """测试 AES 密文模式"""
        mock_http_client = Mock(spec=HttpClient)
        collector = YudouCollector(http_client=mock_http_client)

        # 测试 AES 密文模式匹配
        import re
        pattern = collector.AES_PATTERN

        # 有效的 AES 密文
        valid_ciphertext = "U2FsdGVkX1+abc123def456ghi789="
        assert re.match(pattern, valid_ciphertext)

        # 无效的密文
        invalid_ciphertext = "InvalidCiphertext"
        assert not re.match(pattern, invalid_ciphertext)

    def test_password_range(self):
        """测试密码范围"""
        mock_http_client = Mock(spec=HttpClient)
        collector = YudouCollector(http_client=mock_http_client)

        assert collector.PASSWORD_RANGE == (1000, 9999)
