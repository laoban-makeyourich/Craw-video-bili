"""Web app: paste a Bilibili link, watch it, download it.

Run:
    pip install -r requirements.txt
    python app.py

Then open http://127.0.0.1:5000

Playback uses Bilibili's official embed player, so quality selection
inside the player stays with Bilibili. Download uses yt-dlp on the
server and defaults to 1080p, the 'highest, or one step lower' choice,
unless you pick 'best', 720 or 480. Only download videos you own or
have permission to download.
"""

import os
import subprocess

from flask import Flask, jsonify, redirect, render_template_string, request, send_file

from bili import get_video_info, parse_bilibili_url, quality_to_max_height, ytdlp_format

app = Flask(__name__)
DOWNLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "downloads")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

INDEX_HTML = """
<!doctype html>
<html lang="vi"><head><meta charset="utf-8">
<title>Craw-video-bili</title>
<style>body{font-family:system-ui,sans-serif;max-width:760px;margin:40px auto;padding:0 16px}
input,select{padding:10px;width:100%;box-sizing:border-box;margin:8px 0}
button{padding:10px 18px;cursor:pointer}</style></head>
<body>
<h1>Craw-video-bili</h1>
<p>Nhap link video Bilibili, xem bang player chinh thuc cua Bilibili,
va tai ve o chat luong cao nhat hoac thap hon mot chut.</p>
<form action="/watch" method="get">
  <label>Link Bilibili</label>
  <input name="url" placeholder="https://www.bilibili.com/video/BV..." required>
  <label>Chat luong tai ve</label>
  <select name="quality">
    <option value="1080">1080p (mac dinh, cao nhung nhe hon 4K)</option>
    <option value="best">Cao nhat co san</option>
    <option value="720">720p</option>
    <option value="480">480p</option>
  </select>
  <button type="submit">Xem va tai</button>
</form>
<p><small>Chi tai video ban so huu hoac duoc phep tai. Ton trong ban quyen
va dieu khoan cua Bilibili.</small></p>
</body></html>
"""

WATCH_HTML = """
<!doctype html>
<html lang="vi"><head><meta charset="utf-8"><title>{{ title }}</title>
<style>body{font-family:system-ui,sans-serif;max-width:900px;margin:32px auto;padding:0 16px}
iframe{width:100%;height:520px;border:0}</style></head>
<body>
<p><a href="/">← Nhap link khac</a></p>
<h1>{{ title }}</h1>
{% if owner %}<p>Tac gia: {{ owner }} | Thoi luong: {{ duration }} giay</p>{% endif %}
{% if cover %}<p><img src="{{ cover }}" style="max-width:100%"></p>{% endif %}
{% if embed_url %}<iframe src="{{ embed_url }}" allowfullscreen></iframe>{% endif %}
<p><a href="{{ download_url }}">Tai ve ({{ quality_label }})</a> |
<a href="{{ canonical_url }}" target="_blank">Mo tren Bilibili</a></p>
{% if error %}<p style="color:#a00">{{ error }}</p>{% endif %}
</body></html>
"""


@app.route("/")
def index():
    return render_template_string(INDEX_HTML)


@app.route("/api/info")
def api_info():
    try:
        parsed = parse_bilibili_url(request.args.get("url", ""))
        info = get_video_info(parsed)
    except Exception as exc:  # noqa: BLE001 - show the reason to the user
        return jsonify({"ok": False, "error": str(exc)}), 400
    return jsonify({"ok": True, "parsed": parsed, "info": info})


@app.route("/watch")
def watch():
    url = request.args.get("url", "")
    quality = request.args.get("quality", "1080")
    try:
        quality_to_max_height(quality)
        parsed = parse_bilibili_url(url)
    except Exception as exc:  # noqa: BLE001
        return f"<p>Loi: {exc}</p><p><a href='/'>Quay lai</a></p>", 400
    info, error = {}, ""
    try:
        info = get_video_info(parsed)
    except Exception as exc:  # noqa: BLE001 - embed still works
        error = f"Khong lay duoc thong tin chi tiet: {exc}. Van xem duoc bang player ben duoi."
    quality_label = "cao nhat" if quality == "best" else f"{quality}p"
    return render_template_string(
        WATCH_HTML,
        title=info.get("title") or parsed["id"],
        owner=info.get("owner"),
        duration=info.get("duration"),
        cover=info.get("cover"),
        embed_url=parsed["embed_url"],
        canonical_url=parsed["canonical_url"],
        download_url=f"/download?url={parsed['canonical_url']}&quality={quality}",
        quality_label=quality_label,
        error=error,
    )


@app.route("/download")
def download():
    url = request.args.get("url", "")
    quality = request.args.get("quality", "1080")
    try:
        parsed = parse_bilibili_url(url)
        fmt = ytdlp_format(quality)
    except Exception as exc:  # noqa: BLE001
        return f"<p>Loi: {exc}</p>", 400
    try:
        from downloader import download_video

        result = download_video(parsed["canonical_url"], quality, DOWNLOAD_DIR)
    except Exception as exc:  # noqa: BLE001
        return (
            "<p>Khong tai duoc video. Video co the la VIP, gioi han vung, "
            "hoac can dang nhap.</p>"
            f"<pre>{exc}</pre>"
            "<p><a href='/'>Quay lai</a></p>"
        ), 502
    return send_file(
        result["output"], as_attachment=True,
        download_name=os.path.basename(result["output"]),
    )


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
