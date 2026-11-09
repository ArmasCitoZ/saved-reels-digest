"""Fill in caption, author and duration for saved posts that do not have them yet.

  fetch_meta.py [--browser chrome | --username YOU] [--limit N] [--delay 3]

Captions are enough for Claude to do a first topic triage, so only the posts
that matter get downloaded and transcribed later. Progress is saved as it goes,
and on Ctrl+C; just run it again to continue.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import load_db, log, save_db  # noqa: E402
from ig import Blocked, Fetcher, NetworkError, Unavailable  # noqa: E402

MAX_CONSECUTIVE_FAILS = 5


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--browser", help="reuse cookies from this browser (chrome, firefox, edge, ...)")
    ap.add_argument("--username", help="reuse the instaloader session saved by collect.py live")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--delay", type=float, default=3.0, help="average seconds between requests")
    ap.add_argument("--retry-failed", action="store_true")
    args = ap.parse_args()

    db = load_db()
    todo = [r for r in db["reels"].values()
            if not r.get("caption") and r.get("meta") != "ok"
            and (args.retry_failed or r.get("meta") not in ("failed", "unavailable"))]
    if args.limit:
        todo = todo[: args.limit]
    if not todo:
        print("Nothing to fetch: every saved post already has its caption.")
        return

    f = Fetcher(args.browser, args.username, args.delay)
    ok = fails = gone = streak = 0
    log(f"Fetching metadata for {len(todo)} posts (~{len(todo) * args.delay / 60:.0f} min) ...")
    try:
        for n, r in enumerate(todo, 1):
            try:
                r.update({k: v for k, v in f.metadata(r["shortcode"], r.get("url")).items() if v is not None})
                r["meta"] = "ok"
                ok += 1
                streak = 0
            except Blocked as e:
                save_db(db)
                sys.exit(f"STOPPED: the site is asking for login or rate-limiting ({e}).\n"
                         f"Saved progress ({ok} done). Wait a while, or pass --browser with a "
                         "browser where you are logged in, then run again.")
            except NetworkError as e:
                save_db(db)
                sys.exit(f"STOPPED: no connection ({str(e)[:120]}). Progress saved ({ok} done); "
                         "run it again when you are back online.")
            except Unavailable as e:
                r["meta"], r["meta_error"] = "unavailable", str(e)[:300]
                gone += 1
                streak += 1  # still counts: a throttled session can look like "not available"
                if streak >= MAX_CONSECUTIVE_FAILS:
                    save_db(db)
                    sys.exit(f"STOPPED: {streak} posts in a row look deleted or private, which is more "
                             f"often Instagram throttling than real deletions. Progress saved ({ok} done). "
                             "Wait a while and run it again; when it finishes, --retry-failed checks "
                             "those posts once more.")
            except Exception as e:  # noqa: BLE001
                r["meta"], r["meta_error"] = "failed", str(e)[:300]
                fails += 1
                streak += 1
                if streak >= MAX_CONSECUTIVE_FAILS:
                    save_db(db)
                    sys.exit(f"STOPPED after {streak} failures in a row (last: {e}). "
                             f"Progress saved ({ok} done). Try --browser, then run again.")
            if n % 10 == 0:
                save_db(db)
                log(f"... {n}/{len(todo)}")
    except KeyboardInterrupt:
        # Without this, up to 9 posts read since the last save were lost on Ctrl+C.
        save_db(db)
        sys.exit(f"Interrupted. Progress saved ({ok} done); run it again to continue.")
    save_db(db)
    print(f"Metadata: {ok} ok, {gone} deleted or private, {fails} failed."
          + (" See them with: db.py unavailable" if gone else ""))


if __name__ == "__main__":
    main()
