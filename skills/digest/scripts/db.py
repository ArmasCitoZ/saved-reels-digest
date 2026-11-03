"""Inspect and update the local reel database (used by Claude during triage and merging).

  db.py status                              counts at every stage
  db.py next [--limit 40] [--field relevant] posts still waiting for triage, compact
  db.py set FIELD VALUE CODE [CODE ...]     e.g. set relevant true C1 C2 / set topic "Claude Code" C3
  db.py dump [--undigested] [--all]         relevant reels with caption + transcript, for merging
  db.py similar [--threshold 0.3]           groups of reels that probably say the same thing
  db.py show CODE [CODE ...]                full record
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import DB_PATH, load_db, save_db  # noqa: E402


def _short(s: str | None, n: int) -> str:
    s = re.sub(r"\s+", " ", s or "").strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def _parse_value(v: str):
    low = v.lower()
    return {"true": True, "false": False, "null": None, "none": None}.get(low, v)


def cmd_status(_):
    rs = list(load_db()["reels"].values())
    c = Counter()
    for r in rs:
        c["total"] += 1
        c["with caption"] += bool(r.get("caption"))
        c["meta failed"] += r.get("meta") == "failed"
        c[f"triage: {r.get('relevant')}"] += 1
        c["transcribed"] += bool(r.get("transcript"))
        c["transcribe failed"] += r.get("transcribe") == "failed"
        c["merged into digest"] += bool(r.get("entry"))
    relevant = [r for r in rs if r.get("relevant") is True]
    c["relevant & not yet in digest"] = sum(1 for r in relevant if not r.get("entry"))
    print(f"Database: {DB_PATH}")
    for k in ["total", "with caption", "meta failed", "triage: None", "triage: True",
              "triage: maybe", "triage: False", "transcribed", "transcribe failed",
              "merged into digest", "relevant & not yet in digest"]:
        label = {"triage: None": "not triaged yet", "triage: True": "relevant",
                 "triage: maybe": "maybe (decide after transcript)",
                 "triage: False": "not relevant"}.get(k, k)
        print(f"  {label:32} {c[k]}")


def cmd_next(a):
    rs = [r for r in load_db()["reels"].values()
          if r.get("relevant") is None or (a.maybe and r.get("relevant") == "maybe")]
    if not rs:
        print("Nothing left to triage.")
        return
    print(f"{len(rs)} waiting. Showing {min(a.limit, len(rs))}:")
    for r in rs[: a.limit]:
        text = r.get("caption") or ""
        if a.maybe and r.get("transcript"):
            text = f"{text} || TRANSCRIPT: {r['transcript']}"
        print(f"{r['shortcode']} | @{r.get('author') or '?'} | {r.get('collection') or ''} | "
              f"{_short(text, a.chars) or '(no caption)'}")


def cmd_set(a):
    db = load_db()
    val = _parse_value(a.value)
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


def cmd_dump(a):
    rs = [r for r in load_db()["reels"].values()
          if (a.all or r.get("relevant") is True) and not (a.undigested and r.get("entry"))]
    for r in rs:
        print(f"### {r['shortcode']}  @{r.get('author') or '?'}  {r['url']}"
              + (f"  [entry: {r['entry']}]" if r.get("entry") else ""))
        if r.get("caption"):
            print(f"CAPTION: {_short(r['caption'], a.chars)}")
        if r.get("transcript"):
            print(f"TRANSCRIPT ({r.get('lang', '?')}): {_short(r['transcript'], a.chars * 3)}")
        print()
    print(f"({len(rs)} reels)", file=sys.stderr)


# ---------------------------------------------------------------- similarity
STOP = set("""a al algo como con de del el ella en es esa ese esta este esto hay la las le lo los
mas me mi muy no o para pero por que se si sin su sus te tu un una y ya yo the a an and are as at be
but by can do for from has have how i if in is it its just me my not of on or so that the this to up
was we what when with you your youre im dont like get got one all out more about now here there
will then them they their which who really very want need make use using""".split())


def _tokens(text: str):
    words = re.findall(r"[a-záéíóúñü0-9][a-záéíóúñü0-9+#.-]{1,}", text.lower())
    return [w.strip(".-") for w in words if w not in STOP and not w.isdigit()]


def cmd_similar(a):
    rs = [r for r in load_db()["reels"].values()
          if r.get("relevant") is True and (r.get("caption") or r.get("transcript"))]
    docs = [Counter(_tokens(f"{r.get('caption', '')} {r.get('transcript', '')}")) for r in rs]
    df = Counter(t for d in docs for t in d)
    n = len(docs)
    vecs = []
    for d in docs:
        v = {t: (1 + math.log(c)) * math.log((n + 1) / (df[t] + 0.5)) for t, c in d.items()}
        norm = math.sqrt(sum(x * x for x in v.values())) or 1.0
        vecs.append({t: x / norm for t, x in v.items()})
    parent = list(range(n))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    pairs = []
    for i in range(n):
        for j in range(i + 1, n):
            vi, vj = (vecs[i], vecs[j]) if len(vecs[i]) < len(vecs[j]) else (vecs[j], vecs[i])
            s = sum(x * vj.get(t, 0.0) for t, x in vi.items())
            if s >= a.threshold:
                pairs.append((s, i, j))
                parent[find(i)] = find(j)
    groups = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)
    groups = [g for g in groups.values() if len(g) > 1]
    if not groups:
        print("No obvious duplicates by wording. Still compare meaning when merging.")
        return
    print(f"{len(groups)} candidate groups (same wording; confirm by meaning):")
    for g in sorted(groups, key=len, reverse=True):
        print("- " + " | ".join(f"{rs[i]['shortcode']} @{rs[i].get('author') or '?'}: "
                                 f"{_short(rs[i].get('caption') or rs[i].get('transcript'), 60)}"
                                 for i in g))


def cmd_show(a):
    db = load_db()
    for sc in a.codes:
        print(json.dumps(db["reels"].get(sc, {"error": f"unknown {sc}"}), ensure_ascii=False, indent=1))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status").set_defaults(fn=cmd_status)
    p = sub.add_parser("next"); p.add_argument("--limit", type=int, default=40)
    p.add_argument("--chars", type=int, default=220)
    p.add_argument("--maybe", action="store_true", help="also list 'maybe' reels with their transcript")
    p.set_defaults(fn=cmd_next)
    p = sub.add_parser("set"); p.add_argument("field"); p.add_argument("value")
    p.add_argument("codes", nargs="+"); p.set_defaults(fn=cmd_set)
    p = sub.add_parser("dump"); p.add_argument("--undigested", action="store_true")
    p.add_argument("--all", action="store_true"); p.add_argument("--chars", type=int, default=600)
    p.set_defaults(fn=cmd_dump)
    p = sub.add_parser("similar"); p.add_argument("--threshold", type=float, default=0.3)
    p.set_defaults(fn=cmd_similar)
    p = sub.add_parser("show"); p.add_argument("codes", nargs="+"); p.set_defaults(fn=cmd_show)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
