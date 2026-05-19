import base64
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
import hashlib
import html
import json
import logging
import os
import re
import threading
import zlib
from urllib.parse import unquote, urlparse

from Crypto.Cipher import AES

from collectors.base import BaseCollector, register_collector
from config.settings import default_config
from core.exceptions import ParseError
from core.models import DownloadTask
from utils.check import check_html_contains

ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
LATEST_VIDEO_KEYWORDS = ("最新节点分享", "免费节点")


@dataclass(frozen=True)
class PreparedPrivateBinPayload:
    """PrivateBin payload 中与密码无关的预解析数据"""

    adata: list
    spec: list
    iv: bytes
    tag_len: int
    compression: str
    key: bytes
    ciphertext: bytes
    tag: bytes
    aad: bytes


@register_collector
class XQKXWCollector(BaseCollector):
    """小青科学网采集器"""

    name = "xqkxw"
    home_page = (
        "https://www.youtube.com/playlist?list=PLuUYvtnZVIVI79GPS7VvxhYYm0x2jjuOZ"
    )
    password_workers = min(32, (os.cpu_count() or 4) * 2)
    password_space_size = 10000

    def get_download_tasks(self) -> list[DownloadTask]:
        """从 YouTube 最新视频中的 paste.to 分享提取订阅任务"""

        check_playlist = check_html_contains("playlistVideoRenderer")
        if not self.today_page:
            playlist_html = self.fetch_html(
                self.home_page, timeout=10, check_html=check_playlist
            )
            self.today_page = self.get_today_url(playlist_html)
        self.skip_if_cached()

        video_html = self.fetch_html(self.today_page, timeout=10)
        paste_url = self.extract_paste_url(video_html)

        logging.info(f"[{self.name}] try decrypt passwd")
        share_content = self.fetch_decrypted_share(paste_url)
        return self.parse_subscription_tasks(share_content)

    def get_today_url(self, home_html: str) -> str:
        """从播放列表页面获取最新视频 URL"""
        return self.extract_latest_video_url(home_html)

    def extract_latest_video_url(self, playlist_html: str) -> str:
        """从 YouTube 播放列表页面提取最新视频 URL"""
        for video_id, title in self.iter_playlist_videos(playlist_html):
            if self.is_target_video_title(title):
                return f"https://www.youtube.com/watch?v={video_id}"

        raise ParseError(
            "No latest xqkxw video found",
            self.home_page,
            self.name,
        )

    def iter_playlist_videos(self, playlist_html: str):
        """按播放列表顺序迭代视频 ID 和标题"""
        yield from self.iter_compact_playlist_videos(playlist_html)
        yield from self.iter_initial_data_playlist_videos(playlist_html)

    def iter_compact_playlist_videos(self, playlist_html: str):
        """从 YouTube 压缩 JSON 片段中提取播放列表视频"""
        pattern = re.compile(
            r'"playlistVideoRenderer"\s*:\s*\{\s*"videoId"\s*:\s*"(?P<id>[^"]+)".*?'
            r'"title"\s*:\s*\{\s*"runs"\s*:\s*\[\s*\{\s*"text"\s*:\s*"(?P<title>.*?)"\s*\}\s*\]',
            re.DOTALL,
        )

        for match in pattern.finditer(playlist_html):
            yield match.group("id"), html.unescape(match.group("title"))

    def iter_initial_data_playlist_videos(self, playlist_html: str):
        """从 ytInitialData JSON 中提取播放列表视频"""
        match = re.search(
            r"var ytInitialData\s*=\s*({.*?});</script>",
            playlist_html,
            re.DOTALL,
        )
        if not match:
            raise ParseError(
                "No latest YouTube video watch URL found",
                self.home_page,
                self.name,
            )

        try:
            data = json.loads(match.group(1))
            contents = data["contents"]["twoColumnBrowseResultsRenderer"]["tabs"][0][
                "tabRenderer"
            ]["content"]["sectionListRenderer"]["contents"][0]["itemSectionRenderer"][
                "contents"
            ][0]["playlistVideoListRenderer"]["contents"]
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as e:
            raise ParseError(
                f"Failed to parse latest YouTube video: {e}",
                self.home_page,
                self.name,
            ) from e

        for item in contents:
            renderer = item.get("playlistVideoRenderer")
            video = self.parse_playlist_video_renderer(renderer)
            if video:
                yield video

    def parse_playlist_video_renderer(
        self, renderer: dict | None
    ) -> tuple[str, str] | None:
        """从 playlistVideoRenderer 提取视频 ID 和标题"""
        if not renderer:
            return None

        video_id = renderer.get("videoId")
        title_obj = renderer.get("title") or {}
        if "runs" in title_obj:
            title = "".join(item.get("text", "") for item in title_obj["runs"])
        else:
            title = title_obj.get("simpleText", "")

        if not video_id or not title:
            return None
        return video_id, html.unescape(title)

    def is_target_video_title(self, title: str) -> bool:
        """判断是否为小青科学网最新节点分享视频"""

        return all(keyword in title for keyword in LATEST_VIDEO_KEYWORDS)

    def extract_paste_url(self, video_html: str) -> str:
        """从 YouTube 视频页提取 paste.to 分享 URL"""
        matches = re.findall(
            r"q=(https%3A%2F%2Fpaste\.to%2F.+?)(?:\\u0026|&)",
            video_html,
        )
        if not matches:
            raise ParseError("No paste.to URL found", self.today_page, self.name)

        return unquote(matches[0])

    def fetch_decrypted_share(self, paste_url: str) -> str:
        """获取并解密 paste.to 私密分享内容"""
        paste_id, fragment = self.parse_paste_url(paste_url)
        payload = self.fetch_paste_json(paste_id)
        return self.brute_force_decrypt(payload, fragment)

    def brute_force_decrypt(self, payload: dict, fragment: str) -> str:
        """尝试 0000-9999 四位数字密码解密分享内容"""
        prepared = self.prepare_privatebin_payload(payload, fragment)
        stop_event = threading.Event()
        with ThreadPoolExecutor(max_workers=self.password_workers) as executor:
            futures = {
                executor.submit(
                    self.decrypt_password_range,
                    prepared,
                    start,
                    end,
                    stop_event,
                ): (start, end)
                for start, end in self.iter_password_ranges()
            }

            for future in as_completed(futures):
                try:
                    found = future.result()
                except Exception:
                    continue

                if not found:
                    continue

                password, result = found
                logging.info(f"[{self.name}] found correct password: {password}")
                stop_event.set()
                for pending in futures:
                    if pending != future:
                        pending.cancel()
                return result

        raise ParseError(
            "Failed to brute-force paste.to password",
            self.today_page or self.home_page,
            self.name,
        )

    def iter_password_ranges(self):
        """把四位数字密码空间切分给少量 worker，避免创建 10000 个任务"""
        total = self.password_space_size
        workers = max(1, min(self.password_workers, total))
        chunk_size = (total + workers - 1) // workers

        for start in range(0, total, chunk_size):
            yield start, min(start + chunk_size, total)

    def decrypt_password_range(
        self,
        prepared: PreparedPrivateBinPayload,
        start: int,
        end: int,
        stop_event: threading.Event,
    ) -> tuple[str, str] | None:
        """在一个数字区间内尝试密码"""
        for num in range(start, end):
            if stop_event.is_set():
                return None

            password = f"{num:04d}"
            try:
                return password, self.decrypt_prepared_payload(prepared, password)
            except Exception:
                continue

        return None

    def fetch_paste_json(self, paste_id: str) -> dict:
        """获取 paste.to JSON payload"""
        url = f"https://paste.to/?pasteid={paste_id}"
        content = self.http_client.get(
            url,
            timeout=default_config.collector.fetch_timeout,
            headers={
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "X-Requested-With": "JSONHttpRequest",
                "User-Agent": "Mozilla/5.0",
            },
        )
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            raise ParseError(f"Invalid paste.to JSON: {e}", url, self.name) from e

    def parse_paste_url(self, paste_url: str) -> tuple[str, str]:
        """解析 paste.to URL 中的 paste id 和 fragment key"""
        parsed = urlparse(paste_url)
        paste_id = parsed.query
        fragment = parsed.fragment

        if not paste_id:
            raise ParseError("No paste id found", paste_url, self.name)
        if not fragment:
            raise ParseError("No paste fragment key found", paste_url, self.name)

        return paste_id, fragment

    def parse_subscription_tasks(self, content: str) -> list[DownloadTask]:
        """从解密后的分享内容提取订阅链接"""
        patterns = {
            "v2ray.txt": r"V2ray.*?(https?://[^\s<>'\"，）)]+?\.txt)",
            "clash.yaml": r"clash.*?(https?://[^\s<>'\"，）)]+?\.yaml)",
        }

        tasks: list[DownloadTask] = []
        for filename, pattern in patterns.items():
            match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
            if match:
                tasks.append(DownloadTask(filename=filename, url=match.group(1)))

        return tasks

    def decrypt_privatebin_payload(
        self, payload: dict, fragment: str, password: str = ""
    ) -> str:
        """解密 PrivateBin/Paste.to payload"""
        prepared = self.prepare_privatebin_payload(payload, fragment)
        return self.decrypt_prepared_payload(prepared, password)

    def prepare_privatebin_payload(
        self, payload: dict, fragment: str
    ) -> PreparedPrivateBinPayload:
        """预解析 PrivateBin payload 中与密码无关的字段"""
        ct = payload["ct"]
        adata = payload["adata"]
        spec = adata[0] if isinstance(adata[0], list) else adata

        iv = base64.b64decode(spec[0])
        tag_len = int(spec[4]) // 8
        compression = spec[7]

        key = self.decode_privatebin_key(fragment)
        encrypted = base64.b64decode(ct)
        ciphertext = encrypted[:-tag_len]
        tag = encrypted[-tag_len:]

        return PreparedPrivateBinPayload(
            adata=adata,
            spec=spec,
            iv=iv,
            tag_len=tag_len,
            compression=compression,
            key=key,
            ciphertext=ciphertext,
            tag=tag,
            aad=self.js_json_stringify(adata),
        )

    def decrypt_prepared_payload(
        self, prepared: PreparedPrivateBinPayload, password: str
    ) -> str:
        """用单个密码尝试解密已预解析的 PrivateBin payload"""
        aes_key = self.derive_key(prepared.key, password, prepared.spec)

        cipher = AES.new(
            aes_key, AES.MODE_GCM, nonce=prepared.iv, mac_len=prepared.tag_len
        )
        cipher.update(prepared.aad)

        plain = cipher.decrypt_and_verify(prepared.ciphertext, prepared.tag)
        if prepared.compression == "zlib":
            try:
                plain = zlib.decompress(plain)
            except zlib.error:
                plain = zlib.decompress(plain, -zlib.MAX_WBITS)

        return plain.decode("utf-8")

    def decode_privatebin_key(self, fragment: str) -> bytes:
        """解码 PrivateBin fragment key"""
        fragment = fragment.lstrip("#")
        fragment = fragment.split("&", 1)[0]
        fragment = fragment.split("\\u0026", 1)[0]

        key = self.b58decode(fragment)
        if len(key) < 32:
            key = b"\x00" * (32 - len(key)) + key

        return key

    def derive_key(self, key: bytes, password: str, spec: list) -> bytes:
        """根据 PrivateBin KDF 参数派生 AES key"""
        salt = base64.b64decode(spec[1])
        iterations = int(spec[2])
        key_len = int(spec[3]) // 8

        raw = key
        if password:
            raw += self.js_string_to_bytes(password)

        return hashlib.pbkdf2_hmac(
            "sha256",
            raw,
            salt,
            iterations,
            dklen=key_len,
        )

    def b58decode(self, value: str) -> bytes:
        """Base58 解码"""
        num = 0
        for char in value:
            num *= 58
            num += ALPHABET.index(char)

        combined = num.to_bytes((num.bit_length() + 7) // 8, byteorder="big")
        n_pad = len(value) - len(value.lstrip("1"))
        return b"\x00" * n_pad + combined

    def js_string_to_bytes(self, value: str) -> bytes:
        """模拟 JavaScript 字符串到字节的转换"""
        return bytes(ord(ch) & 0xFF for ch in value)

    def js_json_stringify(self, obj) -> bytes:
        """生成与 PrivateBin 前端一致的 JSON AAD 字节"""
        return json.dumps(obj, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
