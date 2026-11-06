"""Tests for the reel database CLI (db.py next / set / similar / dump / show)."""
import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "skills" / "digest" / "scripts"


def reel(code, **fields):
    return {"shortcode": code, "url": f"https://www.instagram.com/reel/{code}/",
            "added_at": 1761600000, "relevant": None, **fields}


def make_db(home, *reels):
    home.mkdir(parents=True, exist_ok=True)
    db = {"version": 1, "reels": {r["shortcode"]: r for r in reels}}
    (home / "reels.json").write_text(json.dumps(db), encoding="utf-8")


def run(home, *args):
    env = {**os.environ, "SRD_HOME": str(home), "PYTHONIOENCODING": "utf-8"}
    r = subprocess.run([sys.executable, str(SCRIPTS / "db.py"), *args], env=env,
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    return r.stdout


def load(home):
    return json.loads((home / "reels.json").read_text(encoding="utf-8"))["reels"]


# ------------------------------------------------------------------- next
def test_next_lists_only_untriaged(tmp_path):
    make_db(tmp_path, reel("AAAAA1", caption="new idea", author="ana"),
            reel("BBBBB2", relevant=True, caption="done"),
            reel("CCCCC3", relevant="maybe", caption="unsure", transcript="spoken words"))
    out = run(tmp_path, "next")
    assert "1 waiting" in out
    assert "AAAAA1 | @ana" in out
    assert "BBBBB2" not in out and "CCCCC3" not in out


def test_next_maybe_includes_transcript_and_respects_limit(tmp_path):
    make_db(tmp_path, reel("AAAAA1"), reel("CCCCC3", relevant="maybe", transcript="spoken words"))
    out = run(tmp_path, "next", "--maybe", "--limit", "5")
    assert "CCCCC3" in out and "TRANSCRIPT: spoken words" in out
    assert "(no caption)" in out  # AAAAA1 has nothing to show
    assert "Showing 1:" in run(tmp_path, "next", "--maybe", "--limit", "1")


def test_next_when_nothing_left(tmp_path):
    make_db(tmp_path, reel("AAAAA1", relevant=False))
    assert "Nothing left to triage." in run(tmp_path, "next")


# -------------------------------------------------------------------- set
def test_set_parses_values_and_accepts_comma_lists(tmp_path):
    make_db(tmp_path, reel("AAAAA1"), reel("BBBBB2"), reel("CCCCC3"))
    out = run(tmp_path, "set", "relevant", "true", "AAAAA1,BBBBB2", "CCCCC3")
    assert "on 3 reels" in out
    assert all(r["relevant"] is True for r in load(tmp_path).values())
    run(tmp_path, "set", "relevant", "None", "CCCCC3")
    assert load(tmp_path)["CCCCC3"]["relevant"] is None
    run(tmp_path, "set", "topic", "Claude Code", "AAAAA1")
    assert load(tmp_path)["AAAAA1"]["topic"] == "Claude Code"


def test_set_reports_unknown_codes_without_failing(tmp_path):
    make_db(tmp_path, reel("AAAAA1"))
    out = run(tmp_path, "set", "relevant", "false", "AAAAA1", "ZZZZZ9")
    assert "on 1 reels" in out and "Unknown: ZZZZZ9" in out
    assert load(tmp_path)["AAAAA1"]["relevant"] is False
    assert "ZZZZZ9" not in load(tmp_path)


# ------------------------------------------------------------------- dump
def test_dump_shows_relevant_and_filters_undigested(tmp_path):
    make_db(tmp_path,
            reel("AAAAA1", relevant=True, caption="keep me", transcript="hola", lang="es"),
            reel("BBBBB2", relevant=True, caption="already merged", entry="idea-1"),
            reel("CCCCC3", relevant=False, caption="skip me"))
    out = run(tmp_path, "dump")
    assert "### AAAAA1" in out and "CAPTION: keep me" in out and "TRANSCRIPT (es): hola" in out
    assert "[entry: idea-1]" in out
    assert "CCCCC3" not in out
    out = run(tmp_path, "dump", "--undigested")
    assert "AAAAA1" in out and "BBBBB2" not in out
    assert "CCCCC3" in run(tmp_path, "dump", "--all")


def test_dump_truncates_long_captions(tmp_path):
    make_db(tmp_path, reel("AAAAA1", relevant=True, caption="word " * 100))
    line = next(ln for ln in run(tmp_path, "dump", "--chars", "20").splitlines()
                if ln.startswith("CAPTION:"))
    assert line.endswith("…") and len(line) == len("CAPTION: ") + 20


# ---------------------------------------------------------------- similar
def test_similar_groups_reels_with_the_same_wording(tmp_path):
    make_db(tmp_path,
            reel("AAAAA1", relevant=True, author="a",
                 caption="claude code subagents parallel refactor huge repository"),
            reel("BBBBB2", relevant=True, author="b",
                 caption="huge repository refactor with claude code subagents parallel"),
            reel("CCCCC3", relevant=True, author="c",
                 caption="pasta carbonara recipe guanciale pecorino eggs"),
            reel("DDDDD4", relevant=False,
                 caption="claude code subagents parallel refactor huge repository"))
    out = run(tmp_path, "similar")
    assert "1 candidate groups" in out
    group = next(ln for ln in out.splitlines() if ln.startswith("- "))
    assert "AAAAA1" in group and "BBBBB2" in group
    assert "CCCCC3" not in out and "DDDDD4" not in out


def test_similar_without_duplicates(tmp_path):
    make_db(tmp_path,
            reel("AAAAA1", relevant=True, caption="claude code subagents parallel refactor"),
            reel("CCCCC3", relevant=True, caption="pasta carbonara recipe guanciale pecorino"))
    assert "No obvious duplicates" in run(tmp_path, "similar")


# ------------------------------------------------------------------- show
def test_show_prints_record_and_flags_unknown(tmp_path):
    make_db(tmp_path, reel("AAAAA1", caption="café ñandú"))
    out = run(tmp_path, "show", "AAAAA1", "ZZZZZ9")
    assert '"shortcode": "AAAAA1"' in out and "café ñandú" in out
    assert "unknown ZZZZZ9" in out


# ------------------------------------------------------------- collections
def _collection_db(home):
    make_db(home, reel("AAAAA1", caption="claude tip", collection="IA"),
            reel("BBBBB2", caption="pasta", collection="Recetas"),
            reel("CCCCC3", caption="no folder"),
            reel("DDDDD4", relevant=True, caption="agents", collection="IA"),
            reel("EEEEE5", relevant=True, caption="cake", collection="Recetas"))


def test_collections_lists_counts(tmp_path):
    _collection_db(tmp_path)
    out = run(tmp_path, "collections")
    lines = [ln.split() for ln in out.splitlines()]
    assert ["IA", "2"] in lines and ["Recetas", "2"] in lines
    assert "(no collection)" in out


def test_next_and_dump_filter_by_collection_case_insensitive(tmp_path):
    _collection_db(tmp_path)
    nxt = run(tmp_path, "next", "--collection", "ia")
    assert "1 waiting" in nxt and "AAAAA1" in nxt and "BBBBB2" not in nxt
    dump = run(tmp_path, "dump", "--collection", " IA ")
    assert "DDDDD4" in dump and "EEEEE5" not in dump


def test_unknown_collection_says_so(tmp_path):
    _collection_db(tmp_path)
    assert "in collection 'Viajes'" in run(tmp_path, "next", "--collection", "Viajes")
