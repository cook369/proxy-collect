import base64
import logging
import re
import urllib.parse
from lxml import etree
from Crypto.Cipher import AES
from Crypto.Hash import MD5
from Crypto.Util.Padding import unpad
from .base import BaseCollector, register_collector


@register_collector
class CollectorYudou(BaseCollector):
    name = "yudou"
    home_page = "https://www.yudou123.top/"
    AES_PATTERN = r"U2FsdGVkX1[0-9A-Za-z+/=]+"
    PASSWORD_RANGE = (1000, 9999)

    def evp_bytes_to_key(
        self, password: str, salt: bytes, key_len: int = 32, iv_len: int = 16
    ):
        derived = b""
        prev = b""
        pw_bytes = password.encode("utf-8")
        while len(derived) < key_len + iv_len:
            prev = MD5.new(prev + pw_bytes + salt).digest()
            derived += prev
        return derived[:key_len], derived[key_len : key_len + iv_len]

    def decrypt(self, ciphertext: str, password: str) -> str:
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
        for pwd in range(self.PASSWORD_RANGE[0], self.PASSWORD_RANGE[1] + 1):
            try:
                return urllib.parse.unquote(self.decrypt(encrypted_data, str(pwd)))
            except Exception:
                continue
        raise ValueError("Failed to brute-force the encryption password.")

    def get_today_url(self, home_page: str) -> str:
        home_etree = etree.HTML(home_page)
        links = home_etree.xpath('//*[@id="main"]//a/@href')
        if not links:
            raise ValueError("No links found on homepage.")
        return links[0]

    def parse_urls(self, today_page: str) -> list[tuple[str, str]]:
        page_etree = etree.HTML(today_page)
        scripts = page_etree.xpath("//script[contains(text(), 'U2FsdGVkX1')]/text()")
        if not scripts:
            raise ValueError("No encryption scripts found.")
        match = re.search(self.AES_PATTERN, scripts[0])
        if not match:
            raise ValueError("Failed to extract encryption data.")
        encrypted_data = match.group(0)
        decrypted_data = self.brute_force_password(encrypted_data)
        rules = {
            "clash.yaml": r"https?://[^\s'\"<>]+?\.(?:yaml)",
            "v2ray.txt": r"https?://[^\s'\"<>]+?\.(?:txt)",
        }
        urls: list[tuple[str, str]] = []
        for filename, regex_expr in rules.items():
            hrefs = re.findall(regex_expr, decrypted_data)
            if hrefs:
                urls.append((filename, str(hrefs[0])))
        return urls

    def get_download_urls(self) -> list[tuple[str, str]]:
        home_page = self.fetch_html(self.home_page)
        today_url = self.get_today_url(home_page)
        if not today_url:
            return []
        logging.info(f"Today's URL: {today_url}")
        today_page = self.fetch_html(today_url)
        return self.parse_urls(today_page)
