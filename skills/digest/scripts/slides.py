"""Read the text inside photo and carousel posts: scripts fetch the images, Claude looks at them.

  slides.py pending [--collection NAME]        relevant image posts still to read
  slides.py fetch [--limit 10] [--max-images 10] [--delay 3]
                  [--browser chrome | --username YOU] [--collection NAME]
                                               download images and print their paths
  slides.py save CODE [TEXT]                   store what the images say (no TEXT: read stdin)
                                               and delete that post's images
  slides.py save CODE --empty                  the images say nothing useful: delete them
  slides.py clean                              delete every downloaded image

In save, CODE can also be the post's pasted Instagram link.

Works on posts marked relevant or "maybe" that fetch_meta.py found have no video.
Images stay in WORK/.slides only until their text is saved. Instagram only, and
paced like everything else: it stops at the first sign of rate limiting.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import HOME, in_collection, load_db, log, resolve_code, save_db  # noqa: E402
from ig import Blocked, Fetcher, NetworkError, Unavailable  # noqa: E402

SLIDES_DIR = HOME / ".slides"
MAX_CONSECUTIVE_FAILS = 5


def needs_reading(r: dict, collection: str | None = None) -> bool:
    return (r.get("is_video") is False and "slides_text" not in r
            and r.get("slides") != "failed" and r.get("meta") != "unavailable"
            and r.get("relevant") in (True, "maybe")
            and Fetcher.is_instagram(r.get("url")) and in_collection(r, collection))


def existing_images(folder: Path) -> list:
    return sorted(folder.glob("*.jpg"))


def fetch_all(db: dict, todo: list, fetcher, root: Path, max_images: int) -> list:
    """Download images for each post. Returns [(reel, paths)]. Images already there are reused."""
    out = []
    streak = 0
    for r in todo:
        sc = r["shortcode"]
        folder = root / sc
        paths = existing_images(folder)
        if paths:
            out.append((r, paths))
            continue
        try:
            paths = fetcher.download_images(sc, folder, max_images)
            streak = 0
            if paths:
                out.append((r, paths))
            else:
                r["slides_text"] = ""  # nothing to read: do not ask again
        except Blocked as e:
            save_db(db)
            sys.exit(f"STOPPED: Instagram is asking for login or rate-limiting ({e}). "
                     "Images already downloaded are kept; retry later or pass --browser.")
        except NetworkError as e:
            save_db(db)
            sys.exit(f"STOPPED: no connection ({str(e)[:120]}). Run it again when you are back online.")
        except Unavailable as e:
            r["meta"], r["meta_error"] = "unavailable", str(e)[:300]
            streak += 1
        except Exception as e:  # noqa: BLE001
            r.update(slides="failed", slides_error=str(e)[:300])
            log(f"{sc}: {str(e)[:120]}")
            streak += 1
        if streak >= MAX_CONSECUTIVE_FAILS:
            save_db(db)
            sys.exit(f"STOPPED after {streak} failures in a row. Try --browser, then run again.")
    save_db(db)
    return out


def cmd_pending(a) -> None:
    todo = [r for r in load_db()["reels"].values() if needs_reading(r, a.collection)]
    print(f"{len(todo)} image posts waiting to be read.")
    for r in todo:
        print(f"  {r['shortcode']} @{r.get('author') or '?'}")


def cmd_fetch(a) -> None:
    db = load_db()
    todo = [r for r in db["reels"].values() if needs_reading(r, a.collection)]
    remaining = len(todo)
    todo = todo[: a.limit]
    if not todo:
        print("No image posts to read. (Triage and run fetch_meta.py first.)")
        return
    fetched = fetch_all(db, todo, Fetcher(a.browser, a.username, a.delay), SLIDES_DIR, a.max_images)
    for r, paths in fetched:
        print(f"### {r['shortcode']}  @{r.get('author') or '?'}  {len(paths)} images")
        for p in paths:
            print(f"IMAGE: {p}")
    print(f"-- {len(fetched)} posts ready; {remaining - len(todo)} more after these. "
          "Read the images, then: slides.py save CODE")


def cmd_save(a) -> None:
    db = load_db()
    code = resolve_code(db["reels"], a.code)
    if code is None:
        sys.exit(f"Unknown post: {a.code}. Nothing was saved and no images were deleted.")
    r = db["reels"][code]
    if a.empty:
        if a.text and a.text.strip():
            sys.exit("Pass either a text or --empty, not both.")
        text = ""
    else:
        text = (sys.stdin.read() if a.text is None else a.text).strip()
        if not text:
            # Usually a broken pipe or a heredoc that went wrong; deleting the images would lose them.
            sys.exit(f"No text received for {code}, so nothing was saved and its images are kept. "
                     "If they say nothing useful, run: slides.py save " + code + " --empty")
    r["slides_text"] = text
    r.pop("slides", None)
    r.pop("slides_error", None)
    save_db(db)
    # the folder is named after the code, never the pasted link
    shutil.rmtree(SLIDES_DIR / code, ignore_errors=True)
    print(f"Saved {len(r['slides_text'])} characters for {code} and deleted its images.")


def cmd_clean(_) -> None:
    shutil.rmtree(SLIDES_DIR, ignore_errors=True)
    print("Deleted the downloaded images.")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("pending"); p.add_argument("--collection"); p.set_defaults(fn=cmd_pending)
    p = sub.add_parser("fetch"); p.add_argument("--limit", type=int, default=10)
    p.add_argument("--max-images", type=int, default=10, help="per post (carousels can have 20)")
    p.add_argument("--delay", type=float, default=3.0, help="average seconds between posts")
    p.add_argument("--browser"); p.add_argument("--username")
    p.add_argument("--collection"); p.set_defaults(fn=cmd_fetch)
    p = sub.add_parser("save"); p.add_argument("code"); p.add_argument("text", nargs="?")
    p.add_argument("--empty", action="store_true", help="the images say nothing useful")
    p.set_defaults(fn=cmd_save)
    sub.add_parser("clean").set_defaults(fn=cmd_clean)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
