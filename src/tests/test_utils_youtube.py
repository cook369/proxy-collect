"""YouTube 采集辅助函数测试"""

import json

import pytest

from core.exceptions import ParseError
from utils.youtube import (
    extract_youtube_redirect_url,
    find_latest_video_url,
    get_playlist_videos,
)


def test_get_playlist_videos_rejects_compact_renderer_html():
    html = (
        '"playlistVideoRenderer":{"videoId":"OLDER",'
        '"title":{"runs":[{"text":"旧视频 免费节点"}]}}'
    )

    with pytest.raises(ParseError, match="ytInitialData"):
        get_playlist_videos(html)


def test_find_latest_video_url_can_reverse_initial_data_order():
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
                                                            "contentId": "OLDER",
                                                            "metadata": {
                                                                "lockupMetadataViewModel": {
                                                                    "title": {
                                                                        "content": "节点分享 免费节点"
                                                                    }
                                                                }
                                                            },
                                                        }
                                                    },
                                                    {
                                                        "lockupViewModel": {
                                                            "contentId": "LATEST",
                                                            "metadata": {
                                                                "lockupMetadataViewModel": {
                                                                    "title": {
                                                                        "content": "资源分享师 节点分享 免费节点"
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

    assert find_latest_video_url(
        html,
        ("节点分享", "免费节点"),
        reverse=True,
    ) == (
        "https://www.youtube.com/watch?v=LATEST",
        "资源分享师 节点分享 免费节点",
    )


def test_find_latest_video_url_matches_all_keywords():
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
                                                            "contentId": "MATCH",
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
    html = f"<script>var ytInitialData = {json.dumps(data)};</script>"

    assert find_latest_video_url(
        html,
        ("最新节点分享", "免费节点"),
        reverse=False,
    ) == (
        "https://www.youtube.com/watch?v=MATCH",
        "最新节点分享 免费节点",
    )


def test_find_latest_video_url_raises_parse_error_when_no_match():
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
                                                            "contentId": "IGNORE",
                                                            "metadata": {
                                                                "lockupMetadataViewModel": {
                                                                    "title": {
                                                                        "content": "其它视频 免费节点"
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
    html = f"<script>var ytInitialData = {json.dumps(data)};</script>"

    with pytest.raises(ParseError, match="No matching YouTube playlist video"):
        find_latest_video_url(
            html,
            ("最新节点分享", "免费节点"),
            reverse=False,
        )


def test_extract_youtube_redirect_url_decodes_target_url():
    html = (
        r'<a href="/redirect?q=https%3A%2F%2Fpaste.to%2F%3Fabc123'
        r'%23FragmentKey\u0026redir_token=x">'
    )

    assert (
        extract_youtube_redirect_url(
            html,
            "paste.to",
        )
        == "https://paste.to/?abc123#FragmentKey"
    )
