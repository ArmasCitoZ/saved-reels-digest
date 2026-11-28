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


def _mark_at(home, slug, status, when, note=None):
    import json
    db = json.loads((home / "reels.json").read_text(encoding="utf-8"))
    mark = {"status": status, "updated": when}
    if note:
        mark["note"] = note
    db.setdefault("entries", {})[slug] = mark
    (home / "reels.json").write_text(json.dumps(db), encoding="utf-8")


def test_ideas_since_mark_lists_only_reels_saved_after_the_mark(tmp_path):
    marked = 1762000000
    make_db(tmp_path, reel("AAAAA1", entry="hooks", saved_at=marked - 86400),
            reel("BBBBB2", entry="hooks", saved_at=marked + 86400),
            reel("CCCCC3", entry="hooks", saved_at=marked + 2 * 86400),
            reel("DDDDD4", entry="hooks", added_at=None))  # no date: never new
    _mark_at(tmp_path, "hooks", "discarded", marked, "too slow")
    out = run(tmp_path, "ideas", "hooks", "--since-mark").splitlines()
    assert out[0] == "hooks: 4 reels, discarded (too slow); 2 saved since it was marked on 2025-11-01"
    assert [line.split()[1] for line in out[1:]] == ["CCCCC3", "BBBBB2"]
    # the count matches the +N new of db.py marks
    assert "+2 new" in run(tmp_path, "marks")


def test_ideas_since_mark_with_nothing_new_or_no_mark(tmp_path):
    make_db(tmp_path, reel("AAAAA1", entry="hooks", saved_at=1761000000),
            reel("BBBBB2", entry="subagents", saved_at=1761000000))
    _mark_at(tmp_path, "hooks", "tried", 1762000000)
    out = run(tmp_path, "ideas", "hooks", "subagents", "--since-mark").splitlines()
    assert out[0].endswith("; 0 saved since it was marked on 2025-11-01")
    assert out[1].startswith("subagents: 1 reels, todo; not marked")
    assert "db.py ideas subagents lists them all" in out[1]
    assert len(out) == 2


def test_ideas_since_mark_needs_slugs(tmp_path):
    make_db(tmp_path, reel("AAAAA1", entry="hooks"))
    assert "db.py marks --new" in run_failing(tmp_path, "ideas", "--since-mark")


def test_ideas_list_shows_new_reels_since_the_mark(tmp_path):
    marked = 1762000000
    make_db(tmp_path, reel("AAAAA1", entry="hooks", saved_at=marked - 86400),
            reel("BBBBB2", entry="hooks", saved_at=marked + 86400),
            reel("CCCCC3", entry="hooks", saved_at=marked + 2 * 86400),
            reel("DDDDD4", entry="subagents", saved_at=marked - 86400),
            reel("EEEEE5", entry="mcp", saved_at=marked + 86400))
    _mark_at(tmp_path, "hooks", "tried", marked)
    _mark_at(tmp_path, "subagents", "discarded", marked)
    out = run(tmp_path, "ideas").splitlines()
    # same count as db.py marks; nothing new on subagents and no +N on an unmarked idea
    assert out[1].split() == ["hooks", "3", "2025-11-03", "tried", "+2", "new"]
    assert out[2].split() == ["mcp", "1", "2025-11-02", "todo"]
    assert out[3].split() == ["subagents", "1", "2025-10-31", "discarded"]
    assert out[4].startswith("+N new: reels saved after the idea was marked")
    assert "+2 new" in run(tmp_path, "marks")


def test_ideas_list_has_no_footer_without_new_reels(tmp_path):
    make_db(tmp_path, reel("AAAAA1", entry="hooks", saved_at=1761000000))
    _mark_at(tmp_path, "hooks", "tried", 1762000000)
    out = run(tmp_path, "ideas")
    assert "+" not in out and len(out.splitlines()) == 2


def test_ideas_min_reels_keeps_the_ideas_saved_most(tmp_path):
    make_db(tmp_path, reel("AAAAA1", entry="hooks", collection="IA"),
            reel("BBBBB2", entry="hooks", collection="IA"),
            reel("CCCCC3", entry="hooks", collection="Cocina"),
            reel("DDDDD4", entry="subagents", collection="IA"),
            reel("EEEEE5", entry="subagents", collection="IA"),
            reel("FFFFF6", entry="mcp", collection="IA"))
    run(tmp_path, "mark", "tried", "subagents")
    out = run(tmp_path, "ideas", "--min-reels", "2")
    assert out.startswith("2 ideas with 2+ reels")
    assert [r[:2] for r in rows(out)] == [["hooks", "3"], ["subagents", "2"]]
    assert [r[0] for r in rows(run(tmp_path, "ideas", "--min-reels", "2", "--status", "todo"))] \
        == ["hooks"]
    # with --collection only the reels from it count: hooks has 2 in IA, so 3 leaves nothing
    assert [r[0] for r in rows(run(tmp_path, "ideas", "--min-reels", "2", "--collection", "IA",
                                   "--sort", "name"))] == ["hooks", "subagents"]
    assert "None of the 3 ideas has 3 or more reels." in \
        run(tmp_path, "ideas", "--min-reels", "3", "--collection", "IA")


def test_ideas_min_reels_with_older_than(tmp_path):
    now = 1762000000
    make_db(tmp_path, reel("AAAAA1", entry="hooks", saved_at=now - 60 * 86400),
            reel("BBBBB2", entry="hooks", saved_at=now - 50 * 86400),
            reel("CCCCC3", entry="mcp", saved_at=now - 60 * 86400))
    out = run(tmp_path, "ideas", "--min-reels", "2", "--older-than", "30", "--now", str(now))
    assert out.startswith("1 ideas with 2+ reels and no reel saved in the last 30 days")
    assert [r[0] for r in rows(out)] == ["hooks"]


def test_ideas_min_reels_needs_a_positive_number_and_no_slugs(tmp_path):
    make_db(tmp_path, reel("AAAAA1", entry="hooks"))
    assert "1 or more" in run_failing(tmp_path, "ideas", "--min-reels", "0")
    assert "--min-reels filters the list" in run_failing(tmp_path, "ideas", "hooks", "--min-reels", "2")


def test_ideas_newer_than_keeps_what_you_are_saving_now(tmp_path):
    now = 1762000000
    make_db(tmp_path, reel("AAAAA1", entry="hooks", saved_at=now - 60 * 86400),
            reel("BBBBB2", entry="hooks", saved_at=now - 2 * 86400),
            reel("CCCCC3", entry="mcp", saved_at=now - 3 * 86400),
            reel("DDDDD4", entry="subagents", saved_at=now - 40 * 86400),
            reel("EEEEE5", entry="nodate", added_at=None))
    out = run(tmp_path, "ideas", "--newer-than", "7", "--now", str(now))
    assert out.startswith("2 ideas with a reel saved in the last 7 days")
    # one recent reel is enough; an idea with no known date never counts as recent
    assert [r[:2] for r in rows(out)] == [["hooks", "2"], ["mcp", "1"]]
    run(tmp_path, "mark", "tried", "mcp")
    assert [r[0] for r in rows(run(tmp_path, "ideas", "--newer-than", "7", "--status", "todo",
                                   "--now", str(now)))] == ["hooks"]
    out = run(tmp_path, "ideas", "--newer-than", "7", "--min-reels", "2", "--now", str(now))
    assert out.startswith("1 ideas with 2+ reels and a reel saved in the last 7 days")
    assert "None of the 4 ideas has a reel saved in the last 1 days." in \
        run(tmp_path, "ideas", "--newer-than", "1", "--now", str(now))


def test_ideas_newer_than_with_collection_counts_only_its_reels(tmp_path):
    now = 1762000000
    make_db(tmp_path, reel("AAAAA1", entry="hooks", collection="IA", saved_at=now - 50 * 86400),
            reel("BBBBB2", entry="hooks", collection="Cocina", saved_at=now - 86400))
    assert "None of the 1 ideas" in run(tmp_path, "ideas", "--newer-than", "7", "--collection", "IA",
                                        "--now", str(now))


def test_ideas_newer_than_is_checked(tmp_path):
    make_db(tmp_path, reel("AAAAA1", entry="hooks"))
    assert "opposite" in run_failing(tmp_path, "ideas", "--newer-than", "7", "--older-than", "30")
    assert "1 or more" in run_failing(tmp_path, "ideas", "--newer-than", "0")
    assert "--newer-than filters the list" in run_failing(tmp_path, "ideas", "hooks", "--newer-than", "7")


def test_ideas_limit_shows_the_first_ones_and_says_how_many_are_left(tmp_path):
    make_db(tmp_path, reel("AAAAA1", entry="hooks"), reel("BBBBB2", entry="hooks"),
            reel("CCCCC3", entry="hooks"), reel("DDDDD4", entry="mcp"), reel("EEEEE5", entry="mcp"),
            reel("FFFFF6", entry="subagents"), reel("GGGGG7", entry="alfa"))
    out = run(tmp_path, "ideas", "--limit", "2")
    lines = out.splitlines()
    assert lines[0].startswith("Top 2 of 4 ideas")
    # the limit applies after sorting: the ideas with most reels stay
    assert [line.split()[0] for line in lines[1:3]] == ["hooks", "mcp"]
    assert lines[3].startswith("... and 2 more")
    # with --sort name the first two by slug stay instead
    assert [r[0] for r in rows(run(tmp_path, "ideas", "--limit", "2", "--sort", "name"))[:2]] \
        == ["alfa", "hooks"]
    # and after filtering: only one todo idea with 2+ reels left once hooks is tried
    run(tmp_path, "mark", "tried", "hooks")
    out = run(tmp_path, "ideas", "--status", "todo", "--min-reels", "2", "--limit", "5")
    assert out.startswith("1 todo ideas with 2+ reels") and "more" not in out


def test_ideas_limit_equal_to_the_list_prints_everything(tmp_path):
    make_db(tmp_path, reel("AAAAA1", entry="hooks"), reel("BBBBB2", entry="mcp"))
    out = run(tmp_path, "ideas", "--limit", "2")
    assert out.startswith("2 ideas") and len(out.splitlines()) == 3


def test_ideas_limit_is_checked(tmp_path):
    make_db(tmp_path, reel("AAAAA1", entry="hooks"))
    assert "1 or more" in run_failing(tmp_path, "ideas", "--limit", "0")
    assert "--limit filters the list" in run_failing(tmp_path, "ideas", "hooks", "--limit", "3")


def test_ideas_json_has_the_same_rows_filters_and_order(tmp_path):
    import json

    marked = 1761500000
    make_db(tmp_path, reel("AAAAA1", relevant=True, entry="hooks", saved_at=1761600000),
            reel("BBBBB2", relevant=True, entry="hooks", saved_at=1762000000),
            reel("CCCCC3", relevant=True, entry="subagents", saved_at=1761000000),
            reel("DDDDD4", relevant=True, entry="mcp", added_at=None))
    db = json.loads((tmp_path / "reels.json").read_text(encoding="utf-8"))
    db["entries"] = {"hooks": {"status": "tried", "updated": marked, "note": "útil"}}
    (tmp_path / "reels.json").write_text(json.dumps(db), encoding="utf-8")
    out = json.loads(run(tmp_path, "ideas", "--json"))
    assert out["total"] == 3
    assert out["ideas"] == [
        {"slug": "hooks", "reels": 2, "last_saved": "2025-11-01", "status": "tried",
         "note": "útil", "new_since_mark": 2},
        {"slug": "mcp", "reels": 1, "last_saved": None, "status": "todo",
         "note": None, "new_since_mark": None},
        {"slug": "subagents", "reels": 1, "last_saved": "2025-10-20", "status": "todo",
         "note": None, "new_since_mark": None}]
    # filters, sort and --limit apply as in the text list; total counts before the limit
    out = json.loads(run(tmp_path, "ideas", "--json", "--status", "todo", "--sort", "name",
                         "--limit", "1"))
    assert out["total"] == 2 and [i["slug"] for i in out["ideas"]] == ["mcp"]
    # nothing matching is still valid JSON
    assert json.loads(run(tmp_path, "ideas", "--json", "--min-reels", "5")) == {"total": 0, "ideas": []}


def test_ideas_json_with_no_ideas_and_with_slugs(tmp_path):
    import json

    make_db(tmp_path, reel("AAAAA1", relevant=True))
    assert json.loads(run(tmp_path, "ideas", "--json")) == {"total": 0, "ideas": []}
    make_db(tmp_path, reel("AAAAA1", relevant=True, entry="hooks"))
    assert "--json prints the list of ideas" in run_failing(tmp_path, "ideas", "hooks", "--json")
