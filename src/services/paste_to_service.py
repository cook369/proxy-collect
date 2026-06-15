"""Paste.to 解密服务"""

from functools import partial
from core.interfaces import HttpClient
from utils.paste_to import (
    CharsetPasswordStrategy,
    DictionaryPasswordStrategy,
    PasswordAttemptResult,
    brute_force_payload,
    decrypt_prepared_paste_to_payload,
    fetch_paste_to_payload,
    parse_paste_to_url,
    prepare_paste_to_payload,
)


class PasteToService:
    """封装 Paste.to 获取、解析和解密流程"""

    def __init__(
        self,
        *,
        http_client: HttpClient,
        timeout: int,
        max_workers: int,
        password_strategy: (
            CharsetPasswordStrategy | DictionaryPasswordStrategy | None
        ) = None,
    ) -> None:
        self.http_client = http_client
        self.timeout = timeout
        self.max_workers = max_workers
        self.password_strategy = password_strategy

    def decrypt_url(
        self,
        paste_url: str,
        *,
        password: str | None,
    ) -> PasswordAttemptResult:
        """根据 paste.to URL 获取 payload，并按密码或爆破策略解密"""
        paste_id, fragment = parse_paste_to_url(paste_url)
        payload = fetch_paste_to_payload(
            paste_id,
            http_client=self.http_client,
            timeout=self.timeout,
        )
        prepared = prepare_paste_to_payload(payload, fragment)
        if password:
            data = decrypt_prepared_paste_to_payload(prepared, password)
            return PasswordAttemptResult(password=password, content=data)

        decrypt_prepared = partial(decrypt_prepared_paste_to_payload, prepared)

        return brute_force_payload(
            max_workers=self.max_workers,
            password_strategy=self.password_strategy,
            decrypt_prepared=decrypt_prepared,
        )
