"""Inspect and update the local reel database (used by Claude during triage and merging).

  db.py status                              counts at every stage, and per platform
  db.py collections                         Instagram collections and YouTube playlists, with
                                            how many reels each has
  db.py unavailable                         saved posts that were deleted or are private
  db.py next [--limit 40] [--field relevant] posts still waiting for triage, compact
  db.py set FIELD VALUE CODE [CODE ...]     e.g. set relevant true C1 C2 / set topic "Claude Code" C3
  db.py dump [--undigested] [--all]         relevant reels with caption + transcript, for merging
            [--max-total 60000] [--offset N]   output is capped; continue with --offset
  db.py similar [--threshold 0.3]           groups of reels that probably say the same thing,
            [--ngram-threshold 0.1]            also across languages (by similar spellings);
            [--engine auto|python|rust]        uses the Rust reels-similar if installed (faster)
  db.py recent [--days 7]                   relevant reels saved lately and their digest entry
  db.py mark tried|discarded|todo SLUG ... [--note TEXT]
                                            remember what the user did with a digest idea
  db.py marks [--status tried|discarded]    every idea marked tried or discarded (or only one kind),
                                            with how many reels were saved about it since
  db.py ideas [--status todo|tried|discarded] [--sort reels|recent|name]
            [--older-than DAYS]                every idea (slug) reels point to: how many reels,
                                            the newest saved and its mark, to reuse slugs;
                                            --older-than DAYS: only ideas with no reel saved
                                            lately (with --status todo: forgotten ideas)
  db.py ideas SLUG [SLUG ...]               the reels of these ideas: date, code, author, link
  db.py rename OLD NEW [--digest [PATH]]    move every reel of an idea (and its mark) to another
            [--dry-run]                        slug, after renaming it or merging it into NEW;
                                            --digest also renames {#OLD} and (#OLD) in digest.md;
                                            --dry-run only says what would change
  db.py check [--digest PATH] [--strict]    compare digest.md with the database: ideas no reel
            [--fix]                            points to, reels pointing to ideas that are gone,
                                            repeated slugs, broken (#slug) links and reels in
                                            an idea that are no longer relevant; --strict
                                            exits with status 1 when something needs fixing;
                                            --fix runs the db.py rename it is sure about;
                                            also hints at ideas with nearly the same slug

status, unavailable, next, dump, similar, recent and ideas accept --collection NAME to work only on
one Instagram collection or YouTube playlist (as db.py collections names it, case-insensitive);
a name no reel is in is an error that suggests the closest one.
  db.py show CODE [CODE ...]                full record

In set and show, a CODE can also be a pasted Instagram, TikTok or YouTube link.
"""
from __future__ import annotations

import argparse
import difflib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import DB_PATH, HOME, in_collection, load_db, resolve_code, save_db, split_codes  # noqa: E402


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


def _closest(name: str, known) -> str | None:
    """The known name a typo most likely meant (case and '-'/'_' are ignored), or None."""
    def norm(x):
        return x.casefold().replace("_", "-")

    by_norm = {norm(k): k for k in known}
    hit = difflib.get_close_matches(norm(name), list(by_norm), n=1, cutoff=0.75)
    return by_norm[hit[0]] if hit else None


def _guesses(names, known) -> str:
    """A "Did you mean" sentence for the names that have a close match, else an empty string."""
    pairs = [(n, _closest(n, known)) for n in names]
    pairs = [f"{g} (for {n})" if len(names) > 1 else g for n, g in pairs if g]
    return f" Did you mean: {', '.join(pairs)}?" if pairs else ""


PLATFORMS = (("instagram", "Instagram"), ("tiktok", "TikTok"), ("youtube", "YouTube"))


def platform(r: dict) -> str:
    """Where the reel was saved. Instagram reels predate the field, so it is the default."""
    return r.get("platform") or "instagram"


def _no_such_collection(name: str, known=()) -> None:
    guess = _closest(name.strip(), known)
    sys.exit(f"No reels in collection {name!r}."
             + (f" Did you mean --collection \"{guess}\"?" if guess else "")
             + " See the exact names with: db.py collections")


def _check_collection(name: str | None) -> None:
    """Stop on a collection no reel is in, instead of quietly finding nothing in it."""
    if not name:
        return
    reels = load_db()["reels"].values()
    if not any(in_collection(r, name) for r in reels):
        _no_such_collection(name, {r["collection"] for r in reels if r.get("collection")})


def cmd_status(a):
    rs = [r for r in load_db()["reels"].values() if in_collection(r, a.collection)]
    per_platform = Counter(platform(r) for r in rs)
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
    print(f"Database: {DB_PATH}" + (f" (collection {a.collection!r} only)" if a.collection else ""))
    for k in ["total", "with caption", "meta failed", "deleted or private", "triage: None", "triage: True",
              "triage: maybe", "triage: False", "transcribed", "transcribe failed", "images read",
              "merged into digest", "relevant & not yet in digest"]:
        label = {"triage: None": "not triaged yet", "triage: True": "relevant",
                 "triage: maybe": "maybe (decide after transcript)",
                 "triage: False": "not relevant"}.get(k, k)
        print(f"  {label:32} {c[k]}")
        if k == "total":
            for key, name in PLATFORMS:
                if per_platform[key]:
                    print(f"    {'from ' + name:30} {per_platform[key]}")


def cmd_collections(_):
    rs = list(load_db()["reels"].values())
    c = Counter(r.get("collection") or "" for r in rs)
    if not any(c):
        print("No collections recorded. They come from saved_collections.json in Instagram's official "
              "export, and from YouTube playlists (collect.py youtube).")
        return
    youtube_only = {name for name in c
                    if name and all(platform(r) == "youtube" for r in rs if r.get("collection") == name)}
    for name, n in sorted(c.items(), key=lambda kv: (-kv[1], kv[0])):
        shown = f"{name} (YouTube playlist)" if name in youtube_only else name or "(no collection)"
        print(f"  {shown:32} {n}")


def cmd_unavailable(a):
    reels = [r for r in load_db()["reels"].values() if in_collection(r, a.collection)]
    rs = [r for r in reels if r.get("meta") == "unavailable"]
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
# What an idea's {#slug} can hold, so its heading and (#slug) links can point to it.
SLUG_RE = re.compile(r"^[\w-]+$")


def _bad_slug(slug: str) -> str:
    hint = re.sub(r"[^\w-]+", "-", slug.strip().lower()).strip("-")
    return (f"{slug!r} is not a valid slug: use letters, digits, '-' or '_' (as in {{#{hint or 'my-idea'}}})."
            + (f" Try: {hint}" if hint else ""))


def cmd_set(a):
    val = _parse_value(a.value)
    if a.field not in SETTABLE:
        sys.exit(f"Unknown field {a.field!r}. Can be set: {', '.join(SETTABLE)}.")
    if a.field == "relevant" and val not in TRIAGE_VALUES:
        sys.exit(f"Invalid value {a.value!r} for relevant. Use: true, false, maybe or none.")
    if a.field == "entry" and val is not None and not (isinstance(val, str) and SLUG_RE.match(val)):
        sys.exit(_bad_slug(a.value) + " Nothing was changed.")
    db = load_db()
    known_before = Counter(r["entry"] for r in db["reels"].values() if r.get("entry"))
    missing, done, in_ideas = [], 0, {}
    for name in split_codes(a.codes):
        key = resolve_code(db["reels"], name)
        if key is None:
            missing.append(name)
        else:
            db["reels"][key][a.field] = val
            done += 1
            if a.field == "relevant" and val is not True and db["reels"][key].get("entry"):
                in_ideas[key] = db["reels"][key]["entry"]
    if not done:
        sys.exit(f"None of these codes are in the database, so nothing was changed: {', '.join(missing)}")
    save_db(db)
    print(f"Set {a.field}={val!r} on {done} reels."
          + (f" Unknown: {', '.join(missing)}" if missing else ""))
    if in_ideas:
        codes = " ".join(in_ideas)
        print(f"Warning: {len(in_ideas)} of these reels still back an idea: "
              + ", ".join(f"{k} ({slug})" for k, slug in in_ideas.items())
              + f". If they no longer belong there, take them out with: db.py set entry none {codes}")
    if a.field == "entry" and val is not None:
        warning = _near_slug_warning(val, known_before)
        if warning:
            print(warning)


def _near_slug_warning(slug: str, known: Counter) -> str:
    """A warning when `slug` is new but nearly the same as one in use (one idea split in two)."""
    if slug in known:
        return ""
    near = _closest(slug, known)
    if not near:
        return ""
    return (f"Warning: {slug!r} is a new idea, but {near!r} already has {known[near]} reels. "
            f"If they are the same idea, join them with: db.py rename {slug} {near}")


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


RUST_ENV = "SRD_REELS_SIMILAR"


def _rust_binary() -> str | None:
    """The optional Rust duplicate finder (rust/ in the repo): $SRD_REELS_SIMILAR, else on PATH."""
    path = os.environ.get(RUST_ENV)
    if path is not None:
        return path if path and Path(path).is_file() else None
    return shutil.which("reels-similar")


def _similar_rust(binary: str, rs: list, a) -> tuple:
    """Run reels-similar on these reels; indexes are used as codes so the answer maps back."""
    reels = {str(i): {"shortcode": str(i), "relevant": True, "caption": _full_text(r),
                      "lang": r["lang"] if isinstance(r.get("lang"), str) else None}
             for i, r in enumerate(rs)}
    out = subprocess.run([binary, "-", "--threshold", str(a.threshold),
                          "--ngram-threshold", str(a.ngram_threshold)],
                         input=json.dumps({"reels": reels}), capture_output=True, text=True,
                         encoding="utf-8", timeout=600)
    if out.returncode:
        raise RuntimeError(out.stderr.strip() or f"exit code {out.returncode}")
    res = json.loads(out.stdout)
    return ([[int(c) for c in g] for g in res["groups"]], [(int(i), int(j)) for i, j in res["cross"]])


def _similar_python(rs: list, a) -> tuple:
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
    groups = sorted((g for g in groups.values() if len(g) > 1), key=len, reverse=True)

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
    return groups, cross


def cmd_similar(a):
    rs = [r for r in load_db()["reels"].values()
          if r.get("relevant") is True and _full_text(r) and in_collection(r, a.collection)]
    binary = _rust_binary() if a.engine != "python" else None
    if a.engine == "rust" and not binary:
        sys.exit(f"reels-similar not found: build it in rust/ (cargo build --release) and put it on "
                 f"PATH, or set {RUST_ENV} to its path.")
    groups = None
    if binary:
        try:
            groups, cross = _similar_rust(binary, rs, a)
        except (OSError, ValueError, KeyError, TypeError, RuntimeError, subprocess.TimeoutExpired) as e:
            if a.engine == "rust":
                sys.exit(f"reels-similar failed: {e}")
            print(f"reels-similar failed ({e}); using the Python version.", file=sys.stderr)
    if groups is None:
        groups, cross = _similar_python(rs, a)

    def label(i):
        return f"{rs[i]['shortcode']} @{rs[i].get('author') or '?'}: {_short(_full_text(rs[i]), 60)}"

    if not groups and not cross:
        print("No obvious duplicates by wording. Still compare meaning when merging.")
        return
    if groups:
        print(f"{len(groups)} candidate groups (same wording; confirm by meaning):")
        for g in groups:
            print("- " + " | ".join(label(i) for i in g))
    if cross:
        print(f"{len(cross)} possible matches across languages (similar spellings; confirm by meaning):")
        for i, j in cross:
            print(f"- {label(i)} | {label(j)}")


def cmd_recent(a):
    since = (a.now or time.time()) - a.days * 86400
    rs = [r for r in load_db()["reels"].values()
          if r.get("relevant") is True and (saved_ts(r) or 0) >= since
          and in_collection(r, a.collection) and _has_content(r)]
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
    # an idea exists when a reel points to it; a slug only in "entries" can still be cleared
    known = {r.get("entry") for r in db["reels"].values() if r.get("entry")}
    if a.status == "todo":
        known |= set(entries)
    slugs = list(dict.fromkeys(a.slugs))
    unknown = [s for s in slugs if s not in known]
    slugs = [s for s in slugs if s in known]
    if not slugs:
        hint = sorted(known)
        guess = _guesses(unknown, known)
        if guess:
            more = guess
        elif hint:
            more = f" Known ideas: {', '.join(hint[:15])}" + (" ..." if len(hint) > 15 else "")
        else:
            more = " No reel has an entry yet: run db.py set entry SLUG CODE ... first."
        sys.exit("None of these ideas are linked to any reel, so nothing was marked (typo?): "
                 f"{', '.join(unknown)}.{more}")
    for slug in slugs:
        if a.status == "todo":
            entries.pop(slug, None)
            continue
        e = {"status": a.status, "updated": int(time.time())}
        # without --note the old note stays (marking again must not lose it); --note "" clears it
        note = (entries.get(slug) or {}).get("note") if a.note is None else a.note
        if note:
            e["note"] = note
        entries[slug] = e
    save_db(db)
    print(f"Marked {len(slugs)} entries as {a.status}."
          + (f" Skipped, not linked to any reel (typo?): {', '.join(unknown)}.{_guesses(unknown, known)}"
             if unknown else ""))


def cmd_marks(a):
    db = load_db()
    entries = db.get("entries") or {}
    if a.status:
        entries = {k: e for k, e in entries.items() if e.get("status") == a.status}
    if not entries:
        print(f"No ideas marked as {a.status} yet." if a.status
              else "No ideas marked as tried or discarded yet.")
        return
    newer = _saved_since_mark(db["reels"].values(), entries)
    for slug, e in sorted(entries.items(), key=lambda kv: (kv[1].get("status", ""), kv[0])):
        n = newer.get(slug, 0)
        print(f"  {e.get('status', '?'):10} {slug:32} {_day(e.get('updated'))}"
              + (f"  +{n} new" if n else "")
              + (f"  {e['note']}" if e.get("note") else ""))
    back = sorted(s for s, e in entries.items() if newer.get(s) and e.get("status") == "discarded")
    if back:
        print(f"Discarded but still saving reels about: {', '.join(back)}. Maybe worth another look:"
              f" db.py ideas {' '.join(back)}")
    elif newer:
        print("+N new: reels saved about that idea after it was marked (db.py ideas SLUG lists them).")


def _saved_since_mark(reels, entries: dict) -> dict:
    """{slug: how many of its reels were saved after the idea was last marked}.

    A reel with no known save date, or a mark with no date, is never counted as new."""
    out = Counter()
    for r in reels:
        e = entries.get(r.get("entry"))
        ts = saved_ts(r)
        if e and ts and isinstance(e.get("updated"), (int, float)) and ts > e["updated"]:
            out[r["entry"]] += 1
    return dict(out)


def cmd_ideas(a):
    db = load_db()
    marks = db.get("entries") or {}
    ideas = {}
    for r in db["reels"].values():
        if r.get("entry") and in_collection(r, a.collection):
            ideas.setdefault(r["entry"], []).append(r)
    if not ideas:
        print(f"No idea has reels from collection {a.collection!r} yet." if a.collection
              else "No ideas yet: reels get one with db.py set entry SLUG CODE ... while merging.")
        return
    def status(slug):
        return marks.get(slug, {}).get("status", "todo")

    if a.slugs:
        if a.older_than is not None:
            sys.exit("--older-than filters the list of ideas; leave out the slugs to use it.")
        _show_ideas(a.slugs, ideas, marks, a.collection)
        return

    def newest(rs):
        return max((saved_ts(r) or 0 for r in rs), default=0)

    def old_enough(rs):
        # an idea with no known save date cannot be said to be old, so it is left out
        if a.older_than is None:
            return True
        n = newest(rs)
        return bool(n) and n < (a.now or time.time()) - a.older_than * 86400

    order = {"reels": lambda kv: (-len(kv[1]), kv[0]),
             "recent": lambda kv: (-newest(kv[1]), kv[0]),  # unknown dates (0) go last
             "name": lambda kv: kv[0]}[a.sort]
    rows = sorted(((slug, rs) for slug, rs in ideas.items()
                   if (not a.status or status(slug) == a.status) and old_enough(rs)),
                  key=order)
    old = f" with no reel saved in the last {a.older_than} days" if a.older_than is not None else ""
    if not rows:
        what = [f"is {a.status}"] if a.status else []
        if a.older_than is not None:
            what.append(f"has gone {a.older_than} days without a new reel")
        print(f"None of the {len(ideas)} ideas {' and '.join(what)}.")
        return
    where = f" with reels from {a.collection!r}" if a.collection else ""
    print(f"{len(rows)} {a.status + ' ' if a.status else ''}ideas{where}{old} (reels, newest saved, mark):")
    width = max(len(slug) for slug, _ in rows)
    for slug, rs in rows:
        print(f"  {slug:{width}}  {len(rs):3}  {_day(newest(rs) or None)}  {status(slug)}")


def _show_ideas(slugs, ideas: dict, marks: dict, collection: str | None) -> None:
    """The reels behind each slug, newest saved first, to see where an idea comes from."""
    slugs = list(dict.fromkeys(slugs))
    unknown = [s for s in slugs if s not in ideas]
    if len(unknown) == len(slugs):
        where = f" from collection {collection!r}" if collection else ""
        sys.exit(f"No reel{where} points to {', '.join(unknown)} (typo?).{_guesses(unknown, ideas)}"
                 " See every idea with: db.py ideas")
    for slug in slugs:
        if slug not in ideas:
            continue
        rs = sorted(ideas[slug], key=lambda r: saved_ts(r) or 0, reverse=True)
        m = marks.get(slug, {})
        print(f"{slug}: {len(rs)} reels, {m.get('status', 'todo')}"
              + (f" ({m['note']})" if m.get("note") else ""))
        for r in rs:
            print(f"  {_day(saved_ts(r))}  {r['shortcode']}  @{r.get('author') or '?'}  {r['url']}")
    if unknown:
        print(f"Skipped, no reel points to: {', '.join(unknown)} (typo?).{_guesses(unknown, ideas)}")


def cmd_rename(a):
    old, new = a.old, a.new
    if not SLUG_RE.match(new):
        sys.exit(_bad_slug(new))
    if old == new:
        sys.exit("The old and new slugs are the same: nothing to rename.")
    digest = Path(a.digest).expanduser() if a.digest else None
    if digest and not digest.exists():
        sys.exit(f"Not found: {digest}. Nothing was renamed.")
    db = load_db()
    entries = db.setdefault("entries", {})
    if not any(r.get("entry") == old for r in db["reels"].values()) and old not in entries:
        known = sorted({r["entry"] for r in db["reels"].values() if r.get("entry")} | set(entries))
        guess = _closest(old, known)
        sys.exit(f"No reel points to {old!r} and it has no mark, so nothing was renamed (typo?)."
                 + (f" Did you mean {guess!r}?" if guess else "")
                 + (f" Known ideas: {', '.join(known[:15])}" + (" ..." if len(known) > 15 else "")
                    if known else ""))
    msg = rename_in_db(db, old, new, dry=a.dry_run)
    if not a.dry_run:
        save_db(db)
    print(msg)
    if digest:
        print(rename_in_digest(digest, old, new, dry=a.dry_run))
    if a.dry_run:
        print("Dry run: nothing was changed. Run it again without --dry-run to apply it.")


def rename_in_db(db: dict, old: str, new: str, dry: bool = False) -> str:
    """Point every reel of idea `old` (and its mark) to `new`, in memory; says what moved.

    With dry=True nothing changes and the message says what would happen.
    """
    entries = db.setdefault("entries", {})
    moved = [r for r in db["reels"].values() if r.get("entry") == old]
    already = sum(1 for r in db["reels"].values() if r.get("entry") == new)
    if not dry:
        for r in moved:
            r["entry"] = new
    note = ""
    if old in entries:
        mark = entries[old]
        if new in entries:
            note = (f" {'Would keep' if dry else 'Kept'} the {entries[new].get('status', '?')} mark "
                    f"of {new!r} and {'drop' if dry else 'dropped'} the "
                    f"{mark.get('status', '?')} mark of {old!r}.")
        else:
            note = f" Its {mark.get('status', '?')} mark {'would move' if dry else 'moved'} too."
        if not dry:
            mark = entries.pop(old)
            entries.setdefault(new, mark)
    return (f"{'Would move' if dry else 'Moved'} {len(moved)} reels from {old!r} to {new!r}"
            + (f" (merged with the {already} already there)." if already else ".") + note)


def rename_in_digest(path: Path, old: str, new: str, dry: bool = False) -> str:
    """Rename the {#old} heading anchor and every (#old) link in digest.md; says what changed.

    With dry=True the file is left alone and the message says what would change.
    """
    text = path.read_text("utf-8")
    both = f"{{#{old}}}" in text and f"{{#{new}}}" in text
    text, headings = re.subn(r"\{#" + re.escape(old) + r"\}", f"{{#{new}}}", text)
    text, links = re.subn(r"\]\(#" + re.escape(old) + r"\)", f"](#{new})", text)
    if not headings and not links:
        return f"{path.name} has no {{#{old}}} or (#{old}): {'would be ' if dry else ''}left as it was."
    if not dry:
        path.write_text(text, "utf-8")
    msg = (f"In {path.name}: {'would rename' if dry else 'renamed'} {headings} headings and "
           f"{links} links to {{#{new}}}.")
    if both:
        msg += (f" It {'would then have' if dry else 'now has'} two {{#{new}}} ideas: merge their "
                "text into one entry (db.py check lists repeated slugs).")
    return msg


def _linked(db: dict) -> dict[str, list[str]]:
    """Each idea slug reels point to, with the codes of those reels."""
    linked = {}
    for r in db["reels"].values():
        if r.get("entry"):
            linked.setdefault(r["entry"], []).append(r["shortcode"])
    return linked


def sure_rename(db: dict, digest_text: str) -> tuple[str, str] | None:
    """(old, new) when exactly one slug lost its idea and exactly one idea has no reels.

    That is what renaming an idea in digest.md (and forgetting db.py rename) leaves behind,
    so it is the only fix db.py check --fix applies without asking.
    """
    from export_digest import parse_digest

    slugs = {i["slug"] for i in parse_digest(digest_text)["ideas"]}
    linked = _linked(db)
    lost = sorted(set(linked) - slugs)
    unbacked = sorted(slugs - set(linked))
    return (lost[0], unbacked[0]) if len(lost) == 1 and len(unbacked) == 1 else None


def check_digest(db: dict, digest_text: str) -> list[str]:
    """Problems between digest.md and reels.json, as lines to print. Empty when they agree."""
    from export_digest import ANCHOR_LINK_RE, parse_digest

    ideas = parse_digest(digest_text)["ideas"]
    slugs = Counter(i["slug"] for i in ideas)
    linked = _linked(db)
    problems = []
    for slug, n in sorted(slugs.items()):
        if n > 1:
            problems.append(f"{n} ideas share the slug {{#{slug}}}: give each its own, "
                            "or their links and reels get mixed up.")
    lost = sorted(set(linked) - set(slugs))
    unbacked = sorted(set(slugs) - set(linked))
    for slug in lost:
        codes = linked[slug]
        # one lost slug and one idea without reels: almost always the same idea, renamed
        target = unbacked[0] if len(lost) == 1 and len(unbacked) == 1 else "NEW-SLUG"
        problems.append(f"{len(codes)} reels point to {slug!r}, which is not in the digest "
                        f"(renamed or lost while merging?): {', '.join(codes[:8])}"
                        + (" ..." if len(codes) > 8 else "")
                        + (f". Probably renamed to {{#{target}}}: " if target != "NEW-SLUG"
                           else ". Point them to the idea they belong to: ")
                        + f"db.py rename {slug} {target}")
    for slug in unbacked:
        problems.append(f"No reel points to {{#{slug}}}: record its sources with "
                        f"db.py set entry {slug} CODE ...")
    for slug in sorted(set(ANCHOR_LINK_RE.findall(digest_text)) - set(slugs)):
        problems.append(f"A link goes to (#{slug}), but no idea has that slug.")
    for slug in sorted(set(db.get("entries") or {}) - set(slugs)):
        problems.append(f"{slug!r} is marked {db['entries'][slug].get('status', '?')} "
                        "but is not in the digest.")
    demoted = reclassified(db)
    if demoted:
        codes = " ".join(demoted)
        problems.append(f"{len(demoted)} reels back an idea but are not marked relevant (triaged again "
                        f"after merging?), so dump and similar skip them: {codes}. If they belong "
                        f"there: db.py set relevant true {codes}; if not: db.py set entry none {codes}")
    return problems


def reclassified(db: dict) -> list[str]:
    """Codes of reels that point to an idea but whose triage is no longer 'relevant'."""
    return [r["shortcode"] for r in db["reels"].values()
            if r.get("entry") and r.get("relevant") is not True]


NEAR_SLUG = 0.85  # subagent/subagents, hook/hooks, mcp_servers/mcp-servers; not ai-video/ai-voice


def near_duplicate_slugs(db: dict, digest_text: str) -> list[str]:
    """Pairs of digest ideas whose slugs are nearly the same, with the rename that merges them.

    Only a hint: two ideas can have close slugs on purpose, so it never counts as a problem.
    Slugs that differ in their numbers (step-1, step-2) are left alone.
    """
    from export_digest import parse_digest

    slugs = sorted({i["slug"] for i in parse_digest(digest_text)["ideas"]})
    reels = Counter(r["entry"] for r in db["reels"].values() if r.get("entry"))

    def norm(x):
        return x.casefold().replace("_", "-")

    hints = []
    for i, x in enumerate(slugs):
        for y in slugs[i + 1:]:
            if re.findall(r"\d+", x) != re.findall(r"\d+", y):
                continue
            if difflib.SequenceMatcher(None, norm(x), norm(y)).ratio() < NEAR_SLUG:
                continue
            # merge the idea with fewer reels into the one with more (on a tie, into the first)
            old, new = sorted((x, y), key=lambda s: (reels[s], s == x))
            hints.append(f"{{#{old}}} ({reels[old]} reels) and {{#{new}}} ({reels[new]} reels) look "
                         f"like the same idea. If they are, merge them with: "
                         f"db.py rename {old} {new} --digest (then join their text in digest.md)")
    return hints


def cmd_check(a):
    path = Path(a.digest).expanduser()
    if not path.exists():
        sys.exit(f"Not found: {path}. Write the digest first (step 5).")
    from export_digest import parse_digest

    text = path.read_text("utf-8")
    db = load_db()
    ideas = len({i["slug"] for i in parse_digest(text)["ideas"]})
    if a.fix:
        pair = sure_rename(db, text)
        if pair:
            print(f"Fixed: {rename_in_db(db, *pair)}")
            save_db(db)
        else:
            print("Nothing to fix automatically: --fix only renames when one slug lost its idea "
                  "and one idea has no reels.")
    problems = check_digest(db, text)
    waiting = sum(1 for r in db["reels"].values()
                  if r.get("relevant") is True and not r.get("entry") and _has_content(r))
    if waiting:
        problems.append(f"{waiting} relevant reels are not in any idea yet: db.py dump --undigested")
    near = near_duplicate_slugs(db, text)
    if not problems:
        print(f"digest.md and the database agree ({ideas} ideas).")
    else:
        print(f"{len(problems)} things to fix in {path.name} ({ideas} ideas):")
        for p in problems:
            print(f"- {p}")
    if near:
        print("Maybe the same idea (only a hint, --strict ignores it):")
        for h in near:
            print(f"- {h}")
    if problems and a.strict:
        sys.exit(1)


def cmd_show(a):
    reels = load_db()["reels"]
    found = 0
    for name in split_codes(a.codes):
        key = resolve_code(reels, name)
        found += key is not None
        print(json.dumps(reels[key] if key else {"error": f"unknown {name}"}, ensure_ascii=False, indent=1))
    if not found:
        sys.exit("None of these codes are in the database.")


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
    p.add_argument("--engine", choices=("auto", "python", "rust"), default="auto",
                   help="auto uses the faster Rust reels-similar when it is installed")
    p.set_defaults(fn=cmd_similar)
    p = sub.add_parser("recent"); p.add_argument("--days", type=int, default=7)
    p.add_argument("--now", type=float, help=argparse.SUPPRESS)  # fixed clock for tests
    p.set_defaults(fn=cmd_recent)
    p = sub.add_parser("mark"); p.add_argument("status", choices=MARKS)
    p.add_argument("slugs", nargs="+")
    p.add_argument("--note", help="why, in a few words; kept when marking again without it, \"\" clears it")
    p.set_defaults(fn=cmd_mark)
    p = sub.add_parser("marks")
    p.add_argument("--status", choices=("tried", "discarded"), help="list only this kind of mark")
    p.set_defaults(fn=cmd_marks)
    p = sub.add_parser("ideas")
    p.add_argument("slugs", nargs="*", help="list the reels of these ideas instead")
    p.add_argument("--status", choices=MARKS, help="only ideas with this mark (todo = not marked)")
    p.add_argument("--sort", choices=("reels", "recent", "name"), default="reels",
                   help="most reels first (default), newest saved reel first, or by slug")
    p.add_argument("--older-than", type=int, metavar="DAYS",
                   help="only ideas whose newest reel was saved more than DAYS days ago")
    p.add_argument("--now", type=float, help=argparse.SUPPRESS)  # fixed clock for tests
    p.set_defaults(fn=cmd_ideas)
    p = sub.add_parser("rename"); p.add_argument("old"); p.add_argument("new")
    p.add_argument("--digest", nargs="?", const=str(HOME / "digest.md"),
                   help="also rename {#OLD} and (#OLD) in this digest (default WORK/digest.md)")
    p.add_argument("--dry-run", action="store_true",
                   help="only say what would move and change, without writing anything")
    p.set_defaults(fn=cmd_rename)
    p = sub.add_parser("check"); p.add_argument("--digest", default=str(HOME / "digest.md"))
    p.add_argument("--strict", action="store_true",
                   help="exit with status 1 when there is something to fix (for scripts and CI)")
    p.add_argument("--fix", action="store_true",
                   help="apply the one fix that needs no judgement: the rename check is sure of")
    p.set_defaults(fn=cmd_check)
    p = sub.add_parser("show"); p.add_argument("codes", nargs="+"); p.set_defaults(fn=cmd_show)
    for name in ("status", "unavailable", "next", "dump", "similar", "recent", "ideas"):
        sub.choices[name].add_argument("--collection",
                                       help="only reels from this Instagram collection or YouTube playlist")
    a = ap.parse_args()
    _check_collection(getattr(a, "collection", None))
    a.fn(a)


if __name__ == "__main__":
    main()
