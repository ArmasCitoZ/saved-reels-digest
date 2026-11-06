"""Save dates in `dump` and the `recent` command behind the "Saved this week" section."""
import sys
from pathlib import Path

from test_db import make_db, reel, run

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills" / "digest" / "scripts"))
from export_digest import parse_digest  # noqa: E402

NOW = 1762400000          # 2025-11-06 03:33 UTC
DAY = 86400


def test_dump_shows_save_date_from_export_or_collection_time(tmp_path):
    make_db(tmp_path, reel("AAAAA1", relevant=True, saved_at=NOW),
            reel("BBBBB2", relevant=True))  # live/urls source: only added_at
    out = run(tmp_path, "dump")
    blocks = out.split("### ")[1:]
    assert "SAVED: 2025-11-06" in blocks[0]
    assert "SAVED: 2025-10-27" in blocks[1]  # reel() sets added_at=1761600000


def test_recent_lists_only_relevant_reels_inside_the_window(tmp_path):
    make_db(tmp_path,
            reel("NEW001", relevant=True, saved_at=NOW - 1 * DAY, entry="subagents", author="ana"),
            reel("NEW002", relevant=True, saved_at=NOW - 2 * DAY),
            reel("OFFTOP", relevant=False, saved_at=NOW - 1 * DAY),
            reel("OLD001", relevant=True, saved_at=NOW - 30 * DAY, entry="old-idea"))
    out = run(tmp_path, "recent", "--now", str(NOW))
    assert "2 relevant reels saved in the last 7 days (1 digest entries)" in out
    lines = out.splitlines()[1:]
    assert "NEW001 @ana -> subagents" in lines[0]  # newest first
    assert "NEW002" in lines[1] and "(not in digest yet)" in lines[1]
    assert "OFFTOP" not in out and "OLD001" not in out
    assert "OLD001" in run(tmp_path, "recent", "--days", "40", "--now", str(NOW))


def test_recent_when_nothing_new(tmp_path):
    make_db(tmp_path, reel("OLD001", relevant=True, saved_at=NOW - 30 * DAY))
    assert "No relevant reels saved in the last 7 days" in run(tmp_path, "recent", "--now", str(NOW))


def test_obsidian_export_ignores_saved_this_week_section():
    text = """# IA: my saved reels digest
_Updated 2025-11-06 · 10 saved · 4 on topic · 2 unique ideas after merging_

## Do these first
1. **Subagents** → [entry](#subagents)

## Saved this week
- **Subagents** → [entry](#subagents) · 1 more reel

## Claude Code
### Subagents {#subagents}
Run tasks in parallel.
**Seen in 2 reels** (saved 2025-10-01 → 2025-11-05): [@ana](https://www.instagram.com/reel/A/)
"""
    d = parse_digest(text)
    assert [i["slug"] for i in d["ideas"]] == ["subagents"]
    assert d["ideas"][0]["category"] == "Claude Code"
    assert "saved 2025-10-01" in d["ideas"][0]["body"]
