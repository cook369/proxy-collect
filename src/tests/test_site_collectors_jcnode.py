"""jcnode 采集器测试"""

from unittest.mock import Mock

import pytest
import requests

import collectors.sites.jcnode as jcnode
from collectors.sites.jcnode import JCNodeCollector
from core.interfaces import HttpClient
from core.models import ProxyInfo
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
    collector.verify_code = Mock(
        return_value='{"v2ray":"https://example.com/v2ray.txt"}'
    )
    brute_force_password = Mock()
    monkeypatch.setattr(
        "collectors.sites.jcnode.brute_force_password", brute_force_password
    )

    tasks = collector.get_download_tasks()

    collector.verify_code.assert_called_once_with("1234")
    brute_force_password.assert_not_called()
    assert [task.filename for task in tasks] == ["v2ray.txt"]


def test_get_download_tasks_passes_instance_verifier_to_bruteforce(monkeypatch):
    collector = JCNodeCollector(http_client=Mock(spec=HttpClient))
    collector.today_page = "https://jcnode.com/posts/free-nodes/20260615/"
    collector.verification_code_strategy = DictionaryPasswordStrategy(["1234"])
    collector.skip_if_cached = Mock()
    collector.verify_code = Mock(return_value="unused")
    collector.parse_subscription_tasks = Mock(return_value=[])
    brute_force_password = Mock(
        return_value=PasswordAttemptResult(password="1234", content="share content")
    )
    monkeypatch.setattr(
        "collectors.sites.jcnode.brute_force_password", brute_force_password
    )

    collector.get_download_tasks()

    brute_force_password.assert_called_once()
    assert (
        brute_force_password.call_args.kwargs["password_strategy"]
        is collector.verification_code_strategy
    )
    assert (
        brute_force_password.call_args.kwargs["try_password"] is collector.verify_code
    )
    collector.parse_subscription_tasks.assert_called_once_with("share content")


def test_verify_code_posts_with_timeout_and_returns_content(monkeypatch):
    collector = JCNodeCollector(http_client=Mock(spec=HttpClient))
    response = Mock(text='{"v2ray":"https://example.com/v2ray.txt"}')
    response.raise_for_status = Mock()
    post = Mock(return_value=response)
    monkeypatch.setattr("collectors.sites.jcnode.requests.post", post)

    assert collector.verify_code("1234") == response.text

    post.assert_called_once_with(
        collector.verify_url,
        proxies=None,
        headers=collector.verify_headers,
        json={"code": "1234"},
        timeout=jcnode.default_config.collector.fetch_timeout,
    )


def test_verify_code_retries_other_proxy_on_request_error(monkeypatch):
    p1 = ProxyInfo(host="127.0.0.1", port=1080)
    p2 = ProxyInfo(host="127.0.0.2", port=1080)
    collector = JCNodeCollector(proxies_list=[p1, p2])
    monkeypatch.setattr("collectors.sites.jcnode.random.shuffle", lambda items: None)
    response = Mock(text='{"v2ray":"https://example.com/v2ray.txt"}')
    response.raise_for_status = Mock()
    post = Mock(side_effect=[requests.Timeout("timeout"), response])
    monkeypatch.setattr("collectors.sites.jcnode.requests.post", post)

    assert collector.verify_code("1234") == response.text

    assert post.call_count == 2
    assert post.call_args_list[0].kwargs["json"] == {"code": "1234"}
    assert post.call_args_list[1].kwargs["json"] == {"code": "1234"}
    assert post.call_args_list[0].kwargs["proxies"] == {
        "http": p1.url,
        "https": p1.url,
    }
    assert post.call_args_list[1].kwargs["proxies"] == {
        "http": p2.url,
        "https": p2.url,
    }


def test_verify_code_skips_known_failed_proxy(monkeypatch):
    p1 = ProxyInfo(host="127.0.0.1", port=1080)
    p2 = ProxyInfo(host="127.0.0.2", port=1080)
    collector = JCNodeCollector(proxies_list=[p1, p2])
    monkeypatch.setattr("collectors.sites.jcnode.random.shuffle", lambda items: None)
    wrong_response = Mock(text="口令错误")
    wrong_response.raise_for_status = Mock()
    success_response = Mock(text='{"v2ray":"https://example.com/v2ray.txt"}')
    success_response.raise_for_status = Mock()
    post = Mock(
        side_effect=[requests.Timeout("timeout"), wrong_response, success_response]
    )
    monkeypatch.setattr("collectors.sites.jcnode.requests.post", post)

    with pytest.raises(ValueError, match="password error"):
        collector.verify_code("0000")

    assert collector.verify_code("1234") == success_response.text
    assert post.call_count == 3
    assert post.call_args_list[2].kwargs["proxies"] == {
        "http": p2.url,
        "https": p2.url,
    }


def test_verify_code_rejects_wrong_password(monkeypatch):
    collector = JCNodeCollector(http_client=Mock(spec=HttpClient))
    response = Mock(text="口令错误")
    response.raise_for_status = Mock()
    monkeypatch.setattr(
        "collectors.sites.jcnode.requests.post", Mock(return_value=response)
    )

    with pytest.raises(ValueError, match="password error"):
        collector.verify_code("0000")


def test_verify_code_does_not_record_proxy_cache(monkeypatch):
    proxy = ProxyInfo(host="127.0.0.1", port=1080)
    collector = JCNodeCollector(proxies_list=[proxy])
    collector.verify_network_retry_rounds = 1
    monkeypatch.setattr(
        "collectors.sites.jcnode.requests.post",
        Mock(side_effect=requests.Timeout("timeout")),
    )

    with pytest.raises(FatalPasswordAttemptError):
        collector.verify_code("1234")

    assert collector.proxy_pool is not None
    [stored_proxy] = collector.proxy_pool.get_sorted()
    assert stored_proxy.fail_count == 0
    assert stored_proxy.success_count == 0


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
