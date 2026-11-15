"""db.py ideas: every idea the database knows, to reuse slugs while merging."""
from test_db import make_db, reel, run


def rows(out):
    return [line.split() for line in out.splitlines()[1:]]


def test_ideas_lists_reel_counts_newest_save_and_mark(tmp_path):
    make_db(tmp_path, reel("AAAAA1", relevant=True, entry="hooks", saved_at=1761600000),
            reel("BBBBB2", relevant=True, entry="hooks", saved_at=1762000000),
            reel("CCCCC3", relevant=True, entry="subagents", saved_at=1761000000),
            reel("DDDDD4", relevant=True), reel("EEEEE5", relevant=False))
    run(tmp_path, "mark", "tried", "subagents")
    out = run(tmp_path, "ideas")
    assert out.startswith("2 ideas")
    # most reels first, then by slug; the newest saved reel gives the date
    assert rows(out) == [["hooks", "2", "2025-11-01", "todo"],
                         ["subagents", "1", "2025-10-20", "tried"]]


def test_ideas_ties_are_sorted_by_slug_and_unknown_dates_shown(tmp_path):
    make_db(tmp_path, reel("AAAAA1", entry="zeta", added_at=None),
            reel("BBBBB2", entry="alfa", added_at=None))
    assert rows(run(tmp_path, "ideas")) == [["alfa", "1", "?", "todo"], ["zeta", "1", "?", "todo"]]


def test_ideas_when_nothing_is_merged_yet(tmp_path):
    make_db(tmp_path, reel("AAAAA1", relevant=True))
    assert "No ideas yet" in run(tmp_path, "ideas")
