"""Paste.to 分享解密辅助函数"""

import base64
from collections.abc import Callable
from collections.abc import Iterable, Iterator
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
import hashlib
from itertools import product
import json
from queue import Empty, Full, Queue
import threading
from urllib.parse import urlparse
import zlib

from Crypto.Cipher import AES

from core.exceptions import ParseError
from core.interfaces import HttpClient

ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
DEFAULT_PASSWORD_CHARSET = "0123456789"
DEFAULT_PASSWORD_LENGTH = 4
PASSWORD_QUEUE_FACTOR = 100
SENTINEL = object()


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


@dataclass(frozen=True)
class PasteToDecryptResult:
    """Paste.to 解密结果"""

    password: str
    content: str


@dataclass(frozen=True)
class CharsetPasswordStrategy:
    """基于字符集和位数的密码生成策略"""

    length: int = DEFAULT_PASSWORD_LENGTH
    charset: str = DEFAULT_PASSWORD_CHARSET

    def __post_init__(self) -> None:
        if self.length < 1:
            raise ParseError("Paste.to password length must be greater than 0")
        if not self.charset:
            raise ParseError("Paste.to password charset must not be empty")

    def iter_passwords(self) -> Iterator[str]:
        """按组合空间顺序流式生成密码"""
        for chars in product(self.charset, repeat=self.length):
            yield "".join(chars)


@dataclass(frozen=True)
class DictionaryPasswordStrategy:
    """基于外部密码本的密码生成策略"""

    candidates: Iterable[str]

    def iter_passwords(self) -> Iterator[str]:
        """按给定顺序流式生成密码"""
        return iter(self.candidates)


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


def _decrypt_password_queue(
    prepared: PreparedPasteToPayload,
    password_queue: Queue,
    stop_event: threading.Event,
    decrypt_prepared: Callable[[PreparedPasteToPayload, str], str],
) -> tuple[str, str] | None:
    """从密码队列消费候选并尝试解密"""
    while True:
        item = password_queue.get()
        if item is SENTINEL:
            return None

        if stop_event.is_set():
            continue

        password = str(item)
        try:
            result = decrypt_prepared(prepared, password)
            stop_event.set()
            return password, result
        except Exception:
            continue

    return None


def _drain_password_queue(password_queue: Queue) -> None:
    """清空待消费密码，避免已找到结果后生产者阻塞在哨兵入队"""
    while True:
        try:
            password_queue.get_nowait()
        except Empty:
            return


def _put_worker_sentinels(
    password_queue: Queue,
    workers: int,
) -> None:
    """给每个 worker 发送退出哨兵"""
    for _ in range(workers):
        while True:
            try:
                password_queue.put(SENTINEL, timeout=0.1)
                break
            except Full:
                _drain_password_queue(password_queue)


def brute_force_paste_to_payload(
    prepared: PreparedPasteToPayload,
    max_workers: int,
    *,
    password_strategy: (
        CharsetPasswordStrategy | DictionaryPasswordStrategy | None
    ) = None,
) -> PasteToDecryptResult:
    """按模块内密码策略爆破解密 Paste.to payload"""
    strategy = password_strategy or CharsetPasswordStrategy()
    workers = max(1, max_workers)
    password_queue = Queue(maxsize=workers * PASSWORD_QUEUE_FACTOR)
    stop_event = threading.Event()

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [
            executor.submit(
                _decrypt_password_queue,
                prepared,
                password_queue,
                stop_event,
                decrypt_prepared_paste_to_payload,
            )
            for _ in range(workers)
        ]

        for password in strategy.iter_passwords():
            while not stop_event.is_set():
                try:
                    password_queue.put(password, timeout=0.1)
                    break
                except Full:
                    continue
            if stop_event.is_set():
                break

        if stop_event.is_set():
            _drain_password_queue(password_queue)
        _put_worker_sentinels(password_queue, workers)

        for future in as_completed(futures):
            try:
                found = future.result()
            except Exception:
                continue

            if not found:
                continue

            password, result = found
            stop_event.set()
            for pending in futures:
                if pending != future:
                    pending.cancel()
            return PasteToDecryptResult(password=password, content=result)

    raise ParseError(
        "Failed to brute-force paste.to password",
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
) -> PasteToDecryptResult:
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
        return PasteToDecryptResult(password=password, content=data)

    return brute_force_paste_to_payload(
        prepared=prepared,
        max_workers=max_workers,
        password_strategy=password_strategy,
    )
