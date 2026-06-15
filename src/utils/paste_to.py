"""Paste.to 分享解密辅助函数"""

import base64
from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
import hashlib
import json
from urllib.parse import urlparse
import zlib

from Crypto.Cipher import AES

from core.exceptions import ParseError
from core.interfaces import HttpClient
from utils.passwords import (
    CharsetPasswordStrategy,
    DictionaryPasswordStrategy,
    PasswordAttemptResult,
    brute_force_password,
)

ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


@dataclass(frozen=True)
class PreparedPasteToPayload:
    """Paste.to payload 中与密码无关的预解析数据"""

    adata: list
    spec: list
    iv: bytes
    tag_len: int
    compression: str
    key: bytes
    ciphertext: bytes
    tag: bytes
    aad: bytes


def parse_paste_to_url(
    paste_url: str,
) -> tuple[str, str]:
    """解析 paste.to URL 中的 paste id 和 fragment key"""
    parsed = urlparse(paste_url)
    paste_id = parsed.query
    fragment = parsed.fragment

    if not paste_id:
        raise ParseError("No paste id found", paste_url)
    if not fragment:
        raise ParseError("No paste fragment key found", paste_url)

    return paste_id, fragment


def fetch_paste_to_payload(
    paste_id: str,
    *,
    http_client: HttpClient,
    timeout: int,
) -> dict:
    """获取 paste.to JSON payload"""
    url = f"https://paste.to/?pasteid={paste_id}"
    content = http_client.get(
        url,
        timeout=timeout,
        headers={
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "X-Requested-With": "JSONHttpRequest",
            "User-Agent": "Mozilla/5.0",
        },
    )
    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        raise ParseError(f"Invalid paste.to JSON: {e}", url) from e


def prepare_paste_to_payload(
    payload: dict,
    fragment: str,
) -> PreparedPasteToPayload:
    """预解析 Paste.to payload 中与密码无关的字段"""
    ct = payload["ct"]
    adata = payload["adata"]
    spec = adata[0] if isinstance(adata[0], list) else adata

    iv = base64.b64decode(spec[0])
    tag_len = int(spec[4]) // 8
    compression = spec[7]

    key = decode_paste_to_key(fragment)
    encrypted = base64.b64decode(ct)
    ciphertext = encrypted[:-tag_len]
    tag = encrypted[-tag_len:]

    return PreparedPasteToPayload(
        adata=adata,
        spec=spec,
        iv=iv,
        tag_len=tag_len,
        compression=compression,
        key=key,
        ciphertext=ciphertext,
        tag=tag,
        aad=js_json_stringify(adata),
    )


def decrypt_prepared_paste_to_payload(
    prepared: PreparedPasteToPayload,
    password: str,
) -> str:
    """用单个密码尝试解密已预解析的 Paste.to payload"""
    aes_key = derive_paste_to_key(prepared.key, password, prepared.spec)

    cipher = AES.new(aes_key, AES.MODE_GCM, nonce=prepared.iv, mac_len=prepared.tag_len)
    cipher.update(prepared.aad)

    plain = cipher.decrypt_and_verify(prepared.ciphertext, prepared.tag)
    if prepared.compression == "zlib":
        try:
            plain = zlib.decompress(plain)
        except zlib.error:
            plain = zlib.decompress(plain, -zlib.MAX_WBITS)

    return plain.decode("utf-8")


def decode_paste_to_key(fragment: str) -> bytes:
    """解码 Paste.to fragment key"""
    fragment = fragment.lstrip("#")
    fragment = fragment.split("&", 1)[0]
    fragment = fragment.split("\\u0026", 1)[0]

    key = b58decode(fragment)
    if len(key) < 32:
        key = b"\x00" * (32 - len(key)) + key

    return key


def derive_paste_to_key(key: bytes, password: str, spec: list) -> bytes:
    """根据 Paste.to KDF 参数派生 AES key"""
    salt = base64.b64decode(spec[1])
    iterations = int(spec[2])
    key_len = int(spec[3]) // 8

    raw = key
    if password:
        raw += js_string_to_bytes(password)

    return hashlib.pbkdf2_hmac("sha256", raw, salt, iterations, dklen=key_len)


def b58decode(value: str) -> bytes:
    """Base58 解码"""
    num = 0
    for char in value:
        num *= 58
        num += ALPHABET.index(char)

    combined = num.to_bytes((num.bit_length() + 7) // 8, byteorder="big")
    n_pad = len(value) - len(value.lstrip("1"))
    return b"\x00" * n_pad + combined


def js_string_to_bytes(value: str) -> bytes:
    """模拟 JavaScript 字符串到字节的转换"""
    return bytes(ord(ch) & 0xFF for ch in value)


def js_json_stringify(obj) -> bytes:
    """生成与 Paste.to 前端一致的 JSON AAD 字节"""
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def brute_force_payload(
    max_workers: int,
    *,
    password_strategy: (
        CharsetPasswordStrategy | DictionaryPasswordStrategy | None
    ) = None,
    decrypt_prepared: Callable[[str], str],
) -> PasswordAttemptResult:
    """按候选策略爆破解密 Paste.to payload"""
    return brute_force_password(
        max_workers=max_workers,
        password_strategy=password_strategy,
        try_password=decrypt_prepared,
    )


def decrypt_paste_to_url(
    paste_url: str,
    *,
    http_client: HttpClient,
    password: str | None,
    timeout: int,
    max_workers: int,
    password_strategy: (
        CharsetPasswordStrategy | DictionaryPasswordStrategy | None
    ) = None,
) -> PasswordAttemptResult:
    """根据 paste.to URL 获取 payload，并按密码或爆破策略解密"""
    paste_id, fragment = parse_paste_to_url(paste_url)
    payload = fetch_paste_to_payload(
        paste_id,
        http_client=http_client,
        timeout=timeout,
    )
    prepared = prepare_paste_to_payload(payload, fragment)
    if password:
        data = decrypt_prepared_paste_to_payload(prepared, password)
        return PasswordAttemptResult(password=password, content=data)

    decrypt_prepared = partial(decrypt_prepared_paste_to_payload, prepared)

    return brute_force_payload(
        max_workers=max_workers,
        password_strategy=password_strategy,
        decrypt_prepared=decrypt_prepared,
    )
