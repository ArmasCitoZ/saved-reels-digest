"""Collect the list of your saved posts into the local database.

Three sources, pick one:

  collect.py export PATH        Official Instagram data export (zip, folder or a
                                single saved_posts.json / .html). Safest: no
                                automated access to your account at all.
  collect.py live --browser chrome [--limit N]
  collect.py live --username YOU [--limit N]
                                Reads your saved feed live with instaloader,
                                reusing the session of a browser where you are
                                logged in (or a saved instaloader session).
  collect.py urls FILE|-        Plain list of links, one per line (for example
                                gathered by Claude from your browser).

TikTok too:

  collect.py tiktok PATH        TikTok's official data export (zip, folder or the
                                user_data JSON / "Favorite Videos.txt"). Reads your
                                Favorites, TikTok's equivalent of saved posts.

And YouTube:

  collect.py youtube PATH [--playlist NAME]
                                Google Takeout of "YouTube and YouTube Music" (zip,
                                folder or one playlist CSV). Each playlist becomes
                                a collection, so --collection works on it later.
  collect.py youtube --url URL [--browser chrome]
                                Read one playlist directly with yt-dlp. Use --url WL
                                with --browser for your Watch Later, which is private.
"""
from __future__ import annotations

import argparse
import calendar
import csv
import io
import json
import random
import re
import sys
import time
import zipfile
import zlib
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (SESSION_DIR, SHORTCODE_RE, TIKTOK_RE, add_reel, ensure_home,  # noqa: E402
                    load_db, log, save_db, shortcode_from_url, tiktok_key, tiktok_url,
                    youtube_key, youtube_url)
from ig import classify_error  # noqa: E402


def _zip_texts(path: Path, wanted, encoding: str = "utf-8"):
    """Yield (name, text) for the wanted files of a zip. Exports are big and often half-downloaded."""
    try:
        with zipfile.ZipFile(path) as z:
            for name in z.namelist():
                if wanted(name):
                    yield name, z.read(name).decode(encoding, "replace")
    except (zipfile.BadZipFile, zlib.error) as e:
        sys.exit(f"{path} is not a complete zip ({e}). It was probably not fully downloaded: "
                 "download it again and retry. Nothing was changed.")


# --------------------------------------------------------------------- export
def _iter_export_files(path: Path):
    """Yield (name, text) for every .json/.html inside a zip, folder or file."""
    if path.is_file() and path.suffix.lower() == ".zip":
        yield from _zip_texts(path, lambda n: n.lower().endswith((".json", ".html")) and "saved" in n.lower())
    elif path.is_dir():
        for p in sorted(path.rglob("*")):
            # match on the path *inside* the export: the folder it sits in may
            # itself contain "saved" (e.g. ~/saved-reels-digest/instagram-xxxx)
            rel = p.relative_to(path).as_posix().lower()
            if p.suffix.lower() in (".json", ".html") and "saved" in rel:
                yield str(p), p.read_text("utf-8", "replace")
    elif path.is_file():
        yield str(path), path.read_text("utf-8", "replace")
    else:
        sys.exit(f"Not found: {path}")


def _collection_header(fields) -> str | None:
    """The collection's name if this entry is a header. Told by shape: the keys are translated."""
    if not isinstance(fields, dict):
        return None
    entries = [v for v in fields.values() if isinstance(v, dict)]
    if any(e.get("href") for e in entries):
        return None  # a saved post, not a header
    return next((e["value"] for e in entries if isinstance(e.get("value"), str) and e["value"]), None)


def _walk_json(node, collection, out, author=None):
    """Find every saved link in Instagram's (frequently changing) JSON layout.

    Entries look like {"title": <author>, "string_map_data": {"Saved on":
    {"href": url, "timestamp": ts}}}. In saved_collections.json a header entry
    with {"Name": {"value": "My collection"}} precedes the collection's items.
    """
    if isinstance(node, list):
        for item in node:
            if isinstance(item, dict):
                collection = _collection_header(item.get("string_map_data")) or collection
            _walk_json(item, collection, out, author)
        return
    if not isinstance(node, dict):
        return
    if isinstance(node.get("title"), str) and node["title"] not in ("Collection", "Colección"):
        author = node["title"]
    for v in node.values():
        if isinstance(v, dict) and isinstance(v.get("href"), str):
            sc = shortcode_from_url(v["href"])
            if sc:
                out.append({"shortcode": sc, "author": author or None,
                            "saved_at": v.get("timestamp"), "collection": collection})
        elif isinstance(v, (dict, list)):
            _walk_json(v, collection, out, author)


def cmd_export(args) -> None:
    db = load_db()
    found = []
    for name, text in _iter_export_files(Path(args.path).expanduser()):
        before = len(found)
        if name.lower().endswith(".json"):
            try:
                _walk_json(json.loads(text), None, found)
            except json.JSONDecodeError:
                pass
        if len(found) == before:  # HTML export, or JSON we could not walk
            found += [{"shortcode": m} for m in dict.fromkeys(SHORTCODE_RE.findall(text))]
    new = 0
    for f in found:
        sc = f.pop("shortcode")
        new += add_reel(db, sc, source="export", **f)
    save_db(db)
    if not found:
        print("No saved posts found in that export. In Instagram request \"Saved\" under "
              "\"Download your information\", format JSON, and pass the zip or its folder.")
    print(f"Read {len(found)} saved links from the export, {new} new. Total: {len(db['reels'])}.")


# ----------------------------------------------------------------------- live
def _instaloader_session(args):
    import instaloader

    L = instaloader.Instaloader(quiet=True, download_pictures=False, download_videos=False,
                                save_metadata=False, max_connection_attempts=2)
    SESSION_DIR.mkdir(parents=True, exist_ok=True)
    if args.browser:
        from instaloader.__main__ import import_session
        import_session(args.browser, L, None)
        user = L.context.username
        L.save_session_to_file(str(SESSION_DIR / f"session-{user}"))
    else:
        user = args.username
        sf = SESSION_DIR / f"session-{user}"
        try:
            L.load_session_from_file(user, str(sf) if sf.exists() else None)
        except FileNotFoundError:
            sys.exit(f"No saved session for {user}. Run once with --browser chrome "
                     "(or firefox/edge/brave/safari) while logged into Instagram there.")
    return L, user


def _live_stopped(error: Exception, new: int) -> str:
    """Why the read ended early. Everything read so far has been saved by then."""
    kept = f"Saved the {new} new posts read so far."
    detail = str(error)[:160]
    kind = classify_error(detail)
    if kind == "blocked":
        return (f"STOPPED: Instagram is asking for login or rate-limiting ({detail}). {kept} "
                "Wait a few hours before running it again, or use the official export.")
    if kind == "network":
        return f"STOPPED: no connection ({detail}). {kept} Run it again when you are back online."
    return f"STOPPED: could not keep reading your saved posts ({detail}). {kept}"


def cmd_live(args) -> None:
    import instaloader

    L, user = _instaloader_session(args)
    db = load_db()
    new = seen = 0
    try:
        profile = instaloader.Profile.from_username(L.context, user)
        for post in profile.get_saved_posts():
            seen += 1
            caption = post.caption or ""
            added = add_reel(db, post.shortcode, source="live", author=post.owner_username,
                             caption=caption, is_video=post.is_video,
                             duration=post.video_duration if post.is_video else None)
            new += added
            if added and new % 25 == 0:
                save_db(db)
                log(f"... {seen} read, {new} new")
            if args.limit and seen >= args.limit:
                break
            if args.stop_at_known and not added:
                break  # saved feed is newest-first: everything after this is known
            time.sleep(random.uniform(0.3, 0.9))
    except Exception as e:  # noqa: BLE001
        save_db(db)
        sys.exit(_live_stopped(e, new))
    save_db(db)
    print(f"Read {seen} saved posts from @{user}, {new} new. Total: {len(db['reels'])}.")


# --------------------------------------------------------------------- tiktok
def _tiktok_files(path: Path):
    """Yield (name, text) for the TikTok export files that can hold favorites."""
    def wanted(name: str) -> bool:
        low = name.lower()
        return (low.endswith(".json") and "user_data" in low) or (
            low.endswith(".txt") and "favorite video" in low)

    if path.is_file() and path.suffix.lower() == ".zip":
        yield from _zip_texts(path, wanted)
    elif path.is_dir():
        for p in sorted(path.rglob("*")):
            if p.is_file() and wanted(p.relative_to(path).as_posix()):
                yield str(p), p.read_text("utf-8", "replace")
    elif path.is_file():
        yield str(path), path.read_text("utf-8", "replace")
    else:
        sys.exit(f"Not found: {path}")


def _tiktok_ts(date: str | None) -> int | None:
    """TikTok writes "2026-10-30 18:04:11" (UTC)."""
    try:
        return calendar.timegm(time.strptime((date or "").strip(), "%Y-%m-%d %H:%M:%S"))
    except ValueError:
        return None


def _find_favorites(node):
    """The FavoriteVideoList, wherever this version of the export puts it."""
    if isinstance(node, dict):
        for k, v in node.items():
            if k == "FavoriteVideoList" and isinstance(v, list):
                return v
            found = _find_favorites(v)
            if found is not None:
                return found
    elif isinstance(node, list):
        for v in node:
            found = _find_favorites(v)
            if found is not None:
                return found
    return None


def parse_tiktok(name: str, text: str) -> list:
    """[{"id", "saved_at"}] for every favorite video in one export file."""
    out = []
    if name.lower().endswith(".json"):
        try:
            favs = _find_favorites(json.loads(text)) or []
        except json.JSONDecodeError:
            favs = []
        for f in favs:
            if isinstance(f, dict):
                m = TIKTOK_RE.search(f.get("Link") or f.get("link") or "")
                if m:
                    out.append({"id": m.group(1), "saved_at": _tiktok_ts(f.get("Date") or f.get("date"))})
        return out
    # TXT export: blocks of "Date: ...\nLink: ..."
    date = None
    for line in text.splitlines():
        key, _, value = line.partition(":")
        if key.strip().lower() == "date":
            date = value
        m = TIKTOK_RE.search(line)
        if m:
            out.append({"id": m.group(1), "saved_at": _tiktok_ts(date)})
            date = None
    return out


def cmd_tiktok(args) -> None:
    db = load_db()
    found = []
    for name, text in _tiktok_files(Path(args.path).expanduser()):
        found += parse_tiktok(name, text)
    found = list({f["id"]: f for f in reversed(found)}.values())[::-1]  # dedupe, keep first
    new = sum(add_reel(db, tiktok_key(f["id"]), url=tiktok_url(f["id"]), platform="tiktok",
                       source="tiktok", is_video=True, saved_at=f["saved_at"]) for f in found)
    save_db(db)
    if not found:
        print("No favorite videos found. In TikTok pick Settings → Account → Download your data, "
              "format JSON, and pass the zip or user_data JSON.")
    print(f"Read {len(found)} TikTok favorites from the export, {new} new. Total: {len(db['reels'])}.")


# -------------------------------------------------------------------- youtube
YOUTUBE_ID_RE = re.compile(r"[A-Za-z0-9_-]{11}")


def _is_playlist_csv(name: str) -> bool:
    """Takeout folders and files are named in the account's language."""
    low = name.lower().replace("\\", "/")
    return low.endswith(".csv") and not low.endswith("/playlists.csv") and low != "playlists.csv" and any(
        k in low for k in ("playlist", "lista", "watch later", "ver m"))


def _youtube_files(path: Path):
    """Yield (name, text) for every playlist CSV in a Takeout zip, folder or single file."""
    if path.is_file() and path.suffix.lower() == ".zip":
        yield from _zip_texts(path, _is_playlist_csv, "utf-8-sig")
    elif path.is_dir():
        for p in sorted(path.rglob("*")):
            # the folder's own name counts: the user may point straight at "playlists/"
            if p.is_file() and _is_playlist_csv(f"{path.name}/{p.relative_to(path).as_posix()}"):
                yield str(p), p.read_text("utf-8-sig", "replace")
    elif path.is_file():
        yield str(path), path.read_text("utf-8-sig", "replace")
    else:
        sys.exit(f"Not found: {path}")


def _iso_ts(value: str) -> int | None:
    """Takeout timestamps: 2026-10-20T09:15:00+00:00, sometimes ending in Z or " UTC"."""
    value = re.sub(r"(Z| UTC)$", "+00:00", value.strip())
    try:
        d = datetime.fromisoformat(value)
    except ValueError:
        return None
    return int((d if d.tzinfo else d.replace(tzinfo=timezone.utc)).timestamp())


def playlist_name(file_name: str) -> str:
    """"Watch later-videos.csv" -> "Watch later"; "Ideas de IA-vídeos.csv" -> "Ideas de IA"."""
    stem = Path(file_name.replace("\\", "/")).stem
    return re.sub(r"[-\s]*v[ií]deos$", "", stem, flags=re.I).strip() or stem


def parse_youtube_csv(text: str) -> list:
    """[{"id", "saved_at"}]. Rows are matched by shape: the headers change with the language."""
    out = []
    for row in csv.reader(io.StringIO(text)):
        cells = [c.strip() for c in row]
        if len(cells) >= 2 and YOUTUBE_ID_RE.fullmatch(cells[0]):
            ts = _iso_ts(cells[1])
            if ts is not None:
                out.append({"id": cells[0], "saved_at": ts})
    return out


WATCH_LATER_URL = "https://www.youtube.com/playlist?list=WL"
GONE_TITLES = ("[private video]", "[deleted video]")


def read_youtube_playlist(url: str, browser: str | None = None) -> tuple:
    """(title, entries) of a playlist. Lists it only: no video is downloaded."""
    import yt_dlp

    from ig import Fetcher

    url = WATCH_LATER_URL if url.strip().upper() == "WL" else url
    opts = Fetcher(browser)._ydl_opts(extract_flat="in_playlist", skip_download=True)
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as e:  # noqa: BLE001
        sys.exit(f"Could not read that playlist ({str(e)[:200]}). Private lists such as Watch "
                 "Later need --browser with a browser where you are logged into YouTube.")
    entries = [e for e in info.get("entries") or []
               if e and YOUTUBE_ID_RE.fullmatch(e.get("id") or "")
               and (e.get("title") or "").lower() not in GONE_TITLES]
    return info.get("title") or "YouTube", entries


def cmd_youtube_url(args) -> None:
    title, entries = read_youtube_playlist(args.url, args.browser)
    db = load_db()
    new = sum(add_reel(db, youtube_key(e["id"]), url=youtube_url(e["id"]), platform="youtube",
                       source="youtube", is_video=True, collection=title,
                       author=e.get("channel") or e.get("uploader"),
                       duration=e.get("duration")) for e in entries)
    save_db(db)
    print(f"Read {len(entries)} videos from {title!r}, {new} new. Total: {len(db['reels'])}.")


def cmd_youtube(args) -> None:
    if bool(args.path) == bool(args.url):
        sys.exit("Pass either a Takeout PATH or --url URL.")
    if args.url:
        cmd_youtube_url(args)
        return
    db = load_db()
    found = {}
    for name, text in _youtube_files(Path(args.path).expanduser()):
        plist = playlist_name(name)
        if args.playlist and plist.casefold() != args.playlist.strip().casefold():
            continue
        for v in parse_youtube_csv(text):
            found.setdefault(v["id"], {**v, "collection": plist})
    new = sum(add_reel(db, youtube_key(v["id"]), url=youtube_url(v["id"]), platform="youtube",
                       source="youtube", is_video=True, saved_at=v["saved_at"],
                       collection=v["collection"]) for v in found.values())
    save_db(db)
    if not found:
        print("No playlist videos found. In Google Takeout pick \"YouTube and YouTube Music\", "
              "keep playlists selected, and pass the zip or a playlist CSV.")
    print(f"Read {len(found)} YouTube videos from the export, {new} new. Total: {len(db['reels'])}.")


# ----------------------------------------------------------------------- urls
def cmd_urls(args) -> None:
    text = sys.stdin.read() if args.file == "-" else Path(args.file).read_text("utf-8")
    db = load_db()
    codes = list(dict.fromkeys(SHORTCODE_RE.findall(text)))
    new = sum(add_reel(db, sc, source="urls") for sc in codes)
    save_db(db)
    print(f"Parsed {len(codes)} links, {new} new. Total: {len(db['reels'])}.")


def main() -> None:
    ensure_home()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("export"); e.add_argument("path"); e.set_defaults(fn=cmd_export)
    live = sub.add_parser("live")
    g = live.add_mutually_exclusive_group(required=True)
    g.add_argument("--browser", help="chrome, firefox, edge, brave, safari, ...")
    g.add_argument("--username", help="reuse the session saved by a previous --browser run")
    live.add_argument("--limit", type=int, default=0, help="stop after N saved posts (0 = all)")
    live.add_argument("--stop-at-known", action="store_true",
                   help="incremental: stop at the first post already in the database")
    live.set_defaults(fn=cmd_live)
    u = sub.add_parser("urls"); u.add_argument("file"); u.set_defaults(fn=cmd_urls)
    t = sub.add_parser("tiktok"); t.add_argument("path"); t.set_defaults(fn=cmd_tiktok)
    y = sub.add_parser("youtube"); y.add_argument("path", nargs="?")
    y.add_argument("--url", help="read this playlist with yt-dlp instead (WL = your Watch Later)")
    y.add_argument("--browser", help="with --url: reuse this browser's YouTube login")
    y.add_argument("--playlist", help="only this playlist, by name (case-insensitive)")
    y.set_defaults(fn=cmd_youtube)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
