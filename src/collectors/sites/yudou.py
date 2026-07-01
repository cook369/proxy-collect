"""Yudou 采集器（异步版本）"""

import base64
import re
import urllib.parse
from typing import Optional
from Crypto.Cipher import AES
from Crypto.Hash import MD5
from Crypto.Util.Padding import unpad

from collectors.base import BaseCollector, register_collector
from collectors.mixins import TwoStepCollectorMixin, HtmlParser
from config.settings import default_config
from core.models import DownloadTask
from utils.passwords import CharsetPasswordStrategy, brute_force_password


@register_collector
class YudouCollector(TwoStepCollectorMixin, BaseCollector):
    """Yudou 站点采集器（包含 AES 解密功能）"""

    name = "yudou"
    home_page = "https://www.yudou789.top/"
    AES_PATTERN = r"U2FsdGVkX1[0-9A-Za-z+/=]+"
    PASSWORD_RANGE = (1000, 9999)

    # ── AES 解密（站点特有算法） ──

    @staticmethod
    def evp_bytes_to_key(
        password: str, salt: bytes, key_len: int = 32, iv_len: int = 16
    ) -> tuple[bytes, bytes]:
        """从密码和盐生成密钥和 IV (EVP_BytesToKey 兼容)"""
        derived = b""
        prev = b""
        pw_bytes = password.encode("utf-8")
        while len(derived) < key_len + iv_len:
            prev = MD5.new(prev + pw_bytes + salt).digest()
            derived += prev
        return derived[:key_len], derived[key_len : key_len + iv_len]

    def decrypt(self, ciphertext: str, password: str) -> str:
        """AES 解密（CBC 模式，OpenSSL Salted__ 格式）"""
        data = base64.b64decode(ciphertext)
        if not data.startswith(b"Salted__"):
            raise ValueError("Ciphertext missing 'Salted__'")
        salt = data[8:16]
        cipher_bytes = data[16:]
        key, iv = self.evp_bytes_to_key(password, salt)
        cipher = AES.new(key, AES.MODE_CBC, iv)
        decrypted = unpad(cipher.decrypt(cipher_bytes), AES.block_size)
        return urllib.parse.unquote(decrypted.decode("utf-8"))

    async def brute_force_decrypt(self, encrypted_data: str) -> str:
        """并发暴力破解 AES 加密密码（4 位数字）"""
        strategy = CharsetPasswordStrategy(
            length=4,
            charset="0123456789",
        )
        result = await brute_force_password(
            max_workers=default_config.collector.http_password_workers,
            password_strategy=strategy,
            try_password=lambda pwd: self.decrypt(encrypted_data, pwd),
        )
        return result.content

    # ── TwoStep 采集流程 ──

    def get_today_url(self, home_html: str) -> Optional[str]:
        """从首页获取今日链接"""
        parser = HtmlParser(home_html, self.name)
        return parser.xpath('//a[text()[contains(., "免费精选节点")]]/@href')

    def parse_download_tasks(self, today_html: str) -> list[DownloadTask]:
        """从今日页面解析下载任务"""
        parser = HtmlParser(today_html, self.name)
        sub_content_data = parser.xpath(
            'string(//div[p[contains(., "免费节点订阅链接")]])',
            default="",
        )
        if not sub_content_data:
            return []

        rules = {
            "clash.yaml": r"https?://[^\s'\"<>]+?\.(?:yaml)",
            "v2ray.txt": r"https?://[^\s'\"<>]+?\.(?:txt)",
        }

        tasks: list[DownloadTask] = []
        for filename, regex_expr in rules.items():
            hrefs = re.findall(regex_expr, sub_content_data)
            if hrefs:
                tasks.append(DownloadTask(filename=filename, url=str(hrefs[0])))

        return tasks
