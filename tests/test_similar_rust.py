"""db.py similar with the optional Rust engine (rust/reels-similar): same answer as Python.

The comparison tests need the binary. They look for $SRD_REELS_SIMILAR, then a cargo build in
rust/target, then reels-similar on PATH, and are skipped when there is none.
"""
import json
import os
import random
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "digest" / "scripts"
EXE = "reels-similar.exe" if os.name == "nt" else "reels-similar"


def find_binary():
    if os.environ.get("SRD_REELS_SIMILAR"):
        return os.environ["SRD_REELS_SIMILAR"]
    for build in ("release", "debug"):
        p = ROOT / "rust" / "target" / build / EXE
        if p.is_file():
            return str(p)
    return shutil.which("reels-similar")


BINARY = find_binary()
needs_rust = pytest.mark.skipif(not BINARY, reason="reels-similar not built (cd rust && cargo build)")

SYLLABLES = ["ka", "lo", "tri", "men", "sa", "pu", "rel", "dor", "vi", "qua", "ño", "té", "zu", "bri", "on"]
CYRILLIC = ["при", "вет", "мир", "дом", "ка"]
MARKERS = {"en": "the and with this that you your for".split(),
           "es": "el la los con este que para una".split()}
EXTRA = ["link in bio 🔥", "#ia #productividad", "parte 2", "versión 2026...", "C++ y C#", "node.js",
         "ça marche", "100% gratis", "snake_case", "_x", "-- ¡ya!", "2026"]


def corpus(n=160, seed=7):
    """Made-up reels: 30 topics told in English and in "Spanish" (same stems, other endings),
    with noise, so there are groups, cross-language pairs and near misses at every threshold."""
    rnd = random.Random(seed)

    def word():
        if rnd.random() < 0.1:
            return "".join(rnd.choices(CYRILLIC, k=2))
        return "".join(rnd.choices(SYLLABLES, k=rnd.randint(2, 4)))

    topics = [[word() for _ in range(8)] for _ in range(30)]
    reels = {}
    for k in range(n):
        lang = rnd.choice(["en", "es"])
        topic = rnd.choice(topics)
        words = [w + ("ación" if lang == "es" else "ation") if rnd.random() < 0.5 else w
                 for w in rnd.sample(topic, rnd.randint(3, 7))]
        words += rnd.sample(MARKERS[lang], 3) + [word() for _ in range(rnd.randint(0, 4))]
        rnd.shuffle(words)
        r = {"shortcode": f"C{k:03d}", "relevant": rnd.random() < 0.9,
             "caption": " ".join(words) + " " + " ".join(rnd.sample(EXTRA, 2)),
             "author": f"user{k % 13}", "collection": rnd.choice(["IA", "Tech", None])}
        if rnd.random() < 0.3:
            r["transcript"] = " ".join(rnd.sample(topic, 4))
            r["lang"] = rnd.choice([lang, lang, "pt", ""])
        reels[r["shortcode"]] = r
    return {"version": 1, "reels": reels}


def run(home, data, *args, binary=None):
    home.mkdir(parents=True, exist_ok=True)
    (home / "reels.json").write_text(json.dumps(data), encoding="utf-8")
    # an empty SRD_REELS_SIMILAR means "no binary", so a reels-similar on PATH never interferes
    env = {**os.environ, "SRD_HOME": str(home), "PYTHONIOENCODING": "utf-8",
           "SRD_REELS_SIMILAR": binary or ""}
    return subprocess.run([sys.executable, str(SCRIPTS / "db.py"), "similar", *args], env=env,
                          capture_output=True, text=True, encoding="utf-8")


@needs_rust
@pytest.mark.parametrize("args", [(), ("--threshold", "0.5"), ("--threshold", "0.15"),
                                  ("--ngram-threshold", "0"), ("--ngram-threshold", "0.2"),
                                  ("--collection", "ia")])
def test_rust_and_python_give_the_same_groups(tmp_path, args):
    data = corpus()
    py = run(tmp_path, data, "--engine", "python", *args)
    rs = run(tmp_path, data, "--engine", "rust", *args, binary=BINARY)
    assert py.returncode == 0 and rs.returncode == 0, py.stderr + rs.stderr
    assert "candidate groups" in py.stdout  # the corpus really has duplicates to compare
    assert rs.stdout == py.stdout


@needs_rust
def test_auto_uses_rust_when_available(tmp_path):
    data = corpus(40)
    auto = run(tmp_path, data, binary=BINARY)
    assert auto.returncode == 0 and "using the Python version" not in auto.stderr
    assert auto.stdout == run(tmp_path, data, "--engine", "python").stdout


def test_auto_falls_back_to_python_without_the_binary(tmp_path):
    out = run(tmp_path, corpus(30), binary=str(tmp_path / "missing" / EXE))
    assert out.returncode == 0, out.stderr
    assert "candidate groups" in out.stdout


def test_rust_engine_without_the_binary_explains_how_to_build_it(tmp_path):
    out = run(tmp_path, corpus(5), "--engine", "rust", binary=str(tmp_path / "missing" / EXE))
    assert out.returncode != 0
    assert "cargo build --release" in out.stderr


def test_broken_binary_falls_back_to_python(tmp_path):
    broken = tmp_path / "bin" / EXE
    broken.parent.mkdir()
    broken.write_text("not a program")
    out = run(tmp_path, corpus(30), binary=str(broken))
    assert out.returncode == 0
    assert "using the Python version" in out.stderr and "candidate groups" in out.stdout
