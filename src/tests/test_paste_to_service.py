"""Paste.to 服务测试"""

from unittest.mock import Mock

import services.paste_to_service as paste_to_service
from services.paste_to_service import PasteToService
from utils.paste_to import DictionaryPasswordStrategy, PasteToDecryptResult


def test_paste_to_service_decrypts_url_with_configured_dependencies():
    http_client = Mock()
    prepared_payload = object()

    service = PasteToService(
        http_client=http_client,
        timeout=7,
        max_workers=2,
    )

    fetch_paste_to_payload = Mock(return_value={"ct": "payload"})
    prepare_paste_to_payload = Mock(return_value=prepared_payload)
    decrypt_prepared_paste_to_payload = Mock(return_value="decrypted content")

    original_fetch = paste_to_service.fetch_paste_to_payload
    original_prepare = paste_to_service.prepare_paste_to_payload
    original_decrypt = paste_to_service.decrypt_prepared_paste_to_payload
    paste_to_service.fetch_paste_to_payload = fetch_paste_to_payload
    paste_to_service.prepare_paste_to_payload = prepare_paste_to_payload
    paste_to_service.decrypt_prepared_paste_to_payload = (
        decrypt_prepared_paste_to_payload
    )
    try:
        result = service.decrypt_url(
            "https://paste.to/?abc123#FragmentKey",
            password="1234",
        )
    finally:
        paste_to_service.fetch_paste_to_payload = original_fetch
        paste_to_service.prepare_paste_to_payload = original_prepare
        paste_to_service.decrypt_prepared_paste_to_payload = original_decrypt

    assert result == PasteToDecryptResult(
        password="1234",
        content="decrypted content",
    )
    fetch_paste_to_payload.assert_called_once_with(
        "abc123",
        http_client=http_client,
        timeout=7,
    )
    prepare_paste_to_payload.assert_called_once_with({"ct": "payload"}, "FragmentKey")
    decrypt_prepared_paste_to_payload.assert_called_once_with(prepared_payload, "1234")


def test_paste_to_service_passes_bruteforce_strategy():
    http_client = Mock()
    prepared_payload = object()
    password_strategy = DictionaryPasswordStrategy(["alpha", "beta"])

    service = PasteToService(
        http_client=http_client,
        timeout=7,
        max_workers=2,
        password_strategy=password_strategy,
    )

    fetch_paste_to_payload = Mock(return_value={"ct": "payload"})
    prepare_paste_to_payload = Mock(return_value=prepared_payload)
    brute_force_paste_to_payload = Mock(
        return_value=PasteToDecryptResult(password="beta", content="decrypted content")
    )

    original_fetch = paste_to_service.fetch_paste_to_payload
    original_prepare = paste_to_service.prepare_paste_to_payload
    original_bruteforce = paste_to_service.brute_force_paste_to_payload
    paste_to_service.fetch_paste_to_payload = fetch_paste_to_payload
    paste_to_service.prepare_paste_to_payload = prepare_paste_to_payload
    paste_to_service.brute_force_paste_to_payload = brute_force_paste_to_payload
    try:
        result = service.decrypt_url(
            "https://paste.to/?abc123#FragmentKey",
            password=None,
        )
    finally:
        paste_to_service.fetch_paste_to_payload = original_fetch
        paste_to_service.prepare_paste_to_payload = original_prepare
        paste_to_service.brute_force_paste_to_payload = original_bruteforce

    assert result == PasteToDecryptResult(
        password="beta",
        content="decrypted content",
    )
    brute_force_paste_to_payload.assert_called_once_with(
        prepared=prepared_payload,
        max_workers=2,
        password_strategy=password_strategy,
    )
