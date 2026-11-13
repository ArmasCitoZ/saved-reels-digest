# Viewer (work in progress)

A static page, written in TypeScript, to read a long `digest.md` comfortably: search every idea,
filter by category or status, and see which saved reels back each one. It runs in the browser
from local files: no server, and nothing is uploaded.

This folder holds the data layer so far:

| File | What it does |
|---|---|
| `src/digest.ts` | Parses `digest.md` exactly like `export_digest.py` (title, top list, ideas, status, sources) |
| `src/reels.ts` | Reads `reels.json`, attaches each idea's reels and the `db.py mark` marks, and filters ideas |

`test/digest.test.ts` runs both parsers on the same digests and fails if the TypeScript one reads
anything differently from `export_digest.py`, which stays the reference (skipped without Python).

```bash
cd viewer
npm install
npm test            # Vitest
npm run typecheck   # tsc --noEmit
```
