"""db.py ideas: every idea the database knows, to reuse slugs while merging."""
from test_db import make_db, reel, run, run_failing


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


def test_ideas_can_list_one_status(tmp_path):
    make_db(tmp_path, reel("AAAAA1", entry="hooks"), reel("BBBBB2", entry="subagents"),
            reel("CCCCC3", entry="mcp"))
    run(tmp_path, "mark", "tried", "subagents")
    run(tmp_path, "mark", "discarded", "mcp", "--note", "too much setup")
    assert [r[0] for r in rows(run(tmp_path, "ideas", "--status", "todo"))] == ["hooks"]
    assert [r[0] for r in rows(run(tmp_path, "ideas", "--status", "tried"))] == ["subagents"]
    out = run(tmp_path, "ideas", "--status", "discarded")
    assert out.startswith("1 discarded ideas") and [r[0] for r in rows(out)] == ["mcp"]


def test_ideas_status_with_no_match(tmp_path):
    make_db(tmp_path, reel("AAAAA1", entry="hooks"))
    assert "None of the 1 ideas is tried." in run(tmp_path, "ideas", "--status", "tried")


def test_ideas_can_list_one_collection(tmp_path):
    make_db(tmp_path, reel("AAAAA1", entry="hooks", collection="IA"),
            reel("BBBBB2", entry="hooks", collection="Cocina"),
            reel("CCCCC3", entry="hooks", collection="IA"),
            reel("DDDDD4", entry="pasta", collection="Cocina"),
            reel("EEEEE5", entry="subagents", collection="IA"))
    out = run(tmp_path, "ideas", "--collection", "ia")
    assert out.startswith("2 ideas with reels from 'ia'")
    # only the reels saved in that collection are counted
    assert [r[:2] for r in rows(out)] == [["hooks", "2"], ["subagents", "1"]]
    run(tmp_path, "mark", "tried", "pasta")
    assert [r[0] for r in rows(run(tmp_path, "ideas", "--collection", "Cocina", "--status", "tried"))] \
        == ["pasta"]


def test_ideas_collection_without_merged_reels(tmp_path):
    make_db(tmp_path, reel("AAAAA1", entry="hooks", collection="IA"), reel("BBBBB2", collection="Cocina"))
    out = run(tmp_path, "ideas", "--collection", "Cocina")
    assert "No idea has reels from collection 'Cocina' yet." in out


def test_ideas_unknown_collection_suggests_the_closest(tmp_path):
    make_db(tmp_path, reel("AAAAA1", entry="hooks", collection="Ideas de IA"))
    err = run_failing(tmp_path, "ideas", "--collection", "Ideas IA")
    assert 'Did you mean --collection "Ideas de IA"' in err
