# Rust: fast duplicate finder

`db.py similar` compares every relevant reel with every other one (n²). That is fine for a few
hundred reels and slow with thousands. This folder holds a Rust port of the same logic.

Python stays the reference: the Rust code follows `db.py` step by step (same tokens, stop
words, TF-IDF weights, union-find and cross-language pass), so both should give the same
groups. If they ever disagree, Python is right and the Rust side has a bug.

| Crate | What it is |
|---|---|
| `reels-core` | Library: `find_similar(docs, threshold, ngram_threshold)` returns the duplicate groups and the cross-language pairs |
| `reels-similar` | Command line tool: reads `reels.json` and prints the groups as JSON |

Nothing here is needed to use the plugin; it is an optional speed-up. `db.py similar` uses
`reels-similar` on its own when it finds it (in `$SRD_REELS_SIMILAR`, or on `PATH`), and falls
back to Python if it is missing or fails. `--engine python` or `--engine rust` picks one.
`tests/test_similar_rust.py` runs both on made-up collections and checks the output is identical.
CI runs `cargo fmt`, `clippy`, the Rust tests and that comparison on Linux, macOS and Windows.

How much faster it is: [docs/benchmarks.md](../docs/benchmarks.md) (about 24x with 2,000 reels).

Each release attaches ready-built binaries (`reels-similar-linux-x86_64`, `reels-similar-macos-arm64`,
`reels-similar-windows-x86_64.exe`); rename yours to `reels-similar` and put it on `PATH`. To build it
yourself:

```bash
cd rust
cargo test
cargo build --release   # the binary ends up in target/release/reels-similar
```

## reels-similar

```text
reels-similar [PATH | -] [--threshold 0.3] [--ngram-threshold 0.1] [--collection NAME]
```

`PATH` defaults to the database db.py uses (`$SRD_HOME/reels.json`, or
`~/saved-reels-digest/reels.json`); `-` reads the same format from standard input. Options mean
the same as in `db.py similar`. Only reels marked relevant and with some text are compared.

```json
{"reels": 4, "groups": [["AAA", "BBB"]], "cross": [["AAA", "ESP"], ["BBB", "ESP"]]}
```

`groups` are reels with the same wording, biggest group first; `cross` are pairs in different
languages with similar spellings. Exit code 1 means the database could not be read, 2 a bad option.
