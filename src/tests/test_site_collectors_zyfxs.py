"""资源分享师采集器测试"""

import json
from unittest.mock import Mock

import pytest

from collectors.sites.zyfxs import ZYFXSCollector
from core.interfaces import HttpClient
from core.models import FileManifest, SiteManifest
from utils.paste_to import DictionaryPasswordStrategy, PasteToDecryptResult


def test_extract_latest_video_url_from_playlist_uses_reversed_order():
    mock_http_client = Mock(spec=HttpClient)
    collector = ZYFXSCollector(http_client=mock_http_client)
    data = {
        "contents": {
            "twoColumnBrowseResultsRenderer": {
                "tabs": [
                    {
                        "tabRenderer": {
                            "content": {
                                "sectionListRenderer": {
                                    "contents": [
                                        {
                                            "itemSectionRenderer": {
                                                "contents": [
                                                    {
                                                        "playlistVideoListRenderer": {
                                                            "contents": [
                                                                {
                                                                    "playlistVideoRenderer": {
                                                                        "videoId": "OLDER",
                                                                        "title": {
                                                                            "runs": [
                                                                                {
                                                                                    "text": "节点分享 免费节点"
                                                                                }
                                                                            ]
                                                                        },
                                                                    }
                                                                },
                                                                {
                                                                    "playlistVideoRenderer": {
                                                                        "videoId": "LATEST",
                                                                        "title": {
                                                                            "runs": [
                                                                                {
                                                                                    "text": "资源分享师 节点分享 免费节点"
                                                                                }
                                                                            ]
                                                                        },
                                                                    }
                                                                },
                                                            ]
                                                        }
                                                    }
                                                ]
                                            }
                                        }
                                    ]
                                }
                            }
                        }
                    }
                ]
            }
        }
    }
    html = f"<script>var ytInitialData = {json.dumps(data)};</script>"

    assert collector.get_today_url(html) == "https://www.youtube.com/watch?v=LATEST"


def test_get_today_url_rejects_compact_playlist_html():
    mock_http_client = Mock(spec=HttpClient)
    collector = ZYFXSCollector(http_client=mock_http_client)
    html = (
        '"playlistVideoRenderer":{"videoId":"OLDER",'
        '"title":{"runs":[{"text":"节点分享 免费节点"}]}}'
        '"playlistVideoRenderer":{"videoId":"LATEST",'
        '"title":{"runs":[{"text":"资源分享师 节点分享 免费节点"}]}}'
    )

    with pytest.raises(Exception, match="ytInitialData"):
        collector.get_today_url(html)


def test_extract_paste_url_from_video_html():
    mock_http_client = Mock(spec=HttpClient)
    collector = ZYFXSCollector(http_client=mock_http_client)
    html = (
        r'<a href="/redirect?q=https%3A%2F%2Fpaste.to%2F%3Fabc123'
        r'%23FragmentKey\u0026redir_token=x">'
    )

    assert collector.extract_paste_url(html) == "https://paste.to/?abc123#FragmentKey"


def test_parse_subscription_tasks_from_decrypted_share():
    mock_http_client = Mock(spec=HttpClient)
    collector = ZYFXSCollector(http_client=mock_http_client)
    content = """
    V2ray和小火箭，订阅链接：
    https://example.com/zyfxs-v2ray.jpg
    clash，订阅链接：
    https://example.com/zyfxs-clash.jpg
    """

    tasks = collector.parse_subscription_tasks(content)

    assert [task.filename for task in tasks] == ["v2ray.txt", "clash.yaml"]
    assert tasks[0].url == "https://example.com/zyfxs-v2ray.jpg"
    assert tasks[1].url == "https://example.com/zyfxs-clash.jpg"


def test_get_download_tasks_uses_paste_to_service(monkeypatch):
    mock_http_client = Mock(spec=HttpClient)
    collector = ZYFXSCollector(http_client=mock_http_client)
    collector.today_page = "https://www.youtube.com/watch?v=LATEST"
    collector.paste_to_password = "1234"
    collector.paste_to_password_strategy = DictionaryPasswordStrategy(["1234", "5678"])
    collector.skip_if_cached = Mock()
    collector.fetch_html = Mock(
        return_value=(
            r'<a href="/redirect?q=https%3A%2F%2Fpaste.to%2F%3Fabc123'
            r'%23FragmentKey\u0026redir_token=x">'
        )
    )
    paste_to_service = Mock()
    paste_to_service.decrypt_url.return_value = PasteToDecryptResult(
        password="1234", content="share content"
    )
    paste_to_service_class = Mock(return_value=paste_to_service)
    monkeypatch.setattr("collectors.sites.zyfxs.PasteToService", paste_to_service_class)
    collector.parse_subscription_tasks = Mock(return_value=[])

    collector.get_download_tasks()

    paste_to_service_class.assert_called_once()
    assert paste_to_service_class.call_args.kwargs["http_client"] is mock_http_client
    assert (
        paste_to_service_class.call_args.kwargs["password_strategy"]
        is collector.paste_to_password_strategy
    )
    paste_to_service.decrypt_url.assert_called_once_with(
        "https://paste.to/?abc123#FragmentKey",
        password="1234",
    )


def test_run_skips_when_latest_video_already_collected(tmp_path, monkeypatch):
    mock_http_client = Mock(spec=HttpClient)
    latest_url = "https://www.youtube.com/watch?v=LATEST"
    data = {
        "contents": {
            "twoColumnBrowseResultsRenderer": {
                "tabs": [
                    {
                        "tabRenderer": {
                            "content": {
                                "sectionListRenderer": {
                                    "contents": [
                                        {
                                            "itemSectionRenderer": {
                                                "contents": [
                                                    {
                                                        "playlistVideoListRenderer": {
                                                            "contents": [
                                                                {
                                                                    "playlistVideoRenderer": {
                                                                        "videoId": "LATEST",
                                                                        "title": {
                                                                            "simpleText": "资源分享师 节点分享 免费节点"
                                                                        },
                                                                    }
                                                                }
                                                            ]
                                                        }
                                                    }
                                                ]
                                            }
                                        }
                                    ]
                                }
                            }
                        }
                    }
                ]
            }
        }
    }
    mock_http_client.get.return_value = (
        f"<script>var ytInitialData = {json.dumps(data)};</script>"
    )
    collector = ZYFXSCollector(http_client=mock_http_client)
    site_dir = tmp_path / "zyfxs"
    site_dir.mkdir()
    (site_dir / "v2ray.txt").write_text("v" * 200, encoding="utf-8")
    (site_dir / "clash.yaml").write_text("proxies:\n  - name: test\n", encoding="utf-8")

    class FakeManifest:
        sites = {
            "zyfxs": SiteManifest(
                today_page=latest_url,
                status="success",
                updated_at="2026-05-19 12:00:00",
                files={
                    "v2ray.txt": FileManifest(
                        url="https://example.com/zyfxs-v2ray.jpg", success=True
                    ),
                    "clash.yaml": FileManifest(
                        url="https://example.com/zyfxs-clash.jpg", success=True
                    ),
                },
            )
        }

        def __init__(self, manifest_file):
            pass

        def get_site(self, site):
            return self.sites.get(site)

    monkeypatch.setattr("services.manifest_service.ManifestService", FakeManifest)
    paste_to_service = Mock()
    monkeypatch.setattr("collectors.sites.zyfxs.PasteToService", paste_to_service)

    result = collector.run(tmp_path)

    assert result.status == "success"
    assert result.today_page == latest_url
    assert paste_to_service.call_count == 0
    assert mock_http_client.get.call_count == 1
