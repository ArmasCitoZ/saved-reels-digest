# Viewer

A static page, written in TypeScript, to read a long `digest.md` comfortably: search every idea,
filter by category or status, and see which saved reels back each one. It runs in the browser
from local files: no server, and nothing is uploaded.

```bash
cd viewer
npm install
npm run build       # writes dist/index.html, a single self-contained file
```

Open `dist/index.html` in your browser (double-click works) and pick `digest.md`, plus
`reels.json` if you want each idea's reels and the marks from `db.py mark`. Both live in
`~/saved-reels-digest/` (or `$SRD_HOME`). You can also drag the files onto the page.

- The search box matches every word you type in titles, text, categories and reel authors,
  ignoring case and accents (`/` jumps to it).
- Filter by category and by status: pending, tried or discarded. A mark saved with `db.py mark`
  wins over what the digest text says, as in the next digest.

## Code

| File | What it does |
|---|---|
| `src/digest.ts` | Parses `digest.md` exactly like `export_digest.py` (title, top list, ideas, status, sources) |
| `src/reels.ts` | Reads `reels.json`, attaches each idea's reels and the `db.py mark` marks, and filters ideas |
| `src/markdown.ts` | The small Markdown subset the digest uses, escaped so no HTML or script can get in |
| `src/main.ts` | The page: opening files, the search box and filters |
| `index.html` + `scripts/build.mjs` | Page template; the build inlines the bundled script so it works from `file://` |

`test/digest.test.ts` runs both parsers on the same digests and fails if the TypeScript one reads
anything differently from `export_digest.py`, which stays the reference (skipped without Python).

```bash
npm test            # Vitest
npm run typecheck   # tsc --noEmit
```
