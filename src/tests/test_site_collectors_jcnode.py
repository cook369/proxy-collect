"""jcnode 采集器测试"""

from unittest.mock import Mock

import pytest

from collectors.sites.jcnode import JCNodeCollector
from core.exceptions import ProxyError
from core.interfaces import HttpClient
from utils.passwords import (
    DictionaryPasswordStrategy,
    FatalPasswordAttemptError,
    PasswordAttemptResult,
    brute_force_password,
)


def test_get_today_url_extracts_post_link():
    collector = JCNodeCollector(http_client=Mock(spec=HttpClient))
    html = """
    <html><body>
      <div id="top"><main><article><div>
        <p>1</p><p>2</p><p>3</p><p>4</p>
        <p><a href="https://jcnode.com/posts/free-nodes/20260615/">today</a></p>
      </div></article></main></div>
    </body></html>
    """

    assert (
        collector.get_today_url(html) == "https://jcnode.com/posts/free-nodes/20260615/"
    )


def test_parse_subscription_tasks_extracts_clash_and_v2ray_urls():
    collector = JCNodeCollector(http_client=Mock(spec=HttpClient))
    content = (
        '{"v2ray":"https://example.com/v2ray.txt",'
        '"clash":"https://example.com/clash.yaml"}'
    )

    tasks = collector.parse_subscription_tasks(content)

    assert [task.filename for task in tasks] == ["v2ray.txt", "clash.yaml"]
    assert tasks[0].url == "https://example.com/v2ray.txt"
    assert tasks[1].url == "https://example.com/clash.yaml"


def test_get_download_tasks_uses_configured_code_without_bruteforce(monkeypatch):
    collector = JCNodeCollector(http_client=Mock(spec=HttpClient))
    collector.today_page = "https://jcnode.com/posts/free-nodes/20260615/"
    collector.verification_code = "1234"
    collector.skip_if_cached = Mock()
    collector.http_client.post = Mock(
        return_value='{"v2ray":"https://example.com/v2ray.txt"}'
    )
    brute_force_password_mock = Mock()
    monkeypatch.setattr(
        "collectors.sites.jcnode.brute_force_password", brute_force_password_mock
    )

    tasks = collector.get_download_tasks()

    collector.http_client.post.assert_called_once()
    assert collector.http_client.post.call_args.kwargs["json"] == {"code": "1234"}
    brute_force_password_mock.assert_not_called()
    assert [task.filename for task in tasks] == ["v2ray.txt"]


def test_get_download_tasks_passes_instance_verifier_to_bruteforce(monkeypatch):
    collector = JCNodeCollector(http_client=Mock(spec=HttpClient))
    collector.today_page = "https://jcnode.com/posts/free-nodes/20260615/"
    collector.verification_code_strategy = DictionaryPasswordStrategy(["1234"])
    collector.skip_if_cached = Mock()
    collector.http_client.post = Mock(return_value="unused")
    collector.parse_subscription_tasks = Mock(return_value=[])
    brute_force_password_mock = Mock(
        return_value=PasswordAttemptResult(password="1234", content="share content")
    )
    monkeypatch.setattr(
        "collectors.sites.jcnode.brute_force_password", brute_force_password_mock
    )

    collector.get_download_tasks()

    brute_force_password_mock.assert_called_once()
    assert (
        brute_force_password_mock.call_args.kwargs["password_strategy"]
        is collector.verification_code_strategy
    )
    # verify_code bound method may differ by identity, check it's callable
    assert callable(brute_force_password_mock.call_args.kwargs["try_password"])
    collector.parse_subscription_tasks.assert_called_once_with("share content")


def test_verify_code_posts_with_timeout_and_returns_content():
    collector = JCNodeCollector(http_client=Mock(spec=HttpClient))
    collector.http_client.post = Mock(
        return_value='{"v2ray":"https://example.com/v2ray.txt"}'
    )

    result = collector.verify_code("1234")

    assert result == '{"v2ray":"https://example.com/v2ray.txt"}'
    collector.http_client.post.assert_called_once_with(
        collector.verify_url,
        json={"code": "1234"},
        timeout=20,
        headers=collector.verify_headers,
    )


def test_verify_code_raises_fatal_error_on_proxy_error():
    collector = JCNodeCollector(http_client=Mock(spec=HttpClient))
    collector.http_client.post = Mock(
        side_effect=ProxyError("all proxies failed")
    )

    with pytest.raises(FatalPasswordAttemptError, match="network failed"):
        collector.verify_code("1234")

    collector.http_client.post.assert_called_once()


def test_verify_code_rejects_wrong_password():
    collector = JCNodeCollector(http_client=Mock(spec=HttpClient))
    collector.http_client.post = Mock(return_value="口令错误")

    with pytest.raises(ValueError, match="password error"):
        collector.verify_code("0000")


def test_bruteforce_propagates_fatal_attempt_error():
    attempts = []

    def try_password(password):
        attempts.append(password)
        raise FatalPasswordAttemptError("network unavailable")

    with pytest.raises(FatalPasswordAttemptError):
        brute_force_password(
            max_workers=1,
            password_strategy=DictionaryPasswordStrategy(["0000", "0001"]),
            try_password=try_password,
        )

    assert attempts == ["0000"]
