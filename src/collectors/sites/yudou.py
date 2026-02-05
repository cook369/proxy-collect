"""Yudou 采集器"""

import base64
import re
import urllib.parse
from typing import Optional
from Crypto.Cipher import AES
from Crypto.Hash import MD5
from Crypto.Util.Padding import unpad

from collectors.base import BaseCollector, register_collector
from collectors.mixins import TwoStepCollectorMixin, HtmlParser
from core.models import DownloadTask


@register_collector
class YudouCollector(TwoStepCollectorMixin, BaseCollector):
    """Yudou 站点采集器（包含 AES 解密功能）"""

    name = "yudou"
    home_page = "https://www.yudou789.top/"
    AES_PATTERN = r"U2FsdGVkX1[0-9A-Za-z+/=]+"
    PASSWORD_RANGE = (1000, 9999)

    def evp_bytes_to_key(
        self, password: str, salt: bytes, key_len: int = 32, iv_len: int = 16
    ):
        """从密码和盐生成密钥和 IV"""
        derived = b""
        prev = b""
        pw_bytes = password.encode("utf-8")
        while len(derived) < key_len + iv_len:
            prev = MD5.new(prev + pw_bytes + salt).digest()
            derived += prev
        return derived[:key_len], derived[key_len : key_len + iv_len]

    def decrypt(self, ciphertext: str, password: str) -> str:
        """AES 解密"""
        data = base64.b64decode(ciphertext)
        if not data.startswith(b"Salted__"):
            raise ValueError("Ciphertext missing 'Salted__'")
        salt = data[8:16]
        cipher_bytes = data[16:]
        key, iv = self.evp_bytes_to_key(password, salt)
        cipher = AES.new(key, AES.MODE_CBC, iv)
        decrypted = unpad(cipher.decrypt(cipher_bytes), AES.block_size)
        return decrypted.decode("utf-8")

    def brute_force_password(self, encrypted_data: str) -> str:
        """暴力破解密码"""
        for pwd in range(self.PASSWORD_RANGE[0], self.PASSWORD_RANGE[1] + 1):
            try:
                return urllib.parse.unquote(self.decrypt(encrypted_data, str(pwd)))
            except Exception:
                continue
        raise ValueError("Failed to brute-force the encryption password.")

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
