"""小青科学采集器测试"""

import json
from pathlib import Path
from unittest.mock import Mock

from src.collectors.sites.xqkxw import XQKXWCollector
from core.models import FileManifest, SiteManifest
from core.interfaces import HttpClient


def test_extract_latest_video_url_from_playlist_selects_matching_title():
    mock_http_client = Mock(spec=HttpClient)
    collector = XQKXWCollector(http_client=mock_http_client)
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
                                                                        "videoId": "IGNORE_1",
                                                                        "title": {
                                                                            "runs": [
                                                                                {
                                                                                    "text": "其它视频 免费节点"
                                                                                }
                                                                            ]
                                                                        },
                                                                    }
                                                                },
                                                                {
                                                                    "playlistVideoRenderer": {
                                                                        "videoId": "LN-Dgi_0_1I",
                                                                        "title": {
                                                                            "runs": [
                                                                                {
                                                                                    "text": "最新节点分享 免费节点"
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
        == "https://www.youtube.com/watch?v=LN-Dgi_0_1I"
    )


def test_extract_latest_video_url_from_compact_playlist_html():
    mock_http_client = Mock(spec=HttpClient)
    collector = XQKXWCollector(http_client=mock_http_client)
    html = (
        '"playlistVideoRenderer":{"videoId":"LN-Dgi_0_1I",'
        '"title":{"runs":[{"text":"最新节点分享 免费节点"}]}}'
    )

    assert (
        collector.extract_latest_video_url(html)
        == "https://www.youtube.com/watch?v=LN-Dgi_0_1I"
    )


def test_extract_paste_url_from_video_html():
    mock_http_client = Mock(spec=HttpClient)
    collector = XQKXWCollector(http_client=mock_http_client)
    html = (
        r'<a href="/redirect?q=https%3A%2F%2Fpaste.to%2F%3F7d3c11a64e4a5bd4'
        r'%23CZn2QCZQJm1bF8dTdQFEwxiSdfQAbx7wLarWY9zgh4tE\u0026redir_token=x">'
    )

    assert (
        collector.extract_paste_url(html)
        == "https://paste.to/?7d3c11a64e4a5bd4#CZn2QCZQJm1bF8dTdQFEwxiSdfQAbx7wLarWY9zgh4tE"
    )


def test_parse_subscription_tasks_from_decrypted_share():
    mock_http_client = Mock(spec=HttpClient)
    collector = XQKXWCollector(http_client=mock_http_client)
    content = Path("../new-collect/1.data").read_text(encoding="utf-8")

    tasks = collector.parse_subscription_tasks(content)

    assert [task.filename for task in tasks] == ["v2ray.txt", "clash.yaml"]
    assert tasks[0].url.endswith("260518.txt")
    assert tasks[1].url.endswith("20260518.yaml")


def test_brute_force_decrypt_prepares_payload_once_and_finds_password():
    mock_http_client = Mock(spec=HttpClient)
    collector = XQKXWCollector(http_client=mock_http_client)
    collector.password_workers = 2
    attempts = []
    prepared_payload = object()

    collector.iter_passwords = lambda: ["0000", "0001", "0002"]
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


def test_run_skips_when_latest_video_already_collected(tmp_path, monkeypatch):
    mock_http_client = Mock(spec=HttpClient)
    latest_url = "https://www.youtube.com/watch?v=LN-Dgi_0_1I"
    mock_http_client.get.return_value = (
        '"playlistVideoRenderer":{"videoId":"LN-Dgi_0_1I",'
        '"title":{"runs":[{"text":"最新节点分享 免费节点"}]}}'
    )
    collector = XQKXWCollector(http_client=mock_http_client)
    site_dir = tmp_path / "xqkxw"
    site_dir.mkdir()
    (site_dir / "v2ray.txt").write_text("v" * 200, encoding="utf-8")
    (site_dir / "clash.yaml").write_text("proxies:\n  - name: test\n", encoding="utf-8")

    class FakeManifest:
        sites = {
            "xqkxw": SiteManifest(
                today_page=latest_url,
                status="success",
                updated_at="2026-05-18 12:00:00",
                files={
                    "v2ray.txt": FileManifest(
                        url="https://example.com/v2ray.txt", success=True
                    ),
                    "clash.yaml": FileManifest(
                        url="https://example.com/clash.yaml", success=True
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
