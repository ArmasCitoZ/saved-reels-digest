# Rust: fast duplicate finder

`db.py similar` compares every relevant reel with every other one (n²). That is fine for a few
hundred reels and slow with thousands. This folder holds a Rust port of the same logic.

Python stays the reference: the Rust code follows `db.py` step by step (same tokens, stop
words, TF-IDF weights, union-find and cross-language pass), so both should give the same
groups. If they ever disagree, Python is right and the Rust side has a bug.

| Crate | What it is |
|---|---|
| `reels-core` | Library: `find_similar(docs, threshold, ngram_threshold)` returns the duplicate groups and the cross-language pairs |

Nothing here is needed to use the plugin; it is an optional speed-up.

```bash
cd rust
cargo test
```
