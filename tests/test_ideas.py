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


def test_ideas_slug_lists_its_reels_newest_first(tmp_path):
    make_db(tmp_path, reel("AAAAA1", entry="hooks", author="ana", saved_at=1761000000),
            reel("BBBBB2", entry="hooks", author="leo", saved_at=1762000000),
            reel("CCCCC3", entry="subagents"))
    run(tmp_path, "mark", "discarded", "hooks", "--note", "too slow")
    out = run(tmp_path, "ideas", "hooks").splitlines()
    assert out[0] == "hooks: 2 reels, discarded (too slow)"
    assert out[1].split() == ["2025-11-01", "BBBBB2", "@leo", "https://www.instagram.com/reel/BBBBB2/"]
    assert out[2].split()[:3] == ["2025-10-20", "AAAAA1", "@ana"]
    assert len(out) == 3


def test_ideas_slug_with_a_typo_suggests_the_closest(tmp_path):
    make_db(tmp_path, reel("AAAAA1", entry="subagents"))
    assert "Did you mean: subagents?" in run_failing(tmp_path, "ideas", "subagent")
    out = run(tmp_path, "ideas", "subagents", "subagent")
    assert out.startswith("subagents: 1 reels, todo")
    assert "Skipped, no reel points to: subagent (typo?). Did you mean: subagents?" in out


def test_ideas_slug_respects_the_collection(tmp_path):
    make_db(tmp_path, reel("AAAAA1", entry="hooks", collection="IA"),
            reel("BBBBB2", entry="hooks", collection="Cocina"))
    out = run(tmp_path, "ideas", "hooks", "--collection", "IA")
    assert out.startswith("hooks: 1 reels") and "AAAAA1" in out and "BBBBB2" not in out


def test_ideas_can_be_sorted_by_newest_save_or_by_name(tmp_path):
    make_db(tmp_path, reel("AAAAA1", entry="hooks", saved_at=1761600000),
            reel("BBBBB2", entry="hooks", saved_at=1761000000),
            reel("CCCCC3", entry="subagents", saved_at=1762000000),
            reel("DDDDD4", entry="alfa", added_at=None),
            reel("EEEEE5", entry="mcp", saved_at=1762000000))
    def order(*extra):
        return [r[0] for r in rows(run(tmp_path, "ideas", *extra))]

    assert order() == ["hooks", "alfa", "mcp", "subagents"]
    assert order("--sort", "reels") == order()
    # newest saved reel first, ties by slug, ideas with no known date last
    assert order("--sort", "recent") == ["mcp", "subagents", "hooks", "alfa"]
    assert order("--sort", "name") == ["alfa", "hooks", "mcp", "subagents"]


def test_ideas_sort_combines_with_status(tmp_path):
    make_db(tmp_path, reel("AAAAA1", entry="zeta", saved_at=1762000000),
            reel("BBBBB2", entry="beta", saved_at=1761000000),
            reel("CCCCC3", entry="gamma", saved_at=1761500000))
    run(tmp_path, "mark", "tried", "gamma")
    assert [r[0] for r in rows(run(tmp_path, "ideas", "--status", "todo", "--sort", "recent"))] \
        == ["zeta", "beta"]


DAY = 86400
NOW = 1762000000


def test_ideas_older_than_lists_ideas_with_no_recent_reel(tmp_path):
    make_db(tmp_path, reel("AAAAA1", entry="hooks", saved_at=NOW - 100 * DAY),
            reel("BBBBB2", entry="hooks", saved_at=NOW - 2 * DAY),  # a new reel keeps it fresh
            reel("CCCCC3", entry="subagents", saved_at=NOW - 45 * DAY),
            reel("DDDDD4", entry="mcp", saved_at=NOW - 90 * DAY),
            reel("EEEEE5", entry="alfa", added_at=None))  # no known date: not listed
    run(tmp_path, "mark", "tried", "mcp")
    out = run(tmp_path, "ideas", "--older-than", "30", "--now", str(NOW), "--sort", "recent")
    assert out.startswith("2 ideas with no reel saved in the last 30 days")
    assert [r[0] for r in rows(out)] == ["subagents", "mcp"]
    out = run(tmp_path, "ideas", "--older-than", "30", "--status", "todo", "--now", str(NOW))
    assert out.startswith("1 todo ideas with no reel saved in the last 30 days")
    assert [r[0] for r in rows(out)] == ["subagents"]


def test_ideas_older_than_with_no_match(tmp_path):
    make_db(tmp_path, reel("AAAAA1", entry="hooks", saved_at=NOW - DAY))
    out = run(tmp_path, "ideas", "--older-than", "30", "--now", str(NOW))
    assert "None of the 1 ideas has gone 30 days without a new reel." in out
    out = run(tmp_path, "ideas", "--older-than", "30", "--status", "tried", "--now", str(NOW))
    assert "None of the 1 ideas is tried and has gone 30 days without a new reel." in out


def test_ideas_older_than_needs_the_list(tmp_path):
    make_db(tmp_path, reel("AAAAA1", entry="hooks"))
    assert "leave out the slugs" in run_failing(tmp_path, "ideas", "hooks", "--older-than", "30")
