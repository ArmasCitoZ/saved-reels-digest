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
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (SESSION_DIR, SHORTCODE_RE, add_reel, ensure_home, load_db,  # noqa: E402
                    log, save_db, shortcode_from_url)


# --------------------------------------------------------------------- export
def _iter_export_files(path: Path):
    """Yield (name, text) for every .json/.html inside a zip, folder or file."""
    if path.is_file() and path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as z:
            for name in z.namelist():
                if name.lower().endswith((".json", ".html")) and "saved" in name.lower():
                    yield name, z.read(name).decode("utf-8", "replace")
    elif path.is_dir():
        for p in sorted(path.rglob("*")):
            if p.suffix.lower() in (".json", ".html") and "saved" in str(p).lower():
                yield str(p), p.read_text("utf-8", "replace")
    elif path.is_file():
        yield str(path), path.read_text("utf-8", "replace")
    else:
        sys.exit(f"Not found: {path}")


def _walk_json(node, collection, out, author=None):
    """Find every saved link in Instagram's (frequently changing) JSON layout.

    Entries look like {"title": <author>, "string_map_data": {"Saved on":
    {"href": url, "timestamp": ts}}}. In saved_collections.json a header entry
    with {"Name": {"value": "My collection"}} precedes the collection's items.
    """
    if isinstance(node, list):
        for item in node:
            if isinstance(item, dict):
                smd = item.get("string_map_data") or {}
                name = smd.get("Name") or smd.get("Nombre") or {}
                if isinstance(name, dict) and name.get("value") and not name.get("href"):
                    collection = name["value"]
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


def cmd_live(args) -> None:
    import instaloader

    L, user = _instaloader_session(args)
    db = load_db()
    profile = instaloader.Profile.from_username(L.context, user)
    new = seen = 0
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
    save_db(db)
    print(f"Read {seen} saved posts from @{user}, {new} new. Total: {len(db['reels'])}.")


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
    l = sub.add_parser("live")
    g = l.add_mutually_exclusive_group(required=True)
    g.add_argument("--browser", help="chrome, firefox, edge, brave, safari, ...")
    g.add_argument("--username", help="reuse the session saved by a previous --browser run")
    l.add_argument("--limit", type=int, default=0, help="stop after N saved posts (0 = all)")
    l.add_argument("--stop-at-known", action="store_true",
                   help="incremental: stop at the first post already in the database")
    l.set_defaults(fn=cmd_live)
    u = sub.add_parser("urls"); u.add_argument("file"); u.set_defaults(fn=cmd_urls)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
