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


# ------------------------------------------------------------- dump budget
def _many_reels(home, n=10):
    make_db(home, *[reel(f"CODE{i:03d}", relevant=True, caption=f"idea {i} " + "x" * 300)
                    for i in range(n)])


def test_dump_stops_at_budget_and_tells_how_to_continue(tmp_path):
    _many_reels(tmp_path)
    out = run(tmp_path, "dump", "--max-total", "1000")
    shown = [ln for ln in out.splitlines() if ln.startswith("### ")]
    assert 0 < len(shown) < 10
    assert len(out) < 1600
    assert f"Continue with: dump --offset {len(shown)}" in out


def test_dump_offset_pages_through_everything_once(tmp_path):
    _many_reels(tmp_path)
    seen, offset = [], 0
    for _ in range(20):
        out = run(tmp_path, "dump", "--max-total", "1000", "--offset", str(offset))
        page = [ln.split()[1] for ln in out.splitlines() if ln.startswith("### ")]
        seen += page
        offset += len(page)
        if "Continue with" not in out:
            break
    assert seen == [f"CODE{i:03d}" for i in range(10)]


def test_dump_always_shows_at_least_one_reel_and_zero_means_no_limit(tmp_path):
    _many_reels(tmp_path, 3)
    assert run(tmp_path, "dump", "--max-total", "10").count("### ") == 1
    out = run(tmp_path, "dump", "--max-total", "0")
    assert out.count("### ") == 3 and "Continue with" not in out


# ------------------------------------------------------------------- dump paging
def test_dump_continue_line_keeps_every_filter(tmp_path):
    make_db(tmp_path, *[reel(f"PAGE{i:02d}", relevant=True, collection="IA", caption="x" * 200)
                        for i in range(4)], reel("OTHER9", relevant=True, collection="Viajes", caption="y"))
    out = run(tmp_path, "dump", "--collection", "IA", "--all", "--undigested",
              "--chars", "150", "--max-total", "300")
    hint = out.split("Continue with: ")[1].strip()
    assert hint.startswith("dump --offset 1")
    for piece in ('--collection "IA"', "--all", "--undigested", "--chars 150", "--max-total 300"):
        assert piece in hint


def test_following_the_continue_line_reads_each_reel_once(tmp_path):
    make_db(tmp_path, reel("OTHER1", relevant=True, collection="Viajes", caption="z"),
            *[reel(f"PAGE{i:02d}", relevant=True, collection="IA", caption="x" * 200) for i in range(5)])
    args, seen = ["dump", "--collection", "IA", "--max-total", "300"], []
    while True:
        out = run(tmp_path, *args)
        seen += [line.split()[1] for line in out.splitlines() if line.startswith("### ")]
        if "Continue with: " not in out:
            break
        args = ["dump", "--offset", out.split("--offset ")[1].split()[0], "--collection", "IA",
                "--max-total", "300"]
    assert seen == [f"PAGE{i:02d}" for i in range(5)]


# ------------------------------------------------------------------- set validation
def run_failing(home, *args):
    env = {**os.environ, "SRD_HOME": str(home), "PYTHONIOENCODING": "utf-8"}
    r = subprocess.run([sys.executable, str(SCRIPTS / "db.py"), *args], env=env,
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode != 0
    return r.stderr


def test_set_refuses_a_misspelled_field(tmp_path):
    make_db(tmp_path, reel("AAAAA1"))
    assert "relevent" in run_failing(tmp_path, "set", "relevent", "true", "AAAAA1")
    assert "relevent" not in load(tmp_path)["AAAAA1"]


def test_set_refuses_an_invalid_triage_value(tmp_path):
    make_db(tmp_path, reel("AAAAA1"))
    assert "maybe" in run_failing(tmp_path, "set", "relevant", "yes", "AAAAA1")
    assert load(tmp_path)["AAAAA1"]["relevant"] is None
    assert "1 waiting" in run(tmp_path, "next")  # still reachable by triage


def test_set_accepts_every_triage_value(tmp_path):
    make_db(tmp_path, reel("AAAAA1"))
    for value, stored in (("TRUE", True), ("false", False), ("maybe", "maybe"), ("none", None)):
        run(tmp_path, "set", "relevant", value, "AAAAA1")
        assert load(tmp_path)["AAAAA1"]["relevant"] == stored


# ------------------------------------------------------------------- output encoding
def test_emoji_captions_print_on_a_windows_style_pipe(tmp_path):
    make_db(tmp_path, reel("AAAAA1", caption="prueba 🤖 automatización"))
    env = {**os.environ, "SRD_HOME": str(tmp_path), "PYTHONIOENCODING": "cp1252", "PYTHONUTF8": "0"}
    r = subprocess.run([sys.executable, str(SCRIPTS / "db.py"), "next"], env=env, capture_output=True)
    assert r.returncode == 0, r.stderr
    assert "🤖 automatización" in r.stdout.decode("utf-8")
