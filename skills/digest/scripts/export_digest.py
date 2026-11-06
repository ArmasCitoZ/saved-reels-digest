"""Export digest.md to an Obsidian vault: one note per idea plus an index note.

  export_digest.py --vault ~/Obsidian/MyVault [--folder "Saved reels"] [--digest PATH]

Reads the digest written in step 5 (default: WORK/digest.md) and writes into
VAULT/FOLDER:

  INDEX.md          map of content: "Do these first" and every idea by category
  <Idea title>.md   one note per idea, with frontmatter (title, date, tags,
                    aliases, sources) and links to the other ideas of its category

Links are relative markdown links, so the notes also render on GitHub and in
VS Code. Safe to re-run: notes are rewritten from the digest, but anything you
write under a "## My notes" heading in a note is kept. Files in the folder that
this script did not create are never overwritten.
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import HOME  # noqa: E402

MARKER = "saved-reels-digest"  # frontmatter `generator:` value identifying our notes
MY_NOTES = "## My notes"
FIRST_SECTION = "Do these first"
ENTRY_RE = re.compile(r"^###\s+(?P<title>.+?)\s*(?:\{#(?P<slug>[A-Za-z0-9_-]+)\})?\s*$")
DATE_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")
ANCHOR_LINK_RE = re.compile(r"\]\(#([A-Za-z0-9_-]+)\)")
URL_RE = re.compile(r"\]\((https?://[^)\s]+)\)")


def slugify(text: str) -> str:
    s = re.sub(r"[^\w\s-]", "", text.lower(), flags=re.UNICODE)
    return re.sub(r"[\s_]+", "-", s).strip("-") or "idea"


def parse_digest(text: str) -> dict:
    """Split digest.md into title, update date, the top list and ideas by category."""
    out = {"title": "Saved reels digest", "date": None, "top": [], "ideas": []}
    section = None
    idea = None
    for line in text.splitlines():
        if line.startswith("# ") and not out["ideas"] and section is None:
            out["title"] = line[2:].strip()
            continue
        if line.startswith("## "):
            section = line[3:].strip()
            idea = None
            continue
        m = ENTRY_RE.match(line)
        if m and section and section != FIRST_SECTION:
            idea = {"title": m["title"], "slug": m["slug"] or slugify(m["title"]),
                    "category": section, "body": []}
            out["ideas"].append(idea)
            continue
        if section is None and out["date"] is None and DATE_RE.search(line):
            out["date"] = DATE_RE.search(line).group(1)
        elif section == FIRST_SECTION and re.match(r"^\s*\d+\.\s", line):
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


def assign_filenames(ideas: list) -> None:
    used = set()
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
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def rewrite_anchors(text: str, by_slug: dict) -> str:
    """`[x](#slug)` inside the digest becomes a link to that idea's note."""
    def repl(m):
        target = by_slug.get(m.group(1))
        return f"]({quote(target['file'])})" if target else m.group(0)
    return ANCHOR_LINK_RE.sub(repl, text)


def render_note(idea: dict, ideas: list, by_slug: dict, day: str, index_name: str) -> str:
    sources = list(dict.fromkeys(URL_RE.findall(idea["body"])))
    tags = ["saved-reels", slugify(idea["category"])]
    fm = ["---", f"title: {_yaml_str(idea['title'])}", f"date: {day}",
          f"tags: [{', '.join(tags)}]", f"aliases: [{idea['slug']}]",
          f"category: {_yaml_str(idea['category'])}", f"generator: {MARKER}"]
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


def render_index(digest: dict, by_slug: dict, day: str) -> str:
    lines = ["---", f"title: {_yaml_str(digest['title'])}", f"date: {day}",
             "tags: [saved-reels]", f"generator: {MARKER}", "---", "",
             f"# {digest['title']}", "",
             f"_Exported from digest.md on {day} · {len(digest['ideas'])} ideas_", ""]
    if digest["top"]:
        lines += [f"## {FIRST_SECTION}", ""]
        lines += [f"{n}. {rewrite_anchors(t, by_slug)}" for n, t in enumerate(digest["top"], 1)]
        lines.append("")
    categories = list(dict.fromkeys(i["category"] for i in digest["ideas"]))
    for cat in categories:
        lines += [f"## {cat}", ""]
        lines += [f"- {link(i['title'], i['file'])}" for i in digest["ideas"] if i["category"] == cat]
        lines.append("")
    return "\n".join(lines)


def _is_ours(path: Path) -> bool:
    head = path.read_text("utf-8", "replace")[:2000]
    return head.startswith("---") and f"generator: {MARKER}" in head.split("\n---", 1)[0]


def _my_notes(path: Path) -> str:
    text = path.read_text("utf-8", "replace")
    idx = text.find(f"\n{MY_NOTES}")
    return text[idx + 1:].rstrip() + "\n" if idx >= 0 else ""


def export(digest_text: str, out_dir: Path, today: str | None = None) -> dict:
    digest = parse_digest(digest_text)
    if not digest["ideas"]:
        raise ValueError("no ideas found: expected '### Idea title {#slug}' entries under '## Category'")
    day = digest["date"] or today or date.today().isoformat()
    assign_filenames(digest["ideas"])
    by_slug = {i["slug"]: i for i in digest["ideas"]}
    out_dir.mkdir(parents=True, exist_ok=True)
    report = {"written": [], "skipped": [], "stale": []}
    files = {"INDEX.md": render_index(digest, by_slug, day)}
    for i in digest["ideas"]:
        files[i["file"]] = render_note(i, digest["ideas"], by_slug, day, "INDEX.md")
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
            report["stale"].append(path.name)
    return report


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--vault", required=True, help="Obsidian vault folder (any folder works)")
    ap.add_argument("--folder", default="Saved reels", help="subfolder inside the vault")
    ap.add_argument("--digest", default=str(HOME / "digest.md"), help="digest to export")
    args = ap.parse_args(argv)
    src = Path(args.digest).expanduser()
    if not src.exists():
        sys.exit(f"Not found: {src}. Write the digest first (step 5).")
    out_dir = Path(args.vault).expanduser() / args.folder
    try:
        report = export(src.read_text("utf-8"), out_dir)
    except ValueError as e:
        sys.exit(f"Could not export {src}: {e}")
    print(f"Wrote {len(report['written'])} notes to {out_dir} (open INDEX.md).")
    if report["skipped"]:
        print("Skipped (exists and was not created by this tool): " + ", ".join(report["skipped"]))
    if report["stale"]:
        print("No longer in the digest (left untouched, delete if you want): "
              + ", ".join(report["stale"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
