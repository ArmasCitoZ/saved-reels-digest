# Benchmarks: `db.py similar`, Python vs Rust

`db.py similar` compares every relevant reel with every other one, twice (same wording, then
similar spellings across languages). The work grows with the square of the number of reels, so
a collection that doubles takes four times as long. The optional Rust engine
([`rust/`](../rust/README.md)) does the same comparisons and prints exactly the same groups.

## Results

Made-up collections, all reels relevant, each with a caption and a ~120-word transcript (about
what real reels have after `transcribe.py`), half in English and half in Spanish, about six reels
per idea. Times are for the whole `db.py similar` command, including starting Python, reading
`reels.json` and printing the groups.

| Reels | Python | Rust | Speed-up |
|---:|---:|---:|---:|
| 500 | 3.6 s | 0.42 s | 9x |
| 1,000 | 15.3 s | 1.01 s | 15x |
| 2,000 | 58.9 s | 2.46 s | 24x |

Measured on 12 Nov 2026 on a 2-core Intel Xeon at 2.1 GHz (Linux), Python 3.13, Rust 1.97,
`cargo build --release`. Both engines gave identical output at every size.

With 2,000 reels Python needs about a minute; at 5,000 it would be around six. Rust stays in the
seconds, and it spreads the comparisons over every CPU core, so a normal laptop with 4-8 cores
is faster than the numbers above.

## What made Rust fast

The first port was only about 6x faster than Python with 1,000 reels: looking up words in the
standard `HashMap` (which uses a hash designed to resist attacks, not for speed) took most of the
time. Two changes brought it to the numbers above without changing a single result:

- term ids are looked up with a cheap multiply-rotate hash (the FxHash idea);
- the pairs are compared in parallel threads, then joined in the same order as Python's loops,
  so groups and cross-language pairs come out identical.

Each similarity is still added up term by term in the same order as Python, so even rounding
is the same, and `tests/test_similar_rust.py` checks the output matches.

## Run it yourself

```bash
cd rust
cargo build --release
python bench_similar.py              # 500, 1,000 and 2,000 reels
python bench_similar.py 5000         # any sizes you like
```

The script writes the made-up collection to a temporary folder, so your own `reels.json` is
never touched, and stops with an error if the two engines ever disagree.
