# Changelog

Notable changes to this plugin. The format follows [Keep a Changelog](https://keepachangelog.com/)
and versions follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

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
