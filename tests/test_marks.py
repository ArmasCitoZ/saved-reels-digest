"""Marking digest ideas as tried / discarded (db.py mark / marks)."""
import json

import os
import subprocess
import sys

from test_db import SCRIPTS, make_db, reel, run


def run_failing(home, *args):
    env = {**os.environ, "SRD_HOME": str(home), "PYTHONIOENCODING": "utf-8"}
    r = subprocess.run([sys.executable, str(SCRIPTS / "db.py"), *args], env=env,
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode != 0
    return r.stderr


def entries(home):
    return json.loads((home / "reels.json").read_text(encoding="utf-8")).get("entries", {})


def test_mark_records_status_and_note_and_keeps_reels(tmp_path):
    make_db(tmp_path, reel("AAAAA1", relevant=True, entry="subagents"),
            reel("BBBBB2", relevant=True, entry="mcp-servers"))
    out = run(tmp_path, "mark", "tried", "subagents", "--note", "worked for refactors")
    assert "Marked 1 entries as tried." in out and "typo" not in out
    run(tmp_path, "mark", "discarded", "mcp-servers")
    e = entries(tmp_path)
    assert e["subagents"]["status"] == "tried" and e["subagents"]["note"] == "worked for refactors"
    assert e["mcp-servers"]["status"] == "discarded" and "note" not in e["mcp-servers"]
    listing = run(tmp_path, "marks")
    assert "tried" in listing and "subagents" in listing and "worked for refactors" in listing
    assert listing.index("discarded") < listing.index("tried")  # grouped by status
    # reels themselves are untouched, so new reels still merge into the same entry
    assert '"entry": "subagents"' in run(tmp_path, "show", "AAAAA1")


def test_mark_todo_clears_and_unknown_slug_is_skipped(tmp_path):
    make_db(tmp_path, reel("AAAAA1", relevant=True, entry="subagents"))
    run(tmp_path, "mark", "tried", "subagents")
    run(tmp_path, "mark", "todo", "subagents")
    assert entries(tmp_path) == {}
    out = run(tmp_path, "mark", "discarded", "subagents", "sub-agents")
    assert "Marked 1 entries" in out and "not linked to any reel (typo?): sub-agents" in out
    assert list(entries(tmp_path)) == ["subagents"]


def test_mark_with_only_unknown_slugs_changes_nothing(tmp_path):
    make_db(tmp_path, reel("AAAAA1", relevant=True, entry="subagents"))
    r = run_failing(tmp_path, "mark", "tried", "sub-agents")
    assert "nothing was marked" in r and "sub-agents" in r and "Did you mean: subagents?" in r
    assert entries(tmp_path) == {}


def test_mark_lists_known_ideas_when_nothing_is_close(tmp_path):
    make_db(tmp_path, reel("AAAAA1", relevant=True, entry="subagents"),
            reel("BBBBB2", relevant=True, entry="mcp-servers"))
    r = run_failing(tmp_path, "mark", "tried", "prompting")
    assert "Did you mean" not in r and "Known ideas: mcp-servers, subagents" in r


def test_mark_suggests_the_closest_slug_for_each_typo(tmp_path):
    make_db(tmp_path, reel("AAAAA1", relevant=True, entry="subagents"),
            reel("BBBBB2", relevant=True, entry="mcp-servers"),
            reel("CCCCC3", relevant=True, entry="hooks"))
    out = run(tmp_path, "mark", "tried", "hooks", "Sub_Agents", "mcp-server", "prompting")
    assert "Marked 1 entries" in out
    assert "Did you mean: subagents (for Sub_Agents), mcp-servers (for mcp-server)?" in out
    assert list(entries(tmp_path)) == ["hooks"]  # a guess is never applied by itself


def test_mark_with_no_entries_yet_explains_the_order(tmp_path):
    make_db(tmp_path, reel("AAAAA1", relevant=True))
    assert "db.py set entry" in run_failing(tmp_path, "mark", "tried", "subagents")


def test_todo_clears_a_mark_whose_reels_moved_to_another_idea(tmp_path):
    make_db(tmp_path, reel("AAAAA1", relevant=True, entry="subagents"))
    run(tmp_path, "mark", "tried", "subagents")
    run(tmp_path, "set", "entry", "agents", "AAAAA1")
    run(tmp_path, "mark", "todo", "subagents")
    assert entries(tmp_path) == {}


def test_marks_when_empty(tmp_path):
    make_db(tmp_path, reel("AAAAA1"))
    assert "No ideas marked" in run(tmp_path, "marks")


def test_marks_can_list_one_status(tmp_path):
    make_db(tmp_path, reel("AAAAA1", relevant=True, entry="subagents"),
            reel("BBBBB2", relevant=True, entry="mcp-servers"))
    run(tmp_path, "mark", "tried", "subagents")
    run(tmp_path, "mark", "discarded", "mcp-servers", "--note", "too much setup")
    tried = run(tmp_path, "marks", "--status", "tried")
    assert "subagents" in tried and "mcp-servers" not in tried
    discarded = run(tmp_path, "marks", "--status", "discarded")
    assert "mcp-servers" in discarded and "too much setup" in discarded and "subagents" not in discarded
    run(tmp_path, "mark", "todo", "mcp-servers")
    assert "No ideas marked as discarded yet." in run(tmp_path, "marks", "--status", "discarded")
    assert "invalid choice" in run_failing(tmp_path, "marks", "--status", "todo")


def test_marking_again_without_note_keeps_it(tmp_path):
    make_db(tmp_path, reel("AAAAA1", relevant=True, entry="subagents"))
    run(tmp_path, "mark", "tried", "subagents", "--note", "worked for refactors")
    run(tmp_path, "mark", "discarded", "subagents")
    e = entries(tmp_path)["subagents"]
    assert e["status"] == "discarded" and e["note"] == "worked for refactors"
    run(tmp_path, "mark", "tried", "subagents", "--note", "back in use")
    assert entries(tmp_path)["subagents"]["note"] == "back in use"


def test_empty_note_clears_it(tmp_path):
    make_db(tmp_path, reel("AAAAA1", relevant=True, entry="subagents"))
    run(tmp_path, "mark", "tried", "subagents", "--note", "worked for refactors")
    run(tmp_path, "mark", "tried", "subagents", "--note", "")
    assert "note" not in entries(tmp_path)["subagents"]


def _with_marks(home, marks):
    db = json.loads((home / "reels.json").read_text(encoding="utf-8"))
    db["entries"] = marks
    (home / "reels.json").write_text(json.dumps(db), encoding="utf-8")


def test_marks_count_reels_saved_after_the_mark(tmp_path):
    marked = 1762000000
    make_db(tmp_path,
            reel("AAAAA1", relevant=True, entry="subagents", saved_at=marked - 86400),
            reel("BBBBB2", relevant=True, entry="subagents", saved_at=marked + 86400),
            reel("CCCCC3", relevant=True, entry="subagents", saved_at=marked + 2 * 86400),
            reel("DDDDD4", relevant=True, entry="hooks", saved_at=marked - 86400),
            reel("EEEEE5", relevant=True, entry="mcp-servers", saved_at=marked + 86400),
            reel("FFFFF6", relevant=True, entry="mcp-servers", added_at=None))  # no date: not new
    _with_marks(tmp_path, {"subagents": {"status": "tried", "updated": marked},
                           "hooks": {"status": "discarded", "updated": marked},
                           "mcp-servers": {"status": "discarded", "updated": marked, "note": "setup"}})
    out = run(tmp_path, "marks")
    lines = {line.split()[1]: line for line in out.splitlines() if line.startswith("  ")}
    assert "+2 new" in lines["subagents"]
    assert "+1 new" in lines["mcp-servers"] and "setup" in lines["mcp-servers"]
    assert "new" not in lines["hooks"]
    assert "Discarded but still saving reels about: mcp-servers" in out
    assert "db.py ideas mcp-servers" in out


def test_marking_again_resets_the_count(tmp_path):
    make_db(tmp_path, reel("AAAAA1", relevant=True, entry="subagents", saved_at=1762000000))
    _with_marks(tmp_path, {"subagents": {"status": "tried", "updated": 1761000000}})
    assert "+1 new" in run(tmp_path, "marks")
    assert "+N new: reels saved" in run(tmp_path, "marks")  # explained when no discarded idea is involved
    run(tmp_path, "mark", "tried", "subagents")  # now: the reel was saved before this mark
    out = run(tmp_path, "marks")
    assert "new" not in out


def test_marks_new_lists_only_ideas_with_reels_after_the_mark(tmp_path):
    marked = 1762000000
    make_db(tmp_path,
            reel("AAAAA1", relevant=True, entry="subagents", saved_at=marked + 86400),
            reel("DDDDD4", relevant=True, entry="hooks", saved_at=marked - 86400),
            reel("EEEEE5", relevant=True, entry="mcp-servers", saved_at=marked + 86400),
            reel("FFFFF6", relevant=True, entry="plan-mode", added_at=None))  # no date: never new
    _with_marks(tmp_path, {"subagents": {"status": "tried", "updated": marked},
                           "hooks": {"status": "discarded", "updated": marked},
                           "mcp-servers": {"status": "discarded", "updated": marked},
                           "plan-mode": {"status": "tried", "updated": marked}})
    out = run(tmp_path, "marks", "--new")
    listed = [line.split()[1] for line in out.splitlines() if line.startswith("  ")]
    assert listed == ["mcp-servers", "subagents"]
    assert "Discarded but still saving reels about: mcp-servers" in out
    assert ("mark the idea again to reset its +N (the note is kept):"
            " db.py mark discarded mcp-servers; db.py mark tried subagents") in out
    assert "reset" not in run(tmp_path, "marks")  # only the --new review suggests it
    tried = run(tmp_path, "marks", "--new", "--status", "tried")
    assert [line.split()[1] for line in tried.splitlines() if line.startswith("  ")] == ["subagents"]
    assert tried.rstrip().endswith("(the note is kept): db.py mark tried subagents")
    run(tmp_path, "mark", "discarded", "mcp-servers")  # the reset the hint suggests
    assert "+1 new" not in run(tmp_path, "marks").split("mcp-servers", 1)[1].split("\n", 1)[0]
    run(tmp_path, "mark", "tried", "subagents", "mcp-servers")  # marked again: nothing new since
    assert "No reels saved about any tried idea since it was marked." in run(
        tmp_path, "marks", "--new", "--status", "tried")
    assert "No reels saved about any idea since it was marked." in run(tmp_path, "marks", "--new")


def test_marks_collection_lists_only_ideas_with_reels_from_it(tmp_path):
    marked = 1762000000
    make_db(tmp_path,
            reel("AAAAA1", relevant=True, entry="subagents", collection="IA", saved_at=marked + 86400),
            reel("BBBBB2", relevant=True, entry="subagents", collection="Cocina", saved_at=marked + 86400),
            reel("CCCCC3", relevant=True, entry="hooks", collection="IA", saved_at=marked - 86400),
            reel("DDDDD4", relevant=True, entry="mcp-servers", collection="Cocina",
                 saved_at=marked + 86400),
            reel("EEEEE5", relevant=True, entry="risotto", collection="Cocina", saved_at=marked + 86400))
    _with_marks(tmp_path, {"subagents": {"status": "tried", "updated": marked},
                           "hooks": {"status": "discarded", "updated": marked},
                           "mcp-servers": {"status": "discarded", "updated": marked}})
    out = run(tmp_path, "marks", "--collection", "ia")  # case-insensitive, like the other commands
    lines = {line.split()[1]: line for line in out.splitlines() if line.startswith("  ")}
    assert sorted(lines) == ["hooks", "subagents"]  # mcp-servers only has reels from Cocina
    assert "+1 new" in lines["subagents"]  # the Cocina reel saved after the mark does not count
    assert "new" not in lines["hooks"]
    assert "+N new: reels from collection 'ia' saved" in out
    # --new: the discarded idea with new reels in Cocina only shows up there
    assert "No reels from collection 'IA' saved about any discarded idea since it was marked." in run(
        tmp_path, "marks", "--new", "--status", "discarded", "--collection", "IA")
    cocina = run(tmp_path, "marks", "--new", "--status", "discarded", "--collection", "Cocina")
    assert "Discarded but still saving reels from collection 'Cocina' about: mcp-servers." in cocina
    assert 'db.py ideas mcp-servers --collection "Cocina"' in cocina


def test_marks_collection_without_marked_ideas_in_it(tmp_path):
    make_db(tmp_path, reel("AAAAA1", relevant=True, entry="subagents", collection="IA"),
            reel("BBBBB2", relevant=True, entry="risotto", collection="Cocina"))
    _with_marks(tmp_path, {"subagents": {"status": "tried", "updated": 1762000000}})
    assert "No marked idea has reels from collection 'Cocina'." in run(
        tmp_path, "marks", "--collection", "Cocina")
    assert "No tried idea has reels from collection 'Cocina'." in run(
        tmp_path, "marks", "--status", "tried", "--collection", "Cocina")
    assert "Did you mean" in run_failing(tmp_path, "marks", "--collection", "Cocin")


def _listed(out):
    return [line.split()[1] for line in out.splitlines() if line.startswith("  ")]


def test_marks_sort_new_puts_the_most_new_reels_first(tmp_path):
    marked = 1762000000
    make_db(tmp_path,
            reel("AAAAA1", relevant=True, entry="subagents", saved_at=marked + 86400),
            reel("BBBBB2", relevant=True, entry="hooks", saved_at=marked + 86400),
            reel("CCCCC3", relevant=True, entry="hooks", saved_at=marked + 2 * 86400),
            reel("DDDDD4", relevant=True, entry="hooks", saved_at=marked + 3 * 86400),
            reel("EEEEE5", relevant=True, entry="mcp-servers", saved_at=marked - 86400),
            reel("FFFFF6", relevant=True, entry="agents-md", saved_at=marked + 86400))
    _with_marks(tmp_path, {"subagents": {"status": "tried", "updated": marked},
                           "hooks": {"status": "tried", "updated": marked},
                           "mcp-servers": {"status": "discarded", "updated": marked},
                           "agents-md": {"status": "discarded", "updated": marked}})
    # default: by status, then name
    assert _listed(run(tmp_path, "marks")) == ["agents-md", "mcp-servers", "hooks", "subagents"]
    # most +N new first, ties by name, ideas with nothing new last
    assert _listed(run(tmp_path, "marks", "--sort", "new")) == [
        "hooks", "agents-md", "subagents", "mcp-servers"]
    # it combines with --new and --status
    assert _listed(run(tmp_path, "marks", "--new", "--sort", "new")) == [
        "hooks", "agents-md", "subagents"]
    assert _listed(run(tmp_path, "marks", "--status", "tried", "--sort", "new")) == [
        "hooks", "subagents"]


def test_marks_sort_date_puts_the_oldest_mark_first(tmp_path):
    make_db(tmp_path,
            reel("AAAAA1", relevant=True, entry="subagents"),
            reel("BBBBB2", relevant=True, entry="hooks"),
            reel("CCCCC3", relevant=True, entry="mcp-servers"),
            reel("DDDDD4", relevant=True, entry="agents-md"))
    _with_marks(tmp_path, {"subagents": {"status": "tried", "updated": 1763000000},
                           "hooks": {"status": "discarded", "updated": 1761000000},
                           "mcp-servers": {"status": "tried"},  # no date: last
                           "agents-md": {"status": "tried", "updated": 1762000000}})
    assert _listed(run(tmp_path, "marks", "--sort", "date")) == [
        "hooks", "agents-md", "subagents", "mcp-servers"]


def test_marks_sort_rejects_unknown_orders(tmp_path):
    make_db(tmp_path, reel("AAAAA1", relevant=True, entry="subagents"))
    assert "invalid choice" in run_failing(tmp_path, "marks", "--sort", "reels")


def test_marks_limit_shows_the_first_n_after_sorting(tmp_path):
    marked = 1762000000
    make_db(tmp_path,
            reel("AAAAA1", relevant=True, entry="subagents", saved_at=marked + 86400),
            reel("BBBBB2", relevant=True, entry="hooks", saved_at=marked + 86400),
            reel("CCCCC3", relevant=True, entry="hooks", saved_at=marked + 2 * 86400),
            reel("DDDDD4", relevant=True, entry="mcp-servers", saved_at=marked - 86400),
            reel("EEEEE5", relevant=True, entry="agents-md", saved_at=marked + 86400))
    _with_marks(tmp_path, {"subagents": {"status": "tried", "updated": marked},
                           "hooks": {"status": "tried", "updated": marked},
                           "mcp-servers": {"status": "discarded", "updated": marked},
                           "agents-md": {"status": "discarded", "updated": marked}})
    out = run(tmp_path, "marks", "--sort", "new", "--limit", "2")
    assert _listed(out) == ["hooks", "agents-md"]
    assert "... and 2 more (raise --limit" in out
    # the hints only name the ideas that are shown
    out = run(tmp_path, "marks", "--new", "--sort", "new", "--limit", "1")
    assert _listed(out) == ["hooks"] and "... and 2 more" in out
    assert "db.py mark tried hooks" in out and "agents-md" not in out
    # a limit at or above the count changes nothing
    out = run(tmp_path, "marks", "--limit", "4")
    assert len(_listed(out)) == 4 and "more" not in out


def test_marks_limit_must_be_positive(tmp_path):
    make_db(tmp_path, reel("AAAAA1", relevant=True, entry="subagents"))
    _with_marks(tmp_path, {"subagents": {"status": "tried", "updated": 1762000000}})
    assert "--limit needs a number of ideas of 1 or more" in run_failing(tmp_path, "marks", "--limit", "0")
