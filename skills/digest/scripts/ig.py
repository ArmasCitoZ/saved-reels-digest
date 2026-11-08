"""Gentle access to individual posts: yt-dlp first, instaloader session as fallback.

Instagram posts are addressed by shortcode. Other platforms (TikTok favorites)
pass the post's own URL and only use yt-dlp: instaloader is Instagram-only.

Requests are spaced out and every caller stops after a few consecutive
failures, so a rate limit or an expired login never turns into hammering
Instagram with your account.
"""
from __future__ import annotations

import random
import shutil
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


class Unavailable(Exception):
    """The post was deleted, or its account is private: skip it, it will not come back."""


class NetworkError(RuntimeError):
    """Our own connection failed (offline, DNS, timeout): the post is fine, try it again later."""


BLOCKED_HINTS = ("login", "rate", "429", "401", "checkpoint", "challenge", "sign in to confirm")
# what yt-dlp / instaloader say when the post itself is gone or hidden
UNAVAILABLE_HINTS = ("404", "not found", "not available", "unavailable", "does not exist",
                     "has been removed", "been deleted", "private", "restricted")

# what Python / yt-dlp / requests say when the connection itself is the problem
NETWORK_HINTS = ("timed out", "timeout", "connection reset", "connection refused",
                 "connection aborted", "connectionerror", "remote end closed",
                 "temporary failure in name resolution", "name or service not known",
                 "nodename nor servname", "getaddrinfo failed", "failed to resolve",
                 "network is unreachable", "no route to host", "urlopen error",
                 "max retries exceeded", "read error", "incompleteread")


def _is_network(part: str) -> bool:
    low = part.lower()
    return any(k in low for k in NETWORK_HINTS)


def classify_error(msg: str) -> str:
    """'blocked' (stop the run), 'network' (our connection dropped: retry later),
    'unavailable' (deleted/private post) or 'failed' (anything else).

    Blocked wins: when Instagram rate-limits it often also says "not available".
    Network only when every source failed to connect ("yt-dlp: ... | instaloader: ...");
    if one of them got a real answer, the problem is the post, not the connection.
    """
    low = msg.lower()
    if any(k in low for k in BLOCKED_HINTS):
        return "blocked"
    parts = [p for p in msg.split(" | ") if p.strip()]
    if parts and all(_is_network(p) for p in parts):
        return "network"
    if any(k in low for k in UNAVAILABLE_HINTS):
        return "unavailable"
    return "failed"


def _raise_for(msg: str):
    kind = classify_error(msg)
    if kind == "blocked":
        raise Blocked(msg)
    if kind == "unavailable":
        raise Unavailable(msg)
    if kind == "network":
        raise NetworkError(msg)
    raise RuntimeError(msg)


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

    def _ydl_info(self, shortcode, download_to: Path | None = None, url: str | None = None):
        import yt_dlp

        extra = {"skip_download": True}
        if download_to:
            extra = {"format": "bestaudio/best[filesize<80M]/best",
                     "outtmpl": str(download_to / f"{shortcode}.%(ext)s")}
        with yt_dlp.YoutubeDL(self._ydl_opts(**extra)) as ydl:
            info = ydl.extract_info(url or canonical_url(shortcode), download=bool(download_to))
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
    @staticmethod
    def is_instagram(url: str | None) -> bool:
        return not url or "instagram.com" in url

    def metadata(self, shortcode: str, url: str | None = None) -> dict:
        self._wait()
        errors = []
        try:
            i = self._ydl_info(shortcode, url=url)
            return {"caption": i.get("description") or i.get("title") or "",
                    "author": i.get("channel") or i.get("uploader_id") or i.get("uploader"),
                    "duration": i.get("duration"), "is_video": bool(i.get("duration")),
                    "posted_at": i.get("timestamp")}
        except Exception as e:  # noqa: BLE001
            errors.append(f"yt-dlp: {str(e)[:160]}")
            if not self.is_instagram(url):
                _raise_for(errors[0])
        try:
            p = self._il_post(shortcode)
            return {"caption": p.caption or "", "author": p.owner_username,
                    "duration": p.video_duration if p.is_video else None,
                    "is_video": p.is_video, "posted_at": int(p.date_utc.timestamp())}
        except Exception as e:  # noqa: BLE001
            errors.append(f"instaloader: {str(e)[:160]}")
        _raise_for(" | ".join(errors))

    def image_urls(self, shortcode: str) -> list:
        """Image URLs of a photo or carousel post (videos inside a carousel are skipped)."""
        self._wait()
        try:
            p = self._il_post(shortcode)
            if p.typename == "GraphSidecar":
                return [n.display_url for n in p.get_sidecar_nodes() if not n.is_video]
            return [] if p.is_video else [p.url]
        except Exception as e:  # noqa: BLE001
            _raise_for(f"instaloader: {str(e)[:160]}")

    def download_images(self, shortcode: str, folder: Path, max_images: int = 10) -> list:
        """Save a post's images as 01.jpg, 02.jpg... in folder and return their paths."""
        urls = self.image_urls(shortcode)[:max_images]
        folder.mkdir(parents=True, exist_ok=True)
        paths = []
        try:
            for n, url in enumerate(urls, 1):
                if n > 1:
                    time.sleep(random.uniform(0.2, 0.6))
                dest = folder / f"{n:02d}.jpg"
                urllib.request.urlretrieve(url, dest)  # signed CDN URL, no login needed
                paths.append(dest)
        except Exception as e:  # noqa: BLE001
            shutil.rmtree(folder, ignore_errors=True)  # never leave half a carousel behind
            _raise_for(f"image: {str(e)[:160]}")
        return paths

    def download_audio(self, shortcode: str, folder: Path, url: str | None = None) -> Path:
        self._wait()
        errors = []
        try:
            f = self._ydl_info(shortcode, download_to=folder, url=url).get("_file")
            if f:
                return f
            errors.append("yt-dlp: no file downloaded")
        except Exception as e:  # noqa: BLE001
            errors.append(f"yt-dlp: {str(e)[:160]}")
        if not self.is_instagram(url):
            _raise_for(errors[0])
        try:
            p = self._il_post(shortcode)
            if not p.is_video:
                raise RuntimeError("not a video")
            dest = folder / f"{shortcode}.mp4"
            urllib.request.urlretrieve(p.video_url, dest)  # signed CDN URL, no login needed
            return dest
        except Exception as e:  # noqa: BLE001
            errors.append(f"instaloader: {str(e)[:160]}")
        _raise_for(" | ".join(errors))
