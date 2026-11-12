"""Time `db.py similar` with the Python and the Rust engine on made-up collections.

    cd rust && cargo build --release && python bench_similar.py [500 1000 2000]

Each reel gets a caption and a ~120-word transcript, about what real reels have after
transcribe.py. The collection is written to a temporary SRD_HOME, so your reels.json is never
touched. Both outputs must be identical; the script stops if they are not.
"""
import json
import os
import random
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
DB = HERE.parent / "skills" / "digest" / "scripts" / "db.py"
EXE = HERE / "target" / "release" / ("reels-similar.exe" if os.name == "nt" else "reels-similar")
LETTERS = "abcdefghijklmnopqrstuvwxyzáéíóñ"
MARKERS = {"en": "the and with this that you your for".split(),
           "es": "el la los con este que para una".split()}


def collection(n: int, seed: int = 1) -> dict:
    rnd = random.Random(seed)
    vocab = ["".join(rnd.choices(LETTERS, k=rnd.randint(4, 10))) for _ in range(20000)]
    topics = [rnd.sample(vocab, 40) for _ in range(max(10, n // 6))]  # ~6 reels per idea
    reels = {}
    for k in range(n):
        lang = rnd.choice(["en", "es"])
        # the same idea told in Spanish uses the same stems with other endings, like cognates
        topic = [w + ("ación" if lang == "es" else "ation") for w in rnd.choice(topics)]
        words = rnd.choices(topic, k=50) + rnd.choices(vocab, k=60) + rnd.choices(MARKERS[lang], k=10)
        rnd.shuffle(words)
        code = f"B{k:05d}"
        reels[code] = {"shortcode": code, "relevant": True, "caption": " ".join(words[:20]),
                       "transcript": " ".join(words[20:]), "lang": lang}
    return {"version": 1, "reels": reels}


def timed(home: Path, engine: str):
    env = {**os.environ, "SRD_HOME": str(home), "PYTHONIOENCODING": "utf-8", "SRD_REELS_SIMILAR": str(EXE)}
    start = time.perf_counter()
    out = subprocess.run([sys.executable, str(DB), "similar", "--engine", engine], env=env,
                         capture_output=True, text=True, encoding="utf-8", check=True)
    return time.perf_counter() - start, out.stdout


def main(sizes):
    if not EXE.is_file():
        sys.exit(f"{EXE} not found: run `cargo build --release` first")
    print("| Reels | Python | Rust | Speed-up |\n|---:|---:|---:|---:|")
    for n in sizes:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            (home / "reels.json").write_text(json.dumps(collection(n)), encoding="utf-8")
            py_s, py_out = timed(home, "python")
            rs_s, rs_out = timed(home, "rust")
            if py_out != rs_out:
                sys.exit(f"{n} reels: the engines disagree, that is a bug in rust/")
            print(f"| {n:,} | {py_s:.1f} s | {rs_s:.2f} s | {py_s / rs_s:.0f}x |", flush=True)


if __name__ == "__main__":
    main([int(x) for x in sys.argv[1:]] or [500, 1000, 2000])
