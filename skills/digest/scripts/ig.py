"""Gentle access to individual posts: yt-dlp first, instaloader session as fallback.

Requests are spaced out and every caller stops after a few consecutive
failures, so a rate limit or an expired login never turns into hammering
Instagram with your account.
"""
from __future__ import annotations

import random
import time
import urllib.request
from pathlib import Path

from common import SESSION_DIR, canonical_url, log


class _Silent:
    def debug(self, msg): pass
    def info(self, msg): pass
    def warning(self, msg): pass
    def error(self, msg): pass


class Blocked(Exception):
    """Instagram is asking for login / rate limiting: stop the whole run."""


class Fetcher:
    def __init__(self, browser: str | None = None, username: str | None = None,
                 delay: float = 3.0):
        self.browser, self.username, self.delay = browser, username, delay
        self._L = None
        self._last = 0.0

    # ------------------------------------------------------------ pacing
    def _wait(self):
        gap = self.delay * random.uniform(0.7, 1.6)
        sleep = self._last + gap - time.time()
        if sleep > 0:
            time.sleep(sleep)
        self._last = time.time()

    # ------------------------------------------------------------ yt-dlp
    def _ydl_opts(self, **extra):
        opts = {"quiet": True, "no_warnings": True, "noprogress": True,
                "socket_timeout": 30, "retries": 2, "logger": _Silent()}
        if self.browser:
            opts["cookiesfrombrowser"] = (self.browser,)
        opts.update(extra)
        return opts

    def _ydl_info(self, shortcode, download_to: Path | None = None):
        import yt_dlp

        extra = {"skip_download": True}
        if download_to:
            extra = {"format": "bestaudio/best[filesize<80M]/best",
                     "outtmpl": str(download_to / f"{shortcode}.%(ext)s")}
        with yt_dlp.YoutubeDL(self._ydl_opts(**extra)) as ydl:
            info = ydl.extract_info(canonical_url(shortcode), download=bool(download_to))
            if download_to:
                files = [p for p in download_to.glob(f"{shortcode}.*") if not p.name.endswith(".part")]
                info["_file"] = files[0] if files else None
            return info

    # -------------------------------------------------------- instaloader
    def _loader(self):
        if self._L is None:
            import instaloader

            L = instaloader.Instaloader(quiet=True, max_connection_attempts=1)
            if self.username:
                sf = SESSION_DIR / f"session-{self.username}"
                L.load_session_from_file(self.username, str(sf) if sf.exists() else None)
            elif self.browser:
                try:
                    from instaloader.__main__ import import_session
                    import_session(self.browser, L, None)
                except Exception as e:  # noqa: BLE001
                    log(f"instaloader: could not reuse {self.browser} session ({e}); anonymous")
            self._L = L
        return self._L

    def _il_post(self, shortcode):
        import instaloader

        return instaloader.Post.from_shortcode(self._loader().context, shortcode)

    # ------------------------------------------------------------- public
    def metadata(self, shortcode: str) -> dict:
        self._wait()
        errors = []
        try:
            i = self._ydl_info(shortcode)
            return {"caption": i.get("description") or i.get("title") or "",
                    "author": i.get("channel") or i.get("uploader_id") or i.get("uploader"),
                    "duration": i.get("duration"), "is_video": bool(i.get("duration")),
                    "posted_at": i.get("timestamp")}
        except Exception as e:  # noqa: BLE001
            errors.append(f"yt-dlp: {str(e)[:160]}")
        try:
            p = self._il_post(shortcode)
            return {"caption": p.caption or "", "author": p.owner_username,
                    "duration": p.video_duration if p.is_video else None,
                    "is_video": p.is_video, "posted_at": int(p.date_utc.timestamp())}
        except Exception as e:  # noqa: BLE001
            errors.append(f"instaloader: {str(e)[:160]}")
        msg = " | ".join(errors)
        if any(k in msg.lower() for k in ("login", "rate", "429", "401", "checkpoint", "challenge")):
            raise Blocked(msg)
        raise RuntimeError(msg)

    def download_audio(self, shortcode: str, folder: Path) -> Path:
        self._wait()
        errors = []
        try:
            f = self._ydl_info(shortcode, download_to=folder).get("_file")
            if f:
                return f
        except Exception as e:  # noqa: BLE001
            errors.append(f"yt-dlp: {str(e)[:160]}")
        try:
            p = self._il_post(shortcode)
            if not p.is_video:
                raise RuntimeError("not a video")
            dest = folder / f"{shortcode}.mp4"
            urllib.request.urlretrieve(p.video_url, dest)  # signed CDN URL, no login needed
            return dest
        except Exception as e:  # noqa: BLE001
            errors.append(f"instaloader: {str(e)[:160]}")
        msg = " | ".join(errors)
        if any(k in msg.lower() for k in ("login", "rate", "429", "401", "checkpoint", "challenge")):
            raise Blocked(msg)
        raise RuntimeError(msg)
