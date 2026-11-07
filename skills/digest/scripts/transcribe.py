"""Transcribe saved reels locally with Whisper (faster-whisper). Free, offline, private.

  transcribe.py [--model auto] [--language es] [--all] [--limit N] [--collection NAME]
                [--browser chrome | --username YOU] [--shortcodes A,B,C]

By default only reels Claude marked relevant or "maybe" are transcribed.
The audio is deleted right after transcription; only the text is kept.
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
                    total_ram_bytes)
from ig import Blocked, Fetcher  # noqa: E402

MAX_CONSECUTIVE_FAILS = 5


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
    args = ap.parse_args()

    if args.file:
        text, lang = transcribe_file(load_model(args.model), Path(args.file), args.language)
        print(f"[{lang}] {text}")
        return

    db = load_db()
    reels = db["reels"]
    if args.shortcodes:
        todo = [reels[s] for s in args.shortcodes.split(",") if s in reels]
    else:
        todo = [r for r in reels.values()
                if "transcript" not in r and r.get("is_video") is not False
                and r.get("transcribe") != "failed" and r.get("meta") != "unavailable"
                and (args.all or r.get("relevant") in (True, "maybe"))
                and in_collection(r, args.collection)]
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
                media = fetcher.download_audio(sc, tmp, r.get("url"))
                text, lang = transcribe_file(model, media, args.language)
                r.update(transcript=text, lang=lang, transcribe="ok")
                r.pop("transcribe_error", None)
                media.unlink(missing_ok=True)
                done += 1
                streak = 0
            except Blocked as e:
                save_db(db)
                sys.exit(f"STOPPED: Instagram is asking for login or rate-limiting ({e}). "
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
