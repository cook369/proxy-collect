"""小青科学网采集器测试（异步版本）"""

import json
from unittest.mock import Mock, AsyncMock
import pytest

from collectors.sites.xqkxw import XQKXWCollector
from core.interfaces import HttpClient
from core.models import FileManifest, SiteManifest
from utils.paste_to import DictionaryPasswordStrategy, PasswordAttemptResult


def test_extract_latest_video_url_from_playlist_selects_matching_title():
    mock_http_client = AsyncMock(spec=HttpClient)
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
                                                        "lockupViewModel": {
                                                            "contentId": "IGNORE_1",
                                                            "metadata": {
                                                                "lockupMetadataViewModel": {
                                                                    "title": {
                                                                        "content": "其它视频 免费节点"
                                                                    }
                                                                }
                                                            },
                                                        }
                                                    },
                                                    {
                                                        "lockupViewModel": {
                                                            "contentId": "LN-Dgi_0_1I",
                                                            "metadata": {
                                                                "lockupMetadataViewModel": {
                                                                    "title": {
                                                                        "content": "最新节点分享 免费节点"
                                                                    }
                                                                }
                                                            },
                                                        }
                                                    },
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
        collector.get_today_url(html)
        == ("https://www.youtube.com/watch?v=LN-Dgi_0_1I", "最新节点分享 免费节点")
    )


def test_get_today_url_rejects_compact_playlist_html():
    mock_http_client = AsyncMock(spec=HttpClient)
    collector = XQKXWCollector(http_client=mock_http_client)
    html = (
        '"playlistVideoRenderer":{"videoId":"LN-Dgi_0_1I",'
        '"title":{"runs":[{"text":"最新节点分享 免费节点"}]}}'
    )

    with pytest.raises(Exception, match="ytInitialData"):
        collector.get_today_url(html)


def test_extract_paste_url_from_video_html():
    mock_http_client = AsyncMock(spec=HttpClient)
    collector = XQKXWCollector(http_client=mock_http_client)
    html = (
        r'<a href="/redirect?q=https%3A%2F%2Fpaste.to%2F%3F7d3c11a64e4a5bd4'
        r'%23CZn2QCZQJm1bF8dTdQFEwxiSdfQAbx7wLarWY9zgh4tE&redir_token=x">'
    )

    assert (
        collector.extract_paste_url(html)
        == "https://paste.to/?7d3c11a64e4a5bd4#CZn2QCZQJm1bF8dTdQFEwxiSdfQAbx7wLarWY9zgh4tE"
    )


def test_parse_subscription_tasks_from_decrypted_share():
    mock_http_client = AsyncMock(spec=HttpClient)
    collector = XQKXWCollector(http_client=mock_http_client)
    content = """
    V2ray和小火箭，订阅链接，可更新订阅：
    https://gist.githubusercontent.com/example/raw/xqkxw260518.txt
    clash， 订阅链接，可更新订阅（导入）：
    https://gist.githubusercontent.com/example/raw/xqkxw20260518.yaml
    """

    tasks = collector.parse_subscription_tasks(content)

    assert [task.filename for task in tasks] == ["v2ray.txt", "clash.yaml"]
    assert tasks[0].url.endswith("260518.txt")
    assert tasks[1].url.endswith("20260518.yaml")


@pytest.mark.asyncio
async def test_get_download_tasks_uses_paste_to_service(monkeypatch):
    mock_http_client = AsyncMock(spec=HttpClient)
    collector = XQKXWCollector(http_client=mock_http_client)
    collector.today_page = "https://www.youtube.com/watch?v=LATEST"
    collector.paste_to_password = "1234"
    collector.paste_to_password_strategy = DictionaryPasswordStrategy(["1234", "5678"])
    collector.skip_if_cached = Mock()
    collector.fetch_html = AsyncMock(
        return_value=(
            r'<a href="/redirect?q=https%3A%2F%2Fpaste.to%2F%3Fabc123'
            r'%23FragmentKey&redir_token=x">'
        )
    )
    paste_to_service = Mock()
    paste_to_service.decrypt_url = AsyncMock(
        return_value=PasswordAttemptResult(
            password="1234", content="share content"
        )
    )
    paste_to_service_class = Mock(return_value=paste_to_service)
    monkeypatch.setattr("collectors.base.PasteToService", paste_to_service_class)
    collector.parse_subscription_tasks = Mock(return_value=[])

    await collector.get_download_tasks()

    paste_to_service_class.assert_called_once()
    assert paste_to_service_class.call_args.kwargs["http_client"] is mock_http_client
    assert (
        paste_to_service_class.call_args.kwargs["password_strategy"]
        is collector.paste_to_password_strategy
    )
    paste_to_service.decrypt_url.assert_awaited_once_with(
        "https://paste.to/?abc123#FragmentKey",
        password="1234",
    )


@pytest.mark.asyncio
async def test_run_skips_when_latest_video_already_collected(tmp_path, monkeypatch):
    mock_http_client = AsyncMock(spec=HttpClient)
    latest_url = "https://www.youtube.com/watch?v=LN-Dgi_0_1I"
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
                                                        "lockupViewModel": {
                                                            "contentId": "LN-Dgi_0_1I",
                                                            "metadata": {
                                                                "lockupMetadataViewModel": {
                                                                    "title": {
                                                                        "content": "最新节点分享 免费节点"
                                                                    }
                                                                }
                                                            },
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
    mock_http_client.get = AsyncMock(
        return_value=f"<script>var ytInitialData = {json.dumps(data)};</script>"
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
    paste_to_service = Mock()
    monkeypatch.setattr("collectors.base.PasteToService", paste_to_service)

    result = await collector.run(tmp_path)

    assert result.status == "success"
    assert result.today_page == latest_url
    assert paste_to_service.call_count == 0
    assert mock_http_client.get.call_count == 1
