import base64
import os
import urllib.parse
import urllib3

import sys
import logging
import re

import requests
from Crypto.Cipher import AES
from Crypto.Hash import MD5
from Crypto.Util.Padding import unpad
from lxml import etree

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

YUDOU_HOME = "https://www.yudou123.top/"
AES_PATTERN = r"U2FsdGVkX1[0-9A-Za-z+/=]+"
OUTPUT_DIR = "../output/"

session = requests.Session()
session.verify = False  # 禁用证书验证


def decrypt(ciphertext: str, password: str) -> str:
    """Decrypt AES-encrypted data using the given password."""
    try:
        encrypt_data = base64.b64decode(ciphertext)
        salt = encrypt_data[8:16]
        cipher_bytes = encrypt_data[16:]

        # Derive key and IV
        derived = b""
        while len(derived) < 48:
            hasher = MD5.new()
            hasher.update(derived[-16:] + password.encode("utf-8") + salt)
            derived += hasher.digest()
        key, iv = derived[:32], derived[32:48]

        cipher = AES.new(key, AES.MODE_CBC, iv)
        decrypted = unpad(cipher.decrypt(cipher_bytes), 16)
        return decrypted.decode("utf-8")
    except Exception as e:
        raise ValueError(f"Decryption failed: {e}")


def fetch_html(url: str) -> etree._Element:
    """Fetch and parse HTML from a URL."""
    try:
        response = session.get(url)
        response.raise_for_status()
        return etree.HTML(response.text)
    except Exception as e:
        raise ConnectionError(f"Failed to fetch URL {url}: {e}")


def extract_encryption_data(page_etree: etree._Element) -> str:
    """Extract AES-encrypted data from a page's scripts."""
    scripts = page_etree.xpath("//script[contains(text(), 'U2FsdGVkX1')]/text()")
    if not scripts:
        raise ValueError("No encryption scripts found.")
    matches = re.findall(AES_PATTERN, scripts[0])
    if not matches:
        raise ValueError("Failed to extract encryption data from script.")
    return matches[0]


def brute_force_password(
    encrypted_data: str, start: int = 1000, end: int = 9999
) -> str:
    """Brute-force AES password (4-digit numeric)."""
    for pwd in range(start, end + 1):
        try:
            decoded = decrypt(encrypted_data, str(pwd))
            return urllib.parse.unquote(decoded)
        except ValueError:
            continue
    raise ValueError("Failed to brute-force the encryption password.")


def parse_urls(decrypted_data: str) -> list[str]:
    """Extract URLs ending with .txt or .yaml from decrypted data."""
    urls = re.findall(r"https?://[^\s'\"<>]+?\.(?:txt|yaml)", decrypted_data)
    if not urls:
        raise ValueError("No downloadable URLs found.")
    return urls


def download_files(urls: list[str]):
    """Download files to the output directory."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    for url in urls:
        logging.info(f"Downloading: {url}")
        try:
            resp = session.get(url)
            resp.raise_for_status()
            ext = url.split(".")[-1]
            file_name = "v2ray.txt" if ext == "txt" else "clash.yaml"
            path = os.path.join(OUTPUT_DIR, file_name)
            with open(path, "w", encoding="utf-8") as f:
                f.write(resp.text)
            logging.info(f"Saved to: {path}")
        except Exception as e:
            logging.error(f"Failed to download {url}: {e}")


def main():
    try:
        home_etree = fetch_html(YUDOU_HOME)
        links = home_etree.xpath('//*[@id="main"]//a/@href')
        if not links:
            raise ValueError("No links found on homepage.")
        today_url = links[0]
        logging.info(f"Today's URL: {today_url}")

        today_etree = fetch_html(today_url)
        encrypted_data = extract_encryption_data(today_etree)
        logging.info("Encrypted data extracted.")

        decrypted_data = brute_force_password(encrypted_data)
        logging.info("Decryption successful.")

        urls = parse_urls(decrypted_data)
        logging.info(f"Found {len(urls)} URLs.")

        download_files(urls)
        logging.info("All files downloaded successfully.")

    except Exception as e:
        logging.error(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
