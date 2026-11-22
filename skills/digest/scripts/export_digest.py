"""Export digest.md to an Obsidian vault: one note per idea plus an index note.

  export_digest.py --vault ~/Obsidian/MyVault [--folder "Saved reels"] [--digest PATH] [--prune]
  export_digest.py --json [--digest PATH]

Reads the digest written in step 5 (default: WORK/digest.md) and writes into
VAULT/FOLDER:

  INDEX.md          map of content: "Do these first" and every idea by category,
                    with ✅ / 🚫 next to the ideas marked tried / discarded
  <Idea title>.md   one note per idea, with frontmatter (title, date, tags,
                    aliases, status, reels, last_saved, sources) and links to the
                    other ideas of its category

Links are relative markdown links, so the notes also render on GitHub and in
VS Code. Safe to re-run: notes are rewritten from the digest, but anything you
write under a "## My notes" heading in a note is kept. Files in the folder that
this script did not create are never overwritten.

Notes for ideas that are no longer in the digest (merged or removed) are listed
and left alone; --prune deletes them, except the ones with something written
under "## My notes", which are kept and listed.

With --json it writes nothing and prints the digest as structured JSON instead
(title, date, top list and every idea with its category, body, source links,
tried/discarded status, and `reels` / `last_saved` from reels.json). Claude uses
that to fill other tools, such as Notion through its connector, without
re-parsing the markdown by hand.

An idea's status comes from the marks `db.py mark` saved in reels.json when
there is one (like the viewer does), else from the digest's own Status line.
`reels` (how many reels back the idea) and `last_saved` (when the newest was saved)
also come from reels.json, so Bases or Dataview can sort ideas like `db.py ideas --sort`.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import DB_PATH, HOME  # noqa: E402

MARKER = "saved-reels-digest"  # frontmatter `generator:` value identifying our notes
MY_NOTES = "## My notes"
FIRST_SECTION = "Do these first"
# the digest is written in the user's language, so the heading may be translated
TOP_HEADINGS = {FIRST_SECTION.casefold(), "haz esto primero"}
ENTRY_RE = re.compile(r"^###\s+(?P<title>.+?)\s*(?:\{#(?P<slug>[\w-]+)\})?\s*$")
DATE_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")
ANCHOR_LINK_RE = re.compile(r"\]\(#([\w-]+)\)")
URL_RE = re.compile(r"\]\((https?://[^)\s]+)\)")
STATUS_RE = re.compile(r"^\*\*Status:\*\*\s*(?:\S+\s+)?(?P<status>Tried|Discarded)\b", re.I | re.M)
NUMBERED_RE = re.compile(r"^\s*\d+\.\s")
# the marks are the same in every language, even when "Status: Tried" gets translated:
# "**Estado:** ✅ Probado: nota" (one word after the mark, so "✅ follow these steps" is not one)
STATUS_MARK_RE = re.compile(r"^\*\*[^*\n]+:\*\*\s*(?P<mark>✅|🚫)\ufe0f?\s*\S+\s*(?::|$)")
STATUS_MARKS = {"✅": "tried", "🚫": "discarded"}


def slugify(text: str) -> str:
    s = re.sub(r"[^\w\s-]", "", text.lower(), flags=re.UNICODE)
    return re.sub(r"[\s_]+", "-", s).strip("-") or "idea"


def _in_code(lines: list) -> list:
    """For each line, whether it is part of a fenced code block. An unclosed fence does not count."""
    out, opened = [], None
    for n, line in enumerate(lines):
        text = line.strip()
        marker = text[:3] if text.startswith(("```", "~~~")) else None
        if opened is not None:
            out.append(True)
            if marker == lines[opened].strip()[:3] and not text.strip(marker[0]):
                opened = None
        else:
            out.append(bool(marker))
            if marker:
                opened = n
    if opened is not None:
        out[opened:] = [False] * (len(lines) - opened)
    return out


def _top_section(lines: list, in_code: list) -> str | None:
    """The first ## section is the top list if it is numbered and holds no ideas, in any language."""
    headings = [n for n, line in enumerate(lines) if line.startswith("## ") and not in_code[n]]
    if not headings:
        return None
    end = headings[1] if len(headings) > 1 else len(lines)
    body = lines[headings[0] + 1:end]
    if any(ENTRY_RE.match(line) for line in body) or not any(NUMBERED_RE.match(line) for line in body):
        return None
    return lines[headings[0]][3:].strip()


def idea_status(body: str) -> str:
    """todo, tried or discarded, from the line the digest puts first under an idea's heading."""
    first = next((line for line in body.splitlines() if line.strip()), "")
    m = STATUS_MARK_RE.match(first)
    if m:
        return STATUS_MARKS[m["mark"]]
    m = STATUS_RE.search(body)
    return m["status"].lower() if m else "todo"


def parse_digest(text: str) -> dict:
    """Split digest.md into title, update date, the top list and ideas by category."""
    out = {"title": "Saved reels digest", "date": None, "top": [], "top_heading": FIRST_SECTION, "ideas": []}
    lines = text.splitlines()
    in_code = _in_code(lines)
    top = _top_section(lines, in_code)

    def is_top(name: str) -> bool:
        return name == top or name.casefold() in TOP_HEADINGS

    section = None
    idea = None
    for n, line in enumerate(lines):
        if in_code[n]:  # a "## comment" in a code sample is not a heading
            if idea is not None:
                idea["body"].append(line)
            continue
        if line.startswith("# ") and not out["ideas"] and section is None:
            out["title"] = line[2:].strip()
            continue
        if line.startswith("## "):
            section = line[3:].strip()
            idea = None
            if is_top(section):
                out["top_heading"] = section
            continue
        m = ENTRY_RE.match(line)
        if m and section and not is_top(section):
            idea = {"title": m["title"], "slug": m["slug"] or slugify(m["title"]),
                    "category": section, "body": []}
            out["ideas"].append(idea)
            continue
        if section is None and out["date"] is None and DATE_RE.search(line):
            out["date"] = DATE_RE.search(line).group(1)
        elif section and is_top(section) and NUMBERED_RE.match(line):
            out["top"].append(re.sub(r"^\s*\d+\.\s*", "", line).strip())
        elif idea is not None:
            idea["body"].append(line)
    for i in out["ideas"]:
        i["body"] = "\n".join(i["body"]).strip()
    return out


def safe_filename(title: str) -> str:
    """Note name valid on Windows, macOS and Linux, and usable as an Obsidian link."""
    name = re.sub(r'[\\/:*?"<>|#^\[\]]', "", title)
    name = re.sub(r"\s+", " ", name).strip(" .")
    return name[:120] or "idea"


# device names Windows refuses as file names, with any extension
WINDOWS_RESERVED = {"con", "prn", "aux", "nul", *(f"com{n}" for n in range(1, 10)),
                    *(f"lpt{n}" for n in range(1, 10))}


def assign_filenames(ideas: list) -> None:
    used = {"index", *WINDOWS_RESERVED}  # "index" is the map of content, INDEX.md
    for i in ideas:
        base = safe_filename(i["title"])
        name = base
        if name.lower() in used:
            name = f"{base} ({i['slug']})"
        n = 2
        while name.lower() in used:
            name = f"{base} ({i['slug']}-{n})"
            n += 1
        used.add(name.lower())
        i["file"] = f"{name}.md"


def link(text: str, target: str) -> str:
    return f"[{text}]({quote(target)})"


def _yaml_str(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'


def rewrite_anchors(text: str, by_slug: dict) -> str:
    """`[x](#slug)` inside the digest becomes a link to that idea's note."""
    def repl(m):
        target = by_slug.get(m.group(1))
        return f"]({quote(target['file'])})" if target else m.group(0)
    return ANCHOR_LINK_RE.sub(repl, text)


def render_note(idea: dict, ideas: list, by_slug: dict, day: str, index_name: str,
                marks: dict | None = None, stats: dict | None = None) -> str:
    sources = list(dict.fromkeys(URL_RE.findall(idea["body"])))
    tags = ["saved-reels", slugify(idea["category"])]
    status, note = resolve_status(idea, marks)
    # status is a property, so Bases and Dataview can filter tried / discarded / todo ideas
    fm = ["---", f"title: {_yaml_str(idea['title'])}", f"date: {day}",
          f"tags: [{', '.join(tags)}]", f"aliases: [{idea['slug']}]",
          f"category: {_yaml_str(idea['category'])}", f"status: {status}"]
    if note:
        fm.append(f"note: {_yaml_str(note)}")
    # numbers and dates (not strings), so Bases and Dataview can sort and compare them
    st = (stats or {}).get(idea["slug"])
    if st:
        fm.append(f"reels: {st['reels']}")
        if st["last_saved"]:
            fm.append(f"last_saved: {st['last_saved']}")
    fm.append(f"generator: {MARKER}")
    if sources:
        fm.append("sources:")
        fm += [f"  - {u}" for u in sources]
    fm.append("---")
    related = [link(o["title"], o["file"]) for o in ideas
               if o["category"] == idea["category"] and o is not idea]
    parts = ["\n".join(fm), f"# {idea['title']}", rewrite_anchors(idea["body"], by_slug)]
    if related:
        parts.append("Related: " + " · ".join(related))
    parts.append("Up: " + link("Index", index_name))
    return "\n\n".join(p for p in parts if p) + "\n"


INDEX_MARKS = {"tried": " ✅", "discarded": " 🚫", "todo": ""}


def render_index(digest: dict, by_slug: dict, day: str, marks: dict | None = None) -> str:
    status = {i["slug"]: resolve_status(i, marks)[0] for i in digest["ideas"]}
    done = Counter(status.values())
    summary = f"_Exported from digest.md on {day} · {len(digest['ideas'])} ideas"
    if done["tried"] or done["discarded"]:
        summary += f" · ✅ {done['tried']} tried · 🚫 {done['discarded']} discarded"
    lines = ["---", f"title: {_yaml_str(digest['title'])}", f"date: {day}",
             "tags: [saved-reels]", f"generator: {MARKER}", "---", "",
             f"# {digest['title']}", "", summary + "_", ""]
    if digest["top"]:
        lines += [f"## {digest['top_heading']}", ""]
        lines += [f"{n}. {rewrite_anchors(t, by_slug)}" for n, t in enumerate(digest["top"], 1)]
        lines.append("")
    categories = list(dict.fromkeys(i["category"] for i in digest["ideas"]))
    for cat in categories:
        lines += [f"## {cat}", ""]
        lines += [f"- {link(i['title'], i['file'])}{INDEX_MARKS[status[i['slug']]]}"
                  for i in digest["ideas"] if i["category"] == cat]
        lines.append("")
    return "\n".join(lines)


def _is_ours(path: Path) -> bool:
    head = path.read_text("utf-8", "replace")[:2000]
    return head.startswith("---") and f"generator: {MARKER}" in head.split("\n---", 1)[0]


def _my_notes(path: Path) -> str:
    text = path.read_text("utf-8", "replace")
    idx = text.find(f"\n{MY_NOTES}")
    return text[idx + 1:].rstrip() + "\n" if idx >= 0 else ""


def _has_my_notes(path: Path) -> bool:
    """Whether the user wrote anything under "## My notes" (an empty heading does not count)."""
    return bool(_my_notes(path)[len(MY_NOTES):].strip())


def export(digest_text: str, out_dir: Path, today: str | None = None, marks: dict | None = None,
           prune: bool = False, stats: dict | None = None) -> dict:
    digest = parse_digest(digest_text)
    if not digest["ideas"]:
        raise ValueError("no ideas found: expected '### Idea title {#slug}' entries under '## Category'")
    day = digest["date"] or today or date.today().isoformat()
    assign_filenames(digest["ideas"])
    by_slug = {i["slug"]: i for i in digest["ideas"]}
    out_dir.mkdir(parents=True, exist_ok=True)
    report = {"written": [], "skipped": [], "stale": [], "pruned": []}
    files = {"INDEX.md": render_index(digest, by_slug, day, marks)}
    for i in digest["ideas"]:
        files[i["file"]] = render_note(i, digest["ideas"], by_slug, day, "INDEX.md", marks, stats)
    for name, content in files.items():
        path = out_dir / name
        if path.exists():
            if not _is_ours(path):
                report["skipped"].append(name)
                continue
            kept = _my_notes(path)
            if kept:
                content = content + "\n" + kept
        path.write_text(content, encoding="utf-8")
        report["written"].append(name)
    for path in sorted(out_dir.glob("*.md")):
        if path.name not in files and _is_ours(path):
            if prune and not _has_my_notes(path):
                path.unlink()
                report["pruned"].append(path.name)
            else:
                report["stale"].append(path.name)
    return report


def load_marks(path: Path = DB_PATH) -> dict:
    """{slug: {"status", "note"}} for the ideas `db.py mark` marked as tried or discarded.

    The export never fails because of reels.json: a missing or damaged file just means
    no marks, and the digest's own Status lines are used instead (with a warning if damaged).
    """
    if not path.exists():
        return {}
    try:
        entries = json.loads(path.read_text("utf-8-sig")).get("entries") or {}
    except (OSError, ValueError, AttributeError) as e:
        print(f"Could not read the marks in {path} ({e}); using the digest's Status lines.",
              file=sys.stderr)
        return {}
    marks = {}
    for slug, e in entries.items() if isinstance(entries, dict) else ():
        if isinstance(e, dict) and e.get("status") in ("tried", "discarded"):
            note = e.get("note")
            marks[slug] = {"status": e["status"], "note": note if isinstance(note, str) and note else None}
    return marks


def load_reel_stats(path: Path = DB_PATH) -> dict:
    """{slug: {"reels": n, "last_saved": "YYYY-MM-DD" or None}} from the reels in reels.json.

    Like load_marks it never fails: no file or a damaged one just means no stats
    (load_marks already warns about a damaged file).
    """
    try:
        reels = json.loads(path.read_text("utf-8-sig")).get("reels") or {}
    except (OSError, ValueError, AttributeError):
        return {}
    stats = {}
    for r in reels.values() if isinstance(reels, dict) else ():
        slug = r.get("entry") if isinstance(r, dict) else None
        if not isinstance(slug, str) or not slug:
            continue
        st = stats.setdefault(slug, {"reels": 0, "newest": 0})
        st["reels"] += 1
        try:
            ts = int(r.get("saved_at") or r.get("added_at") or 0)
        except (TypeError, ValueError):
            ts = 0
        st["newest"] = max(st["newest"], ts)
    return {slug: {"reels": st["reels"],
                   "last_saved": (datetime.fromtimestamp(st["newest"], timezone.utc).date().isoformat()
                                  if st["newest"] > 0 else None)}
            for slug, st in stats.items()}


def resolve_status(idea: dict, marks: dict | None) -> tuple[str, str | None]:
    """(status, note): the reels.json mark wins over what the digest text says."""
    mark = (marks or {}).get(idea["slug"])
    if mark:
        return mark["status"], mark["note"]
    return idea_status(idea["body"]), None


def to_json(digest_text: str, marks: dict | None = None, stats: dict | None = None) -> dict:
    """The digest as plain data, for exporters that are not files (e.g. Notion via a connector).

    Every idea has `reels` (how many reels in reels.json back it, 0 if none) and
    `last_saved` (YYYY-MM-DD of the newest one, or null), like the Obsidian notes.
    Unlike `sources` they also count reels saved after the entry was written.
    """
    digest = parse_digest(digest_text)
    if not digest["ideas"]:
        raise ValueError("no ideas found: expected '### Idea title {#slug}' entries under '## Category'")
    ideas = []
    for i in digest["ideas"]:
        status, note = resolve_status(i, marks)
        st = (stats or {}).get(i["slug"]) or {}
        ideas.append({"title": i["title"], "slug": i["slug"], "category": i["category"],
                      "status": status, "note": note,
                      "reels": st.get("reels", 0), "last_saved": st.get("last_saved"),
                      "sources": list(dict.fromkeys(URL_RE.findall(i["body"]))),
                      "body": i["body"]})
    return {"title": digest["title"], "date": digest["date"], "top": digest["top"],
            "categories": list(dict.fromkeys(i["category"] for i in ideas)), "ideas": ideas}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--vault", help="Obsidian vault folder (any folder works)")
    mode.add_argument("--json", action="store_true", help="print the digest as JSON, write nothing")
    ap.add_argument("--folder", default="Saved reels", help="subfolder inside the vault")
    ap.add_argument("--digest", default=str(HOME / "digest.md"), help="digest to export")
    ap.add_argument("--prune", action="store_true",
                    help="delete notes this script made for ideas no longer in the digest "
                         "(notes with text under '## My notes' are kept)")
    args = ap.parse_args(argv)
    src = Path(args.digest).expanduser()
    if not src.exists():
        sys.exit(f"Not found: {src}. Write the digest first (step 5).")
    if args.json:
        try:
            data = to_json(src.read_text("utf-8"), load_marks(), load_reel_stats())
        except ValueError as e:
            sys.exit(f"Could not export {src}: {e}")
        print(json.dumps(data, ensure_ascii=False, indent=1))
        return 0
    out_dir = Path(args.vault).expanduser() / args.folder
    try:
        report = export(src.read_text("utf-8"), out_dir, marks=load_marks(), prune=args.prune,
                        stats=load_reel_stats())
    except ValueError as e:
        sys.exit(f"Could not export {src}: {e}")
    print(f"Wrote {len(report['written'])} notes to {out_dir} (open INDEX.md).")
    if report["skipped"]:
        print("Skipped (exists and was not created by this tool): " + ", ".join(report["skipped"]))
    if report["pruned"]:
        print("Deleted, no longer in the digest: " + ", ".join(report["pruned"]))
    if report["stale"] and args.prune:
        print("No longer in the digest but kept, they have text under '## My notes': "
              + ", ".join(report["stale"]))
    elif report["stale"]:
        print("No longer in the digest (left untouched; --prune deletes them): "
              + ", ".join(report["stale"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
