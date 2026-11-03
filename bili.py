"""Bilibili helpers: parse a link, get public metadata, pick a quality.

No login, no cookies and no DRM bypass are used here. Only the public
view API and, for download, the standard yt-dlp tool are used. That means
paid, VIP-only or region-locked videos will not be available, which is
expected. Only download videos you own or have permission to download,
and respect Bilibili's terms and the creator's copyright.
"""

import re
import urllib.parse

import requests

BV_RE = re.compile(r"BV[0-9A-Za-z]{10}")
AV_RE = re.compile(r"av(\d+)", re.IGNORECASE)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Referer": "https://www.bilibili.com/",
}


def parse_bilibili_url(raw):
    """Return a dict with kind, id, canonical_url and embed_url.

    Accepted inputs: a full bilibili.com/video link, a b23.tv short
    link, a plain BV id, or a plain av id. A b23.tv link is returned
    as-is here; yt-dlp and the browser resolve its redirect, so the
    caller does not need to pre-resolve it to get an embed for a BV id
    found in the final URL.
    """
    if not raw or not isinstance(raw, str):
        raise ValueError("Chua nhap link Bilibili.")
    text = raw.strip()
    bv = BV_RE.search(text)
    if bv:
        bvid = bv.group(0)
        return {
            "kind": "BV",
            "id": bvid,
            "canonical_url": f"https://www.bilibili.com/video/{bvid}",
            "embed_url": (
                "https://player.bilibili.com/player.html"
                f"?bvid={bvid}&high_quality=1&danmaku=0"
            ),
        }
    av = AV_RE.search(text)
    if av:
        aid = av.group(1)
        return {
            "kind": "av",
            "id": aid,
            "canonical_url": f"https://www.bilibili.com/video/av{aid}",
            "embed_url": (
                "https://player.bilibili.com/player.html"
                f"?aid={aid}&high_quality=1&danmaku=0"
            ),
        }
    # A bare b23.tv link has no BV id in it. Keep it as the canonical
    # URL and let yt-dlp follow the redirect when downloading.
    if "b23.tv" in text:
        return {
            "kind": "short",
            "id": text,
            "canonical_url": text,
            "embed_url": "",
        }
    raise ValueError("Khong tim thay BV id hoac av id trong link.")


def get_video_info(parsed):
    """Fetch public metadata from Bilibili's view API.

    Returns title, owner, cover, duration and pages (cid/part). For a
    short link or an unknown id this raises ValueError with the API
    message, so the caller can still fall back to the official embed.
    """
    if parsed["kind"] == "BV":
        params = {"bvid": parsed["id"]}
    elif parsed["kind"] == "av":
        params = {"aid": parsed["id"]}
    else:
        raise ValueError("Link rut gon b23.tv can mo tren trinh duyet de lay BV id.")
    resp = requests.get(
        "https://api.bilibili.com/x/web-interface/view",
        params=params,
        headers=HEADERS,
        timeout=20,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0:
        raise ValueError(f"Bilibili API: {data.get('message', 'unknown error')}")
    info = data["data"]
    return {
        "title": info.get("title"),
        "owner": (info.get("owner") or {}).get("name"),
        "cover": info.get("pic"),
        "duration": info.get("duration"),
        "pages": [
            {"cid": p.get("cid"), "part": p.get("part"), "duration": p.get("duration")}
            for p in info.get("pages") or []
        ],
    }


def quality_to_max_height(quality):
    """Map a user quality choice to a maximum height.

    'best' means the highest available format. '1080' is the default
    'highest, or one step lower' choice: it keeps full HD while avoiding
    very large 4K files. '720' and '480' are the lower options.
    """
    mapping = {"best": None, "1080": 1080, "720": 720, "480": 480}
    if quality not in mapping:
        raise ValueError("Chat luong phai la best, 1080, 720 hoac 480.")
    return mapping[quality]


def ytdlp_format(quality):
    """Return a yt-dlp format string for the chosen quality."""
    max_height = quality_to_max_height(quality)
    if max_height is None:
        return "bestvideo+bestaudio/best"
    return (
        f"bestvideo[height<={max_height}]+bestaudio/"
        f"best[height<={max_height}]/best"
    )


def pick_format(formats, quality):
    """Pick one format dict from a yt-dlp format list, for testing.

    Formats are expected to have height, ext and format_id. Returns
    the highest format at or below the chosen height, or the lowest
    format above it when nothing fits, or the highest overall for
    'best'. Returns None when the list is empty.
    """
    if not formats:
        return None
    max_height = quality_to_max_height(quality)
    videos = [f for f in formats if f.get("height")]
    if not videos:
        return formats[0]
    if max_height is None:
        return max(videos, key=lambda f: f["height"])
    fitting = [f for f in videos if f["height"] <= max_height]
    if fitting:
        return max(fitting, key=lambda f: f["height"])
    return min(videos, key=lambda f: f["height"])


def download_filename(title, ext="mp4"):
    """Make a safe filename from a video title."""
    safe = re.sub(r'[\\/:*?"<>|]', "_", title or "bilibili-video").strip()
    safe = safe[:120] or "bilibili-video"
    return f"{safe}.{ext}"
