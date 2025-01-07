import base64
import os
import urllib.parse
import sys
import logging
import re

import requests
from Crypto.Cipher import AES
from Crypto.Hash import MD5
from Crypto.Util.Padding import unpad
from lxml import etree

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

YUDOU_HOME = "https://www.yudou66.com/"
OUTPUT_DIR = "../output/"


def decrypt(ciphertext, password):
    """Decrypts the given ciphertext using the provided password."""
    try:
        encrypt_data = base64.b64decode(ciphertext)
        salt = encrypt_data[8:16]
        ciphertext = encrypt_data[16:]

        # Derive the key and IV
        derived = b""
        while len(derived) < 48:
            hasher = MD5.new()
            hasher.update(derived[-16:] + password.encode("utf-8") + salt)
            derived += hasher.digest()

        key, iv = derived[:32], derived[32:48]
        cipher = AES.new(key, AES.MODE_CBC, iv)
        decrypted = unpad(cipher.decrypt(ciphertext), 16)
        return decrypted.decode("utf-8")
    except Exception as e:
        raise ValueError(f"Decryption failed: {e}")


def fetch_html(url):
    """Fetches and parses HTML content from the given URL."""
    response = requests.get(url)
    response.raise_for_status()
    return etree.HTML(response.text)


def extract_encryption_script(scripts):
    """Extracts the encryption data from the provided script elements."""
    for script in scripts:
        if script.text and "encryption" in script.text:
            lines = script.text.split("\n")
            for i, line in enumerate(lines):
                if "encryption" in line:
                    return lines[i + 1].split('"')[1]
    return ""


def brute_force_password(encrypted_data):
    """Attempts to brute-force the password to decrypt the data."""
    for pwd in range(1000, 10000):
        try:
            decoded_data = decrypt(encrypted_data, str(pwd))
            decrypted_data = urllib.parse.unquote(decoded_data)
            return decrypted_data
        except ValueError:
            continue
    raise ValueError("Failed to brute-force the encryption password.")


def parse_urls(decrypted_data):
    """Parses URLs from the decrypted data."""
    matches = re.finditer(r"http.*\.(txt|yaml)", decrypted_data)
    urls = [match.group(0) for match in matches]
    if not urls:
        raise ValueError("No URLs found in the decrypted data.")
    return urls


def download_files(urls):
    """Downloads files from the given URLs and saves them locally."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    for url in urls:
        logging.info(f"Downloading from {url}")
        response = requests.get(url)
        response.raise_for_status()

        # Determine output file name
        file_name = "v2ray.txt" if url.endswith("txt") else "clash.yaml" if url.endswith("yaml") else None
        if file_name:
            output_path = os.path.join(OUTPUT_DIR, file_name)
            logging.info(f"Saving to {output_path}")
            with open(output_path, "w", encoding="utf-8") as file:
                file.write(response.text)


def main():
    try:
        # Fetch homepage and extract today's URL
        home_etree = fetch_html(YUDOU_HOME)
        hrefs = home_etree.xpath('//*[@id="main"]//a/@href')
        if not hrefs:
            raise ValueError("No links found on the homepage.")

        today_url = hrefs[0]
        logging.info(f"Reading URL: {today_url}")

        # Fetch today's page and extract encryption script
        today_etree = fetch_html(today_url)
        scripts = today_etree.xpath("//script")
        encryption = extract_encryption_script(scripts)
        if not encryption:
            raise ValueError("Failed to extract encryption data.")

        logging.info("Encryption data retrieved successfully.")

        # Decrypt and parse URLs
        decrypted_data = brute_force_password(encryption)
        logging.info("Decryption successful.")

        urls = parse_urls(decrypted_data)
        logging.info("URLs parsed successfully.")

        # Download files from the parsed URLs
        download_files(urls)
        logging.info("All files downloaded successfully.")

    except Exception as e:
        logging.error(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
