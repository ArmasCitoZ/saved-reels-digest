"""Transcribe saved reels locally with Whisper (faster-whisper). Free, offline, private.

  transcribe.py [--model auto] [--language es] [--all] [--limit N] [--collection NAME]
                [--max-minutes 30]
                [--browser chrome | --username YOU] [--shortcodes A,B,C or links]

By default only reels Claude marked relevant or "maybe" are transcribed.
The audio is deleted right after transcription; only the text is kept.
If the connection drops, the run waits and retries the same reel a few times,
then stops; reels already transcribed are saved, and running it again picks up
exactly where it left off (network errors never mark a reel as failed).
The Whisper model is downloaded once (~75 MB tiny ... ~1.5 GB large-v3)
into the workspace and reused. With --model auto (default) it is chosen from
the computer's RAM: tiny under 4 GB, base under 8 GB, otherwise small, and
medium on an NVIDIA GPU.
"""
from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (HOME, in_collection, load_db, log, pick_whisper_model, save_db,  # noqa: E402
                    shortcode_from_url, tiktok_id_from_url, tiktok_key, total_ram_bytes)
from ig import Blocked, Fetcher, NetworkError, classify_error  # noqa: E402

MAX_CONSECUTIVE_FAILS = 5
# seconds to wait before each retry when our connection drops (then give up for this run)
NETWORK_WAITS = (15, 60, 180)


def has_cuda() -> bool:
    try:
        import ctranslate2
        return ctranslate2.get_cuda_device_count() > 0
    except Exception:  # noqa: BLE001
        return False


def load_model(name: str):
    from faster_whisper import WhisperModel

    cuda = has_cuda()
    if name == "auto":
        name = pick_whisper_model(total_ram_bytes(), cuda)
    device, ctype = ("cuda", "float16") if cuda else ("cpu", "int8")
    log(f"Loading Whisper '{name}' on {device} (first time downloads the model) ...")
    return WhisperModel(name, device=device, compute_type=ctype,
                        download_root=str(HOME / ".models"))


def transcribe_file(model, path: Path, language: str | None) -> tuple[str, str]:
    segments, info = model.transcribe(str(path), language=language, vad_filter=True,
                                      beam_size=1, condition_on_previous_text=False)
    text = " ".join(s.text.strip() for s in segments).strip()
    return text, info.language


def needs_transcript(r: dict, everything: bool = False, collection: str | None = None) -> bool:
    """Still to do. Old runs marked network drops as "failed": those are retried too."""
    failed = r.get("transcribe") == "failed"
    if failed and classify_error(r.get("transcribe_error") or "") != "network":
        return False
    return ("transcript" not in r and r.get("is_video") is not False
            and r.get("meta") != "unavailable"
            and (everything or r.get("relevant") in (True, "maybe"))
            and in_collection(r, collection))


def too_long(r: dict, max_minutes: float) -> bool:
    """Long YouTube videos can take longer to transcribe than a whole batch of reels."""
    return bool(max_minutes and (r.get("duration") or 0) > max_minutes * 60)


def fetch_with_retry(fetcher, r: dict, folder: Path, waits=NETWORK_WAITS, sleep=time.sleep) -> Path:
    """Download one reel's audio, waiting out short network drops. Raises NetworkError if it lasts."""
    for attempt in range(len(waits) + 1):
        try:
            return fetcher.download_audio(r["shortcode"], folder, r.get("url"))
        except NetworkError as e:
            if attempt == len(waits):
                raise
            log(f"  network problem ({str(e)[:80]}); retrying in {waits[attempt]} s ...")
            sleep(waits[attempt])
    raise AssertionError("unreachable")


def pick_shortcodes(reels: dict, spec: str) -> tuple[list[dict], list[str]]:
    """Reels named in --shortcodes, in order and once each, plus the names not in the database.

    Spaces around commas are ignored, and pasted Instagram or TikTok links are accepted.
    """
    todo, unknown, seen = [], [], set()
    for raw in spec.split(","):
        name = raw.strip()
        if not name:
            continue
        key = name
        if key not in reels:
            tiktok_id = tiktok_id_from_url(name)
            key = shortcode_from_url(name) or (tiktok_key(tiktok_id) if tiktok_id else name)
        if key not in reels:
            unknown.append(name)
        elif key not in seen:
            seen.add(key)
            todo.append(reels[key])
    return todo, unknown


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", default="auto",
                    help="auto (default, by RAM), tiny, base, small, medium, large-v3")
    ap.add_argument("--language", default=None, help="force a language code (es, en...); default auto")
    ap.add_argument("--all", action="store_true", help="ignore triage, transcribe every video")
    ap.add_argument("--shortcodes", help="comma-separated list to (re)transcribe")
    ap.add_argument("--collection", help="only reels from this Instagram collection")
    ap.add_argument("--file", help="transcribe a local media file and print it (testing)")
    ap.add_argument("--browser"); ap.add_argument("--username")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--delay", type=float, default=3.0)
    ap.add_argument("--max-minutes", type=float, default=30,
                    help="skip videos longer than this (0 = no limit; --shortcodes ignores it)")
    args = ap.parse_args()

    if args.file:
        text, lang = transcribe_file(load_model(args.model), Path(args.file), args.language)
        print(f"[{lang}] {text}")
        return

    db = load_db()
    reels = db["reels"]
    if args.shortcodes:
        todo, unknown = pick_shortcodes(reels, args.shortcodes)
        if unknown:
            log(f"Not in the database, skipped: {', '.join(unknown)}. "
                "Check for typos, or collect those posts first.")
        if not todo:
            sys.exit("None of the --shortcodes are in the database, so there is nothing to transcribe.")
    else:
        todo = [r for r in reels.values() if needs_transcript(r, args.all, args.collection)]
        long_ones = [r for r in todo if too_long(r, args.max_minutes)]
        if long_ones:
            todo = [r for r in todo if not too_long(r, args.max_minutes)]
            log(f"Skipping {len(long_ones)} videos longer than {args.max_minutes:g} min "
                "(--max-minutes 0 to include them; their captions are still used).")
    if args.limit:
        todo = todo[: args.limit]
    if not todo:
        print("Nothing to transcribe. (Triage first, or pass --all.)")
        return

    model = load_model(args.model)
    fetcher = Fetcher(args.browser, args.username, args.delay)
    tmp = Path(tempfile.mkdtemp(prefix="srd-"))
    done = streak = 0
    t0 = time.time()
    try:
        for n, r in enumerate(todo, 1):
            sc = r["shortcode"]
            try:
                media = fetch_with_retry(fetcher, r, tmp)
                text, lang = transcribe_file(model, media, args.language)
                r.update(transcript=text, lang=lang, transcribe="ok")
                r.pop("transcribe_error", None)
                media.unlink(missing_ok=True)
                done += 1
                streak = 0
            except NetworkError as e:
                save_db(db)
                sys.exit(f"STOPPED: no connection ({str(e)[:120]}). Saved {done} transcripts; "
                         "run the same command again when you are back online and it will "
                         "continue with the remaining reels.")
            except Blocked as e:
                save_db(db)
                sys.exit(f"STOPPED: the site is asking for login or rate-limiting ({e}). "
                         f"Saved {done} transcripts. Retry later or pass --browser.")
            except Exception as e:  # noqa: BLE001
                r.update(transcribe="failed", transcribe_error=str(e)[:300])
                streak += 1
                if streak >= MAX_CONSECUTIVE_FAILS:
                    save_db(db)
                    sys.exit(f"STOPPED after {streak} failures in a row (last: {e}). "
                             f"Saved {done} transcripts.")
            save_db(db)
            eta = (time.time() - t0) / n * (len(todo) - n) / 60
            status = "ok" if r.get("transcribe") == "ok" else "failed"
            log(f"[{n}/{len(todo)}] {sc} {status}  (~{eta:.0f} min left)")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"Transcribed {done}/{len(todo)} reels.")


if __name__ == "__main__":
    main()
