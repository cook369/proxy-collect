"""Paste.to 辅助函数测试（异步版本）"""

from unittest.mock import Mock, AsyncMock
import pytest

from core.exceptions import ParseError
import utils.paste_to as paste_to
from utils.paste_to import (
    CharsetPasswordStrategy,
    DictionaryPasswordStrategy,
    PasswordAttemptResult,
    b58decode,
    brute_force_payload,
    decode_paste_to_key,
    decrypt_paste_to_url,
    fetch_paste_to_payload,
    js_json_stringify,
    js_string_to_bytes,
    parse_paste_to_url,
)


def test_parse_paste_to_url_returns_paste_id_and_fragment():
    assert parse_paste_to_url("https://paste.to/?abc123#FragmentKey") == (
        "abc123",
        "FragmentKey",
    )


def test_parse_paste_to_url_requires_fragment():
    with pytest.raises(ParseError):
        parse_paste_to_url("https://paste.to/?abc123")


def test_decode_paste_to_key_strips_extra_fragment_data_and_left_pads_key():
    assert decode_paste_to_key("#2&extra") == (b"\x00" * 31) + b"\x01"
    assert decode_paste_to_key("2\\u0026extra") == (b"\x00" * 31) + b"\x01"


def test_b58decode_preserves_leading_zeroes():
    assert b58decode("112") == b"\x00\x00\x01"


def test_js_helpers_match_paste_to_frontend_encoding():
    assert js_string_to_bytes("AĀ") == b"A\x00"
    assert js_json_stringify(["a", {"b": 1}]) == b'["a",{"b":1}]'


@pytest.mark.asyncio
async def test_fetch_paste_to_payload_uses_pasteid_endpoint():
    http_client = AsyncMock()
    http_client.get = AsyncMock(return_value='{"ct": "payload"}')

    assert await fetch_paste_to_payload(
        "abc123",
        http_client=http_client,
        timeout=7,
    ) == {"ct": "payload"}
    http_client.get.assert_awaited_once()
    assert http_client.get.call_args.args[0] == "https://paste.to/?pasteid=abc123"


def test_charset_password_strategy_generates_passwords_from_charset_and_length():
    strategy = CharsetPasswordStrategy(length=2, charset="ab")

    assert list(strategy.iter_passwords()) == ["aa", "ab", "ba", "bb"]


@pytest.mark.asyncio
async def test_brute_force_payload_returns_password_and_content():
    attempts = []

    def fake_decrypt(password):
        attempts.append(password)
        if password == "2":
            return "decrypted content"
        raise ValueError("bad password")

    result = await brute_force_payload(
        max_workers=1,
        password_strategy=CharsetPasswordStrategy(length=1, charset="012"),
        decrypt_prepared=fake_decrypt,
    )

    assert result == PasswordAttemptResult(password="2", content="decrypted content")
    assert attempts == ["0", "1", "2"]


@pytest.mark.asyncio
async def test_brute_force_payload_uses_dictionary_strategy():
    attempts = []

    def fake_decrypt(password):
        attempts.append(password)
        if password == "beta":
            return "decrypted content"
        raise ValueError("bad password")

    result = await brute_force_payload(
        max_workers=1,
        password_strategy=DictionaryPasswordStrategy(["alpha", "beta", "0002"]),
        decrypt_prepared=fake_decrypt,
    )

    assert result == PasswordAttemptResult(password="beta", content="decrypted content")
    assert attempts == ["alpha", "beta"]


@pytest.mark.asyncio
async def test_brute_force_payload_uses_default_four_digit_numeric_strategy():
    attempts = []

    def fake_decrypt(password):
        attempts.append(password)
        if password == "0002":
            return "decrypted content"
        raise ValueError("bad password")

    result = await brute_force_payload(
        max_workers=1,
        decrypt_prepared=fake_decrypt,
    )

    assert result == PasswordAttemptResult(password="0002", content="decrypted content")
    assert attempts == ["0000", "0001", "0002"]


@pytest.mark.asyncio
async def test_decrypt_paste_to_url_uses_password_without_bruteforce():
    http_client = AsyncMock()
    http_client.get = AsyncMock(return_value='{"ct": "payload"}')
    prepared_payload = object()

    def fake_decrypt(prepared, password):
        assert prepared is prepared_payload
        assert password == "1234"
        return "decrypted by password"

    original_prepare = paste_to.prepare_paste_to_payload
    original_decrypt = paste_to.decrypt_prepared_paste_to_payload
    paste_to.prepare_paste_to_payload = lambda payload, fragment: prepared_payload
    paste_to.decrypt_prepared_paste_to_payload = fake_decrypt
    try:
        result = await decrypt_paste_to_url(
            "https://paste.to/?abc123#FragmentKey",
            http_client=http_client,
            password="1234",
            max_workers=1,
            timeout=7,
        )
    finally:
        paste_to.prepare_paste_to_payload = original_prepare
        paste_to.decrypt_prepared_paste_to_payload = original_decrypt

    assert result == PasswordAttemptResult(
        password="1234",
        content="decrypted by password",
    )


@pytest.mark.asyncio
async def test_decrypt_paste_to_url_brute_forces_without_password():
    http_client = AsyncMock()
    http_client.get = AsyncMock(return_value='{"ct": "payload"}')
    prepared_payload = object()

    def fake_decrypt(prepared, password):
        assert prepared is prepared_payload
        if password == "2":
            return "decrypted by brute force"
        raise ValueError("bad password")

    original_prepare = paste_to.prepare_paste_to_payload
    original_decrypt = paste_to.decrypt_prepared_paste_to_payload
    paste_to.prepare_paste_to_payload = lambda payload, fragment: prepared_payload
    paste_to.decrypt_prepared_paste_to_payload = fake_decrypt
    try:
        result = await decrypt_paste_to_url(
            "https://paste.to/?abc123#FragmentKey",
            http_client=http_client,
            password=None,
            max_workers=1,
            timeout=7,
            password_strategy=CharsetPasswordStrategy(length=1, charset="012"),
        )
    finally:
        paste_to.prepare_paste_to_payload = original_prepare
        paste_to.decrypt_prepared_paste_to_payload = original_decrypt

    assert result == PasswordAttemptResult(
        password="2",
        content="decrypted by brute force",
    )
