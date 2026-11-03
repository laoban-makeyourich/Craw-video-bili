"""CLI: inspect or download a Bilibili video.

Examples:
    python cli.py --url "https://www.bilibili.com/video/BV..." --info-only
    python cli.py --url "https://www.bilibili.com/video/BV..." --quality 1080 --download
    python cli.py --url "https://www.bilibili.com/video/BV..." --quality best --download

Only download videos you own or have permission to download.
"""

import argparse
import subprocess
import sys

from bili import get_video_info, parse_bilibili_url, ytdlp_format


def main():
    parser = argparse.ArgumentParser(description="Craw-video-bili CLI")
    parser.add_argument("--url", required=True, help="Link Bilibili, BV id hoac av id")
    parser.add_argument("--quality", default="1080", choices=["best", "1080", "720", "480"])
    parser.add_argument("--info-only", action="store_true")
    parser.add_argument("--download", action="store_true")
    parser.add_argument("--outdir", default="downloads")
    args = parser.parse_args()

    parsed = parse_bilibili_url(args.url)
    print(f"Parsed: {parsed['kind']} {parsed['id']}")
    print(f"Canonical: {parsed['canonical_url']}")
    if parsed["embed_url"]:
        print(f"Embed: {parsed['embed_url']}")
    try:
        info = get_video_info(parsed)
        print(f"Title: {info['title']}")
        print(f"Owner: {info['owner']}")
        print(f"Duration: {info['duration']}s")
        for page in info["pages"]:
            print(f"  Part: {page['part']} (cid={page['cid']})")
    except Exception as exc:  # noqa: BLE001
        print(f"Info warning: {exc}")

    if args.info_only or not args.download:
        print(f"Format for quality {args.quality}: {ytdlp_format(args.quality)}")
        if not args.download:
            print("Them --download de tai ve.")
        return 0

    from downloader import download_video

    result = download_video(parsed["canonical_url"], args.quality, args.outdir)
    print(f"Downloaded: {result['output']}")
    print(f"Height: {result['height']}p, size: {result['size']} bytes, "
          f"time: {result['seconds']}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
