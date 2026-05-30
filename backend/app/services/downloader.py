from pathlib import Path
from typing import Any
import importlib
import os


def _load_yt_dlp() -> Any:
    """Dynamically import `yt_dlp` at runtime.

    This avoids static import errors in local editors where the
    dependency is only provided inside the Docker container.
    """
    try:
        return importlib.import_module("yt_dlp")
    except Exception as exc:
        raise ImportError(
            "yt_dlp is required at runtime. Install it in the runtime environment (Docker)."
        ) from exc


def download_video(url: str, raw_dir: Path, progress_callback=None) -> Path:
    raw_dir.mkdir(parents=True, exist_ok=True)
    output_template = str(raw_dir / "%(id)s.%(ext)s")
    ydl_opts = {
        "format": "bestvideo[ext=mp4][vcodec!*=av01][vcodec!*=av1]+bestaudio[ext=m4a]/best[ext=mp4][vcodec!*=av01]/best",
        "outtmpl": output_template,
        "merge_output_format": "mp4",
        "quiet": True,
        "noprogress": False,
        "no_warnings": True,
        "retries": 5,
        "nocheckcertificate": True,
        "source_address": "0.0.0.0",
        "continuedl": True,
        "noplaylist": True,
        "nopart": True,
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            "Referer": "https://www.youtube.com/",
            "Accept-Language": "en-US,en;q=0.9",
        },
        "geo_bypass": True,
    }

    if progress_callback:
        import re
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        
        def hook(d):
            if d['status'] == 'downloading':
                def clean(text):
                    return ansi_escape.sub('', text).strip() if text else ''

                percent = clean(d.get('_percent_str', ''))
                speed = clean(d.get('_speed_str', ''))
                eta = clean(d.get('_eta_str', ''))
                downloaded = clean(d.get('_downloaded_bytes_str', ''))
                
                # yt-dlp sometimes uses estimated total
                total = clean(d.get('_total_bytes_str', '')) or clean(d.get('_total_bytes_estimate_str', ''))

                if percent:
                    msg_parts = [f"{percent}"]
                    if downloaded and total:
                        msg_parts.append(f"({downloaded} / {total})")
                    if speed:
                        msg_parts.append(f"@ {speed}")
                    if eta:
                        msg_parts.append(f"ETA {eta}")
                        
                    progress_callback(" ".join(msg_parts))

        ydl_opts["progress_hooks"] = [hook]

    # Support cookies file (for age-restricted / login-required videos)
    cookies_file = os.environ.get("YT_COOKIES_FILE")
    if cookies_file:
        cookies_path = Path(cookies_file)
        if cookies_path.exists():
            ydl_opts["cookiefile"] = str(cookies_path)

    yt_dlp = _load_yt_dlp()
    YoutubeDL = getattr(yt_dlp, "YoutubeDL")

    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            video_id = info.get("id")
            ext = info.get("ext", "mp4")
    except Exception as exc:
        msg = str(exc)
        if (
            "Sign in to confirm" in msg
            or "--cookies-from-browser" in msg
            or "Use --cookies" in msg
        ):
            raise RuntimeError(
                "Download failed because the video requires authentication. "
                "Provide a browser cookies file and mount it into the container, "
                "then set the environment variable YT_COOKIES_FILE to its path "
                "(e.g. /app/data/cookies.txt).\n\n"
                "You can export cookies using yt-dlp on your host: "
                "`yt-dlp --cookies-from-browser chrome --cookies ./cookies.txt` "
                "and mount the file into /app/data in docker-compose."
            ) from exc
        raise

    file_path = raw_dir / f"{video_id}.{ext}"
    if not file_path.exists():
        raise FileNotFoundError(f"Video unduhan tidak ditemukan: {file_path}")
    return file_path
