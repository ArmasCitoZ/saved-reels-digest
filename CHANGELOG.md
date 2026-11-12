# Changelog

Notable changes to this plugin. The format follows [Keep a Changelog](https://keepachangelog.com/)
and versions follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- Optional Rust duplicate finder (`rust/`, binary `reels-similar`). `db.py similar` uses it automatically when it is installed and gives the same groups as before, much faster on large collections; `--engine python|rust` picks one explicitly.
- `db.py check` compares `digest.md` with the database: ideas no reel points to, reels pointing to ideas that were renamed or lost while merging, repeated slugs, `(#slug)` links that go nowhere, marks for ideas no longer in the digest and relevant reels still waiting.

### Fixed
- `fetch_meta.py` stops after 5 posts in a row look deleted or private, instead of marking a throttled session's whole list as gone.
- `collect.py live` keeps what it read and explains why when Instagram or the connection cuts the read short, instead of a traceback.
- A half-downloaded export zip now gets a clear message in every collector, and an export with no saved posts says what to request.
- Instagram collections are recognized whatever language the export is in, not just English and Spanish.
- An idea called "Index" no longer replaces the vault's `INDEX.md`, and titles Windows cannot use as file names (CON, NUL...) get a safe one.
- The exporters accept slugs with accents (`{#automatización}`), which used to end up inside the idea's title and break its links.
- The exporters leave `##` and `###` lines inside code blocks alone, instead of treating them as new categories and ideas.
- `db.py similar` finds duplicates in any alphabet; words with letters outside Spanish (ç, è, Cyrillic...) used to be cut up or ignored.
- `db.py recent` no longer lists deleted posts nothing was read from as waiting for the digest.
- A full disk while saving `reels.json` or its backup no longer leaves half-written temporary files behind, and says the database was not changed.
- `transcribe.py --shortcodes` names the codes that are not in the database instead of skipping them silently, and accepts spaces after commas and pasted Instagram or TikTok links.
- `slides.py save` refuses an empty text instead of deleting the downloaded images; `--empty` marks posts whose images say nothing useful.
- `fetch_meta.py` saves the captions it already read when you press Ctrl+C, instead of losing up to nine posts.
- `db.py set` and `show` accept pasted Instagram or TikTok links, and fail with a clear message (changing nothing) when none of the codes are in the database.
- Pasted YouTube links (`watch?v=`, `youtu.be`, Shorts, live and embed links) work in `db.py set`, `db.py show` and `transcribe.py --shortcodes`, like Instagram and TikTok links already did; before, saved YouTube videos could only be named by their internal `yt…` code.
- `slides.py save` accepts the post's pasted Instagram link, like `db.py set`/`show` and `transcribe.py`; an unknown post says that nothing was saved and no images were deleted.
- `db.py mark` only marks ideas that some reel points to: a mistyped slug is skipped and named, and when none of the slugs exist nothing is saved and the known ideas are listed. Before, typos were stored as marks the digest never showed.

## [0.2.0] - 2026-11-08

### Added
- Read the text inside photo and carousel posts: `slides.py` fetches the images and Claude looks at them.
- YouTube Watch Later and playlists, from Google Takeout or a playlist link (`collect.py youtube`).
- TikTok favorites from TikTok's official data export (`collect.py tiktok`).
- `db.py similar` also suggests duplicates between reels in different languages.
- Export the digest to an Obsidian vault, and to Notion through Claude's connector (`export_digest.py --json`).
- `db.py mark` remembers ideas as tried or discarded; the digest shows it.
- Save dates in the digest and a "Saved this week" section (`db.py recent`).
- `--collection` filter and `db.py collections` for Instagram collections.
- `doctor.py` checks the computer before setup; the Whisper model is picked from the available RAM.
- Step-by-step Windows guide (`docs/windows.md`) and a sample digest (`examples/digest.md`).
- CI on Linux, macOS and Windows, `CONTRIBUTING.md`, issue templates and this changelog.
- `reels.backup.json`: a copy of the database refreshed at most once a day, so hours of transcription survive a bad run.
- A demo GIF in the README, drawn from the real output of the scripts on invented data (`docs/demo/make_demo.py`).

### Changed
- `db.py dump` is capped at about 60,000 characters per call; continue with `--offset`.
- `transcribe.py` skips videos over 30 minutes by default (`--max-minutes`).

### Fixed
- Transcription resumes after network drops without marking reels as failed or repeating work.
- Deleted and private posts are detected and listed apart (`db.py unavailable`).
- Exporters keep the top list of Spanish digests ("Haz esto primero").
- Exporting from a folder whose own path contains "saved" no longer reads unrelated files.
- `db.py dump` keeps `--collection`, `--all` and the other filters in its "Continue with" line, so later pages no longer skip or repeat reels.
- `db.py set` refuses unknown fields and invalid triage values, which used to hide reels from every later step without any warning.
- Scripts always print UTF-8, so a caption with an emoji no longer crashes them on Windows when Claude reads their output.
- A damaged `reels.json` gives a clear message and the way to restore it, instead of a traceback.
- The Obsidian and JSON exports find the top list and each idea's status when the digest is in any language, and keep the top list's own heading.
- Deleted posts that have no text no longer show up in `db.py dump` or stay counted as waiting for the digest.

## [0.1.0] - 2026-11-03

### Added
- First version: collect saved Instagram reels (official export, browser session or Claude in Chrome),
  transcribe them locally with Whisper, triage by topic, merge duplicates and write a ranked `digest.md`.
