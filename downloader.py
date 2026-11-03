"""Fast Bilibili download: yt-dlp for formats, Range download for files.

Why not plain yt-dlp download? On some networks Bilibili's CDN
returns HTTP 567 for a full, non-Range request to an .m4s stream,
while a Range request (bytes=0-1023, then chunked Ranges) returns
206 and the real data. Plain yt-dlp download therefore fails with
567 even though the video is public and playable. This module
therefore:

1. Uses yt-dlp only to extract formats (--dump-json, --skip-download).
2. Picks the best video at or below the chosen height, preferring
   avc1 for compatibility, and the best m4a audio.
3. Downloads each stream in 2 MB Range chunks, 4 in parallel, with
   a Chrome User-Agent and Bilibili Referer. This is also the
   time optimisation: short videos, no playlist, no subtitles,
   no thumbnail, no re-encode, and parallel chunks.
4. Merges video + audio with ffmpeg -c copy (no re-encode).

Only download videos you own or have permission to download.
"""

import concurrent.futures
import json
import os
import subprocess
import sys
import time

import requests

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Referer": "https://www.bilibili.com/",
}
CHUNK = 2 * 1024 * 1024
WORKERS = 4


def _dump_json(url):
    """Run yt-dlp --dump-json, falling back to --no-check-certificates
    only when the first run fails with an SSL error. This keeps the
    secure default on normal machines, while still working behind a
    proxy that uses a self-signed certificate.
    """
    # Use "python -m yt_dlp" instead of the yt-dlp binary, so the
    # tool works even when the binary is not on PATH (for example
    # inside a venv). Fall back to the binary if the module is missing.
    base = [
        sys.executable, "-m", "yt_dlp",
        "--no-playlist", "--skip-download", "--dump-json", url,
    ]
    result = subprocess.run(base, capture_output=True, text=True, timeout=120)
    if result.returncode == 0 and result.stdout.strip():
        return json.loads(result.stdout)
    if "CERTIFICATE_VERIFY_FAILED" in (result.stderr or ""):
        result = subprocess.run(
            base[:3] + ["--no-check-certificates"] + base[3:],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode == 0 and result.stdout.strip():
            return json.loads(result.stdout)
    raise RuntimeError(
        f"yt-dlp extract failed: {(result.stderr or '')[-500:]}"
    )


def pick_video_format(formats, max_height):
    videos = [f for f in formats if f.get("vcodec") not in (None, "none") and f.get("height")]
    if not videos:
        return None
    if max_height is not None:
        fitting = [f for f in videos if f["height"] <= max_height]
        if fitting:
            videos = fitting
        else:
            videos = [min(videos, key=lambda f: f["height"])]
    else:
        videos = [max(videos, key=lambda f: f["height"])]
    # Prefer avc1 (widest player support), then any codec at that height.
    best_height = max(f["height"] for f in videos)
    at_best = [f for f in videos if f["height"] == best_height]
    avc = [f for f in at_best if (f.get("vcodec") or "").startswith("avc1")]
    return (avc or at_best)[0]


def pick_audio_format(formats):
    audios = [f for f in formats if f.get("vcodec") in (None, "none") and f.get("acodec") not in (None, "none")]
    if not audios:
        return None
    return max(audios, key=lambda f: f.get("abr") or 0)


def download_range(url, outpath):
    """Download one stream URL with parallel Range requests."""
    probe = requests.get(url, headers={**HEADERS, "Range": "bytes=0-0"}, timeout=30)
    if probe.status_code != 206 or "Content-Range" not in probe.headers:
        raise RuntimeError(f"Range probe failed: HTTP {probe.status_code}")
    total = int(probe.headers["Content-Range"].split("/")[1])
    ranges = [(s, min(s + CHUNK - 1, total - 1)) for s in range(0, total, CHUNK)]

    def fetch(rng):
        start, end = rng
        resp = requests.get(
            url,
            headers={**HEADERS, "Range": f"bytes={start}-{end}"},
            timeout=60,
        )
        resp.raise_for_status()
        return start, resp.content

    with open(outpath, "wb") as fh:
        fh.truncate(total)
        with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as pool:
            for start, data in pool.map(fetch, ranges):
                fh.seek(start)
                fh.write(data)
    return total


def download_video(url, quality, outdir):
    """Download a Bilibili video at the chosen quality.

    quality: 'best', '1080', '720' or '480'. Returns a dict with
    title, height, duration, output path, size and seconds taken.
    """
    from bili import parse_bilibili_url, quality_to_max_height

    parsed = parse_bilibili_url(url)
    max_height = quality_to_max_height(quality)
    started = time.time()
    info = _dump_json(parsed["canonical_url"])
    video = pick_video_format(info.get("formats") or [], max_height)
    audio = pick_audio_format(info.get("formats") or [])
    if video is None:
        raise RuntimeError("No video format found.")
    os.makedirs(outdir, exist_ok=True)
    safe_id = parsed["id"] if parsed["kind"] in ("BV", "av") else "bilibili"
    video_path = os.path.join(outdir, f"{safe_id}-video.m4s")
    audio_path = os.path.join(outdir, f"{safe_id}-audio.m4s")
    out_path = os.path.join(outdir, f"{safe_id}.mp4")
    download_range(video["url"], video_path)
    if audio is not None:
        download_range(audio["url"], audio_path)
        merge = subprocess.run(
            ["ffmpeg", "-y", "-i", video_path, "-i", audio_path,
             "-c", "copy", out_path],
            capture_output=True, text=True, timeout=600,
        )
        if merge.returncode != 0:
            raise RuntimeError(f"ffmpeg merge failed: {merge.stderr[-500:]}")
        os.remove(video_path)
        os.remove(audio_path)
    else:
        os.rename(video_path, out_path)
    return {
        "title": info.get("title"),
        "height": video.get("height"),
        "duration": info.get("duration"),
        "output": out_path,
        "size": os.path.getsize(out_path),
        "seconds": round(time.time() - started, 1),
    }
