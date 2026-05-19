"""资源分享师采集器测试"""

import json
from unittest.mock import Mock

from collectors.sites.zyfxs import ZYFXSCollector
from core.interfaces import HttpClient
from core.models import FileManifest, SiteManifest


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

    assert (
        collector.extract_latest_video_url(html)
        == "https://www.youtube.com/watch?v=LATEST"
    )


def test_extract_latest_video_url_from_compact_playlist_html_uses_reversed_order():
    mock_http_client = Mock(spec=HttpClient)
    collector = ZYFXSCollector(http_client=mock_http_client)
    html = (
        '"playlistVideoRenderer":{"videoId":"OLDER",'
        '"title":{"runs":[{"text":"节点分享 免费节点"}]}}'
        '"playlistVideoRenderer":{"videoId":"LATEST",'
        '"title":{"runs":[{"text":"资源分享师 节点分享 免费节点"}]}}'
    )

    assert (
        collector.extract_latest_video_url(html)
        == "https://www.youtube.com/watch?v=LATEST"
    )


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


def test_brute_force_decrypt_prepares_payload_once_and_finds_password():
    mock_http_client = Mock(spec=HttpClient)
    collector = ZYFXSCollector(http_client=mock_http_client)
    collector.password_workers = 2
    collector.password_space_size = 3
    attempts = []
    prepared_payload = object()

    collector.prepare_privatebin_payload = Mock(return_value=prepared_payload)

    def fake_decrypt(prepared, password):
        assert prepared is prepared_payload
        attempts.append(password)
        if password == "0002":
            return "decrypted content"
        raise ValueError("bad password")

    collector.decrypt_prepared_payload = fake_decrypt

    assert collector.brute_force_decrypt({}, "fragment") == "decrypted content"
    collector.prepare_privatebin_payload.assert_called_once_with({}, "fragment")
    assert "0002" in attempts


def test_password_ranges_submit_one_task_per_worker():
    mock_http_client = Mock(spec=HttpClient)
    collector = ZYFXSCollector(http_client=mock_http_client)
    collector.password_workers = 4
    collector.password_space_size = 10

    assert list(collector.iter_password_ranges()) == [(0, 3), (3, 6), (6, 9), (9, 10)]


def test_run_skips_when_latest_video_already_collected(tmp_path, monkeypatch):
    mock_http_client = Mock(spec=HttpClient)
    latest_url = "https://www.youtube.com/watch?v=LATEST"
    mock_http_client.get.return_value = (
        '"playlistVideoRenderer":{"videoId":"LATEST",'
        '"title":{"runs":[{"text":"资源分享师 节点分享 免费节点"}]}}'
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
    collector.fetch_decrypted_share = Mock()

    result = collector.run(tmp_path)

    assert result.status == "success"
    assert result.today_page == latest_url
    assert collector.fetch_decrypted_share.call_count == 0
    assert mock_http_client.get.call_count == 1
