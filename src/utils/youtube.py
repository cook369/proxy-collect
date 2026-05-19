"""YouTube 页面解析辅助函数"""

import html
import json
import re
from urllib.parse import unquote

from core.exceptions import ParseError
from core.interfaces import HttpClient
from utils.check import check_html_contains


def get_playlist_videos(
    playlist_html: str,
) -> list[tuple[str, str]]:
    """从 ytInitialData JSON 中提取播放列表视频"""
    match = re.search(
        r"var ytInitialData\s*=\s*({.*?});</script>",
        playlist_html,
        re.DOTALL,
    )
    if not match:
        raise ParseError(
            "No ytInitialData found in YouTube playlist HTML",
        )

    try:
        data = json.loads(match.group(1))
        contents = data["contents"]["twoColumnBrowseResultsRenderer"]["tabs"][0][
            "tabRenderer"
        ]["content"]["sectionListRenderer"]["contents"][0]["itemSectionRenderer"][
            "contents"
        ][0]["playlistVideoListRenderer"]["contents"]
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as e:
        raise ParseError(
            f"Failed to parse latest YouTube video: {e}",
        ) from e

    playlist = []

    for item in contents:
        renderer = item.get("playlistVideoRenderer")
        video = parse_playlist_video_renderer(renderer)
        if video:
            playlist.append(video)
    return playlist


def parse_playlist_video_renderer(renderer: dict | None) -> tuple[str, str] | None:
    """从 playlistVideoRenderer 提取视频 ID 和标题"""
    if not renderer:
        return None

    video_id = renderer.get("videoId")
    if video_id:
        video_id = f"https://www.youtube.com/watch?v={video_id}"
    title_obj = renderer.get("title") or {}
    if "runs" in title_obj:
        title = "".join(item.get("text", "") for item in title_obj["runs"])
    else:
        title = title_obj.get("simpleText", "")

    if not video_id or not title:
        return None
    return video_id, html.unescape(title)


def find_latest_video_url(
    playlist_html: str,
    keywords: tuple[str, ...],
    *,
    reverse: bool,
) -> tuple[str, str]:
    """从 YouTube 播放列表页面提取匹配关键词的视频 URL"""
    playlist = get_playlist_videos(playlist_html)
    if not playlist:
        raise ParseError("YouTube playlist contains no playable videos")
    if reverse:
        playlist = playlist[::-1]
    for video, title in playlist:
        if all(keyword in title for keyword in keywords):
            return video, title
    raise ParseError(
        f"No matching YouTube playlist video found for keywords: {', '.join(keywords)}"
    )


def extract_youtube_redirect_url(
    video_html: str,
    target_host: str,
) -> str:
    """从 YouTube redirect 链接中提取指定目标站点 URL"""
    escaped_host = re.escape(target_host)
    matches = re.findall(
        rf"q=(https%3A%2F%2F{escaped_host}%2F.+?)(?:\\u0026|&)",
        video_html,
    )
    if not matches:
        raise ParseError(f"No {target_host} URL found")

    return unquote(matches[-1])


check_playlist = check_html_contains("playlistVideoRenderer")


def get_playlist_html(http_client: HttpClient, url: str) -> str:
    playlist_html = http_client.get(url, timeout=10, check_html=check_playlist)
    return playlist_html
