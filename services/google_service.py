import re
import webbrowser
from urllib.parse import quote_plus

import requests

from core.config import api_logger, config


YOUTUBE_SEARCH_URL = "https://www.youtube.com/results"
YOUTUBE_WATCH_URL = "https://www.youtube.com/watch?v={video_id}"


def normalize_youtube_query(command):
    """Extract the actual video/song query from a user command."""
    query = command.strip()
    query = re.sub(r"^(please\s+)?(play|open)\s+", "", query, flags=re.IGNORECASE)
    query = re.sub(r"^(the\s+)?(song|video)\s+", "", query, flags=re.IGNORECASE)
    query = re.split(r"\s+on\s+youtube\b", query, maxsplit=1, flags=re.IGNORECASE)[0]
    query = re.split(r"\s+not\s+the\s+search\b", query, maxsplit=1, flags=re.IGNORECASE)[0]
    query = re.sub(r"\byoutube\b", "", query, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", query).strip(" .,!?:;\"'")


def _get_youtube_api_key():
    return config.YOUTUBE_API_KEY or config.GOOGLE_API_KEY


def _find_video_id_with_api(query):
    api_key = _get_youtube_api_key()
    if not api_key:
        return None

    params = {
        "part": "id",
        "type": "video",
        "maxResults": 1,
        "q": query,
        "key": api_key,
    }

    try:
        response = requests.get(
            "https://www.googleapis.com/youtube/v3/search",
            params=params,
            timeout=10,
        )
        if response.status_code in (400, 401, 403):
            api_logger.warning(
                "YouTube Data API unavailable or unauthorized; falling back to page search."
            )
            return None
        response.raise_for_status()
        items = response.json().get("items", [])
        if not items:
            return None
        return items[0].get("id", {}).get("videoId")
    except Exception as exc:
        api_logger.warning(f"YouTube Data API search failed: {exc}")
        return None


def _find_video_id_from_page(query):
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0 Safari/537.36"
        )
    }
    params = {"search_query": query}

    try:
        response = requests.get(
            YOUTUBE_SEARCH_URL,
            params=params,
            headers=headers,
            timeout=10,
        )
        response.raise_for_status()
    except Exception as exc:
        api_logger.error(f"YouTube page search failed: {exc}")
        return None

    matches = re.findall(r'"videoId":"([a-zA-Z0-9_-]{11})"', response.text)
    if not matches:
        matches = re.findall(r"/watch\?v=([a-zA-Z0-9_-]{11})", response.text)

    for video_id in matches:
        if video_id:
            return video_id
    return None


def find_youtube_video(query):
    clean_query = normalize_youtube_query(query)
    if not clean_query:
        return {"success": False, "error": "Please tell me what to play on YouTube."}

    video_id = _find_video_id_with_api(clean_query) or _find_video_id_from_page(clean_query)
    if not video_id:
        return {
            "success": False,
            "query": clean_query,
            "error": f"I couldn't find a YouTube video for {clean_query}.",
        }

    return {
        "success": True,
        "query": clean_query,
        "video_id": video_id,
        "url": YOUTUBE_WATCH_URL.format(video_id=video_id),
    }


def play_youtube_video(query, open_browser=True):
    result = find_youtube_video(query)
    if not result["success"]:
        return result

    if open_browser:
        try:
            opened = webbrowser.open(result["url"])
        except Exception as exc:
            api_logger.error(f"Failed to open YouTube watch URL: {exc}")
            return {
                "success": False,
                "query": result["query"],
                "url": result["url"],
                "error": "I found the video, but couldn't open it in your browser.",
            }
        if not opened:
            return {
                "success": False,
                "query": result["query"],
                "url": result["url"],
                "error": "I found the video, but your browser did not accept the URL.",
            }

    api_logger.info(f"Opened YouTube watch URL for query: {result['query']}")
    return result


def search_youtube(topic):
    """Backward-compatible wrapper. Now opens the best video, not search results."""
    return play_youtube_video(topic)
