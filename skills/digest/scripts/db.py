"""Inspect and update the local reel database (used by Claude during triage and merging).

  db.py status                              counts at every stage
  db.py collections                         Instagram collections and how many reels each has
  db.py unavailable                         saved posts that were deleted or are private
  db.py next [--limit 40] [--field relevant] posts still waiting for triage, compact
  db.py set FIELD VALUE CODE [CODE ...]     e.g. set relevant true C1 C2 / set topic "Claude Code" C3
  db.py dump [--undigested] [--all]         relevant reels with caption + transcript, for merging
            [--max-total 60000] [--offset N]   output is capped; continue with --offset
  db.py similar [--threshold 0.3]           groups of reels that probably say the same thing,
            [--ngram-threshold 0.1]            also across languages (by similar spellings)
  db.py recent [--days 7]                   relevant reels saved lately and their digest entry
  db.py mark tried|discarded|todo SLUG ... [--note TEXT]
                                            remember what the user did with a digest idea
  db.py marks                               every idea marked tried or discarded

next, dump, similar and recent accept --collection NAME to work only on one Instagram
collection (as named in the official export, case-insensitive).
  db.py show CODE [CODE ...]                full record
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
import time
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import DB_PATH, in_collection, load_db, save_db  # noqa: E402


# ~15k tokens: a page of dump output Claude can read in one go without flooding its context
DUMP_BUDGET = 60_000
DUMP_CHARS = 600


def _short(s: str | None, n: int) -> str:
    s = re.sub(r"\s+", " ", s or "").strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def _parse_value(v: str):
    low = v.lower()
    return {"true": True, "false": False, "null": None, "none": None}.get(low, v)


def _has_content(r: dict) -> bool:
    """False for a deleted or private post nothing was read from: it can never become an idea."""
    return r.get("meta") != "unavailable" or bool(_full_text(r))


def cmd_status(_):
    rs = list(load_db()["reels"].values())
    c = Counter()
    for r in rs:
        c["total"] += 1
        c["with caption"] += bool(r.get("caption"))
        c["meta failed"] += r.get("meta") == "failed"
        c["deleted or private"] += r.get("meta") == "unavailable"
        c[f"triage: {r.get('relevant')}"] += 1
        c["transcribed"] += bool(r.get("transcript"))
        c["transcribe failed"] += r.get("transcribe") == "failed"
        c["images read"] += bool(r.get("slides_text"))
        c["merged into digest"] += bool(r.get("entry"))
    c["relevant & not yet in digest"] = sum(1 for r in rs if r.get("relevant") is True
                                            and not r.get("entry") and _has_content(r))
    print(f"Database: {DB_PATH}")
    for k in ["total", "with caption", "meta failed", "deleted or private", "triage: None", "triage: True",
              "triage: maybe", "triage: False", "transcribed", "transcribe failed", "images read",
              "merged into digest", "relevant & not yet in digest"]:
        label = {"triage: None": "not triaged yet", "triage: True": "relevant",
                 "triage: maybe": "maybe (decide after transcript)",
                 "triage: False": "not relevant"}.get(k, k)
        print(f"  {label:32} {c[k]}")


def cmd_collections(_):
    c = Counter(r.get("collection") or "" for r in load_db()["reels"].values())
    if not any(c):
        print("No collections recorded. They come from saved_collections.json in the official export.")
        return
    for name, n in sorted(c.items(), key=lambda kv: (-kv[1], kv[0])):
        print(f"  {name or '(no collection)':32} {n}")


def cmd_unavailable(_):
    rs = [r for r in load_db()["reels"].values() if r.get("meta") == "unavailable"]
    if not rs:
        print("No deleted or private posts found (so far).")
        return
    print(f"{len(rs)} saved posts are deleted or private (left out of the digest):")
    for r in rs:
        print(f"  {r['url']}  @{r.get('author') or '?'}  {r.get('collection') or ''}".rstrip())


def cmd_next(a):
    rs = [r for r in load_db()["reels"].values()
          if (r.get("relevant") is None or (a.maybe and r.get("relevant") == "maybe"))
          and r.get("meta") != "unavailable" and in_collection(r, a.collection)]
    if not rs:
        print("Nothing left to triage" + (f" in collection {a.collection!r}." if a.collection else "."))
        return
    print(f"{len(rs)} waiting. Showing {min(a.limit, len(rs))}:")
    for r in rs[: a.limit]:
        text = r.get("caption") or ""
        if a.maybe and r.get("transcript"):
            text = f"{text} || TRANSCRIPT: {r['transcript']}"
        if a.maybe and r.get("slides_text"):
            text = f"{text} || IMAGES: {r['slides_text']}"
        print(f"{r['shortcode']} | @{r.get('author') or '?'} | {r.get('collection') or ''} | "
              f"{_short(text, a.chars) or '(no caption)'}")


# Fields the digest steps are meant to write by hand; the rest belong to the collectors.
SETTABLE = ("relevant", "entry", "topic", "caption", "author", "collection")
TRIAGE_VALUES = (True, False, "maybe", None)


def cmd_set(a):
    val = _parse_value(a.value)
    if a.field not in SETTABLE:
        sys.exit(f"Unknown field {a.field!r}. Can be set: {', '.join(SETTABLE)}.")
    if a.field == "relevant" and val not in TRIAGE_VALUES:
        sys.exit(f"Invalid value {a.value!r} for relevant. Use: true, false, maybe or none.")
    db = load_db()
    missing, done = [], 0
    for sc in a.codes:
        for s in sc.split(","):
            s = s.strip()
            if not s:
                continue
            if s in db["reels"]:
                db["reels"][s][a.field] = val
                done += 1
            else:
                missing.append(s)
    save_db(db)
    print(f"Set {a.field}={val!r} on {done} reels."
          + (f" Unknown: {', '.join(missing)}" if missing else ""))


def saved_ts(r: dict) -> int | None:
    """When the reel was saved: the export's timestamp, else when we first collected it."""
    ts = r.get("saved_at") or r.get("added_at")
    try:
        return int(ts) if ts else None
    except (TypeError, ValueError):
        return None


def _day(ts: int | None) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d") if ts else "?"


def _dump_block(r, chars: int) -> str:
    lines = [f"### {r['shortcode']}  @{r.get('author') or '?'}  {r['url']}"
             + (f"  [entry: {r['entry']}]" if r.get("entry") else ""),
             f"SAVED: {_day(saved_ts(r))}"]
    if r.get("caption"):
        lines.append(f"CAPTION: {_short(r['caption'], chars)}")
    if r.get("transcript"):
        lines.append(f"TRANSCRIPT ({r.get('lang', '?')}): {_short(r['transcript'], chars * 3)}")
    if r.get("slides_text"):
        lines.append(f"IMAGES: {_short(r['slides_text'], chars * 3)}")
    return "\n".join(lines) + "\n\n"


def _dump_again(a, offset: int) -> str:
    """The command that shows the next page: the same filters, or the offsets would not line up."""
    parts = [f"dump --offset {offset}"]
    if a.undigested:
        parts.append("--undigested")
    if a.all:
        parts.append("--all")
    if a.collection:
        parts.append(f'--collection "{a.collection}"')
    if a.chars != DUMP_CHARS:
        parts.append(f"--chars {a.chars}")
    if a.max_total != DUMP_BUDGET:
        parts.append(f"--max-total {a.max_total}")
    return " ".join(parts)


def cmd_dump(a):
    rs = [r for r in load_db()["reels"].values()
          if (a.all or r.get("relevant") is True) and not (a.undigested and r.get("entry"))
          and in_collection(r, a.collection) and _has_content(r)]
    shown = used = 0
    for r in rs[a.offset:]:
        block = _dump_block(r, a.chars)
        # always print at least one reel, then stop before going over the budget
        if a.max_total and shown and used + len(block) > a.max_total:
            break
        sys.stdout.write(block)
        used += len(block)
        shown += 1
    end = a.offset + shown
    if end < len(rs):
        print(f"-- {len(rs) - end} more reels not shown (output limited to ~{a.max_total} chars). "
              f"Continue with: {_dump_again(a, end)}")
    print(f"(reels {a.offset + 1 if shown else a.offset}-{end} of {len(rs)})", file=sys.stderr)


# ---------------------------------------------------------------- similarity
STOP = set("""a al algo como con de del el ella en es esa ese esta este esto hay la las le lo los
mas me mi muy no o para pero por que se si sin su sus te tu un una y ya yo the a an and are as at be
but by can do for from has have how i if in is it its just me my not of on or so that the this to up
was we what when with you your youre im dont like get got one all out more about now here there
will then them they their which who really very want need make use using""".split())


def _tokens(text: str):
    words = re.findall(r"[^\W_][\w+#.-]+", text.lower())  # letters of any alphabet
    return [w.strip(".-") for w in words if w not in STOP and not w.isdigit()]


def _full_text(r: dict) -> str:
    return " ".join(r.get(k) or "" for k in ("caption", "transcript", "slides_text")).strip()


def _tfidf(docs: list) -> list:
    """Unit-length TF-IDF vectors for a list of Counters."""
    df = Counter(t for d in docs for t in d)
    n = len(docs)
    vecs = []
    for d in docs:
        v = {t: (1 + math.log(c)) * math.log((n + 1) / (df[t] + 0.5)) for t, c in d.items()}
        norm = math.sqrt(sum(x * x for x in v.values())) or 1.0
        vecs.append({t: x / norm for t, x in v.items()})
    return vecs


def _cosine(a: dict, b: dict) -> float:
    a, b = (a, b) if len(a) < len(b) else (b, a)
    return sum(x * b.get(t, 0.0) for t, x in a.items())


NGRAM = 4
EN_MARKERS = set("the and with this that you your for from have how what".split())
ES_MARKERS = set("el la los las con este esta que para por una como pero del".split())


def _char_ngrams(tokens: list) -> Counter:
    """Pieces of words, so cognates match: "automatización" and "automation" share "auto", "toma"..."""
    grams = Counter()
    for t in tokens:
        w = "_" + "".join(c for c in unicodedata.normalize("NFD", t) if not unicodedata.combining(c)) + "_"
        grams.update(w[i:i + NGRAM] for i in range(max(1, len(w) - NGRAM + 1)))
    return grams


def _language(r: dict) -> str | None:
    """Whisper's language if there is a transcript, else a guess from the most common words."""
    if r.get("lang"):
        return r["lang"]
    words = re.findall(r"[a-záéíóúñü]+", _full_text(r).lower())
    en, es = sum(w in EN_MARKERS for w in words), sum(w in ES_MARKERS for w in words)
    return None if en == es else ("en" if en > es else "es")


def cmd_similar(a):
    rs = [r for r in load_db()["reels"].values()
          if r.get("relevant") is True and _full_text(r) and in_collection(r, a.collection)]
    tokens = [_tokens(_full_text(r)) for r in rs]
    vecs = _tfidf([Counter(t) for t in tokens])
    n = len(rs)
    parent = list(range(n))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(n):
        for j in range(i + 1, n):
            if _cosine(vecs[i], vecs[j]) >= a.threshold:
                parent[find(i)] = find(j)
    groups = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)
    groups = [g for g in groups.values() if len(g) > 1]

    def label(i):
        return f"{rs[i]['shortcode']} @{rs[i].get('author') or '?'}: {_short(_full_text(rs[i]), 60)}"

    # Second pass, only between reels in different languages: there, shared words are rare.
    cross = []
    if a.ngram_threshold:
        langs = [_language(r) for r in rs]
        grams = _tfidf([_char_ngrams(t) for t in tokens])
        for i in range(n):
            for j in range(i + 1, n):
                if (langs[i] and langs[j] and langs[i] != langs[j] and find(i) != find(j)
                        and _cosine(grams[i], grams[j]) >= a.ngram_threshold):
                    cross.append((i, j))
    if not groups and not cross:
        print("No obvious duplicates by wording. Still compare meaning when merging.")
        return
    if groups:
        print(f"{len(groups)} candidate groups (same wording; confirm by meaning):")
        for g in sorted(groups, key=len, reverse=True):
            print("- " + " | ".join(label(i) for i in g))
    if cross:
        print(f"{len(cross)} possible matches across languages (similar spellings; confirm by meaning):")
        for i, j in cross:
            print(f"- {label(i)} | {label(j)}")


def cmd_recent(a):
    since = (a.now or time.time()) - a.days * 86400
    rs = [r for r in load_db()["reels"].values()
          if r.get("relevant") is True and (saved_ts(r) or 0) >= since
          and in_collection(r, a.collection)]
    if not rs:
        print(f"No relevant reels saved in the last {a.days} days.")
        return
    rs.sort(key=lambda r: saved_ts(r) or 0, reverse=True)
    entries = Counter(r.get("entry") for r in rs if r.get("entry"))
    print(f"{len(rs)} relevant reels saved in the last {a.days} days"
          f" ({len(entries)} digest entries):")
    for r in rs:
        print(f"  {_day(saved_ts(r))} {r['shortcode']} @{r.get('author') or '?'} "
              f"-> {r.get('entry') or '(not in digest yet)'}")


MARKS = ("tried", "discarded", "todo")  # todo = clear the mark


def cmd_mark(a):
    db = load_db()
    entries = db.setdefault("entries", {})
    known = {r.get("entry") for r in db["reels"].values() if r.get("entry")}
    unknown = []
    for slug in a.slugs:
        if slug not in known:
            unknown.append(slug)
        if a.status == "todo":
            entries.pop(slug, None)
            continue
        e = {"status": a.status, "updated": int(time.time())}
        if a.note:
            e["note"] = a.note
        entries[slug] = e
    save_db(db)
    print(f"Marked {len(a.slugs)} entries as {a.status}."
          + (f" Not linked to any reel yet (typo?): {', '.join(unknown)}" if unknown else ""))


def cmd_marks(_):
    entries = load_db().get("entries") or {}
    if not entries:
        print("No ideas marked as tried or discarded yet.")
        return
    for slug, e in sorted(entries.items(), key=lambda kv: (kv[1].get("status", ""), kv[0])):
        print(f"  {e.get('status', '?'):10} {slug:32} {_day(e.get('updated'))}"
              + (f"  {e['note']}" if e.get("note") else ""))


def cmd_show(a):
    db = load_db()
    for sc in a.codes:
        print(json.dumps(db["reels"].get(sc, {"error": f"unknown {sc}"}), ensure_ascii=False, indent=1))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status").set_defaults(fn=cmd_status)
    sub.add_parser("collections").set_defaults(fn=cmd_collections)
    sub.add_parser("unavailable").set_defaults(fn=cmd_unavailable)
    p = sub.add_parser("next"); p.add_argument("--limit", type=int, default=40)
    p.add_argument("--chars", type=int, default=220)
    p.add_argument("--maybe", action="store_true", help="also list 'maybe' reels with their transcript")
    p.set_defaults(fn=cmd_next)
    p = sub.add_parser("set"); p.add_argument("field"); p.add_argument("value")
    p.add_argument("codes", nargs="+"); p.set_defaults(fn=cmd_set)
    p = sub.add_parser("dump"); p.add_argument("--undigested", action="store_true")
    p.add_argument("--all", action="store_true"); p.add_argument("--chars", type=int, default=DUMP_CHARS)
    p.add_argument("--max-total", type=int, default=DUMP_BUDGET,
                   help="stop after about this many characters (0 = no limit)")
    p.add_argument("--offset", type=int, default=0, help="skip the first N reels (to continue)")
    p.set_defaults(fn=cmd_dump)
    p = sub.add_parser("similar"); p.add_argument("--threshold", type=float, default=0.3)
    p.add_argument("--ngram-threshold", type=float, default=0.1,
                   help="for reels in different languages (0 = skip that pass)")
    p.set_defaults(fn=cmd_similar)
    p = sub.add_parser("recent"); p.add_argument("--days", type=int, default=7)
    p.add_argument("--now", type=float, help=argparse.SUPPRESS)  # fixed clock for tests
    p.set_defaults(fn=cmd_recent)
    p = sub.add_parser("mark"); p.add_argument("status", choices=MARKS)
    p.add_argument("slugs", nargs="+"); p.add_argument("--note", help="why, in a few words")
    p.set_defaults(fn=cmd_mark)
    sub.add_parser("marks").set_defaults(fn=cmd_marks)
    p = sub.add_parser("show"); p.add_argument("codes", nargs="+"); p.set_defaults(fn=cmd_show)
    for name in ("next", "dump", "similar", "recent"):
        sub.choices[name].add_argument("--collection", help="only reels from this Instagram collection")
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
