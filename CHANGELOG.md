# Changelog

Notable changes to this plugin. The format follows [Keep a Changelog](https://keepachangelog.com/)
and versions follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- `db.py ideas` puts `+N new` next to the mark of tried or discarded ideas with reels saved after the mark (counted like `db.py marks`) and ends with a line pointing to `db.py ideas SLUG --since-mark`, so the list Claude reads while merging shows the news too.
- `db.py ideas --min-reels N` lists only the ideas backed by at least N reels, the ones that keep showing up in what you save. It combines with `--status`, `--sort`, `--older-than` and `--collection` (which counts only the reels from that collection). The skill runs `--status todo --min-reels 3` when it sums up a run, to suggest what to try first.
- The viewer shows `+N nuevos` next to the mark of a tried or discarded idea with reels saved after it was marked (counted like `db.py marks --new`), and a "Con novedades" checkbox, kept in the URL as `#novedades=1`, lists only those ideas. Marking an idea again in the viewer clears its badge, as the `db.py mark` command it gives resets the count.
- The Obsidian `INDEX.md` puts `+N` next to the ✅ / 🚫 of ideas with N reels saved after their mark, and the summary line says how many ideas have new reels, so the news shows without Bases or Dataview.
- `db.py marks --new` ends with the `db.py mark` commands that reset `+N` once the new reels are read (marking again keeps the note), and the skill's weekly review runs them, so the same ideas stop coming back every week.
- `db.py ideas SLUG --since-mark` lists only the reels of an idea saved after it was marked, the ones `db.py marks` counts as `+N new`, so reviewing them no longer means comparing dates by hand. An idea with no mark says so instead of listing everything; without slugs it points to `db.py marks --new`.
- Obsidian notes and `export_digest.py --json` have `new_since_mark` on ideas marked tried or discarded in `reels.json`: how many of their reels were saved after the mark (`0` included), so Bases or Dataview can filter tried ideas with new tricks and discarded ones that keep coming back. Unmarked ideas have no such property (`null` in the JSON).
- `db.py marks --new` lists only the marked ideas that got reels saved after the mark, to see at a glance which tried ideas have new tricks and which discarded ones keep coming back. It combines with `--status`.
- `export_digest.py --json` gives every idea `reels` (how many reels in `reels.json` back it, `0` if none) and `last_saved` (the date of the newest one, or `null`), like the Obsidian notes, so a Notion export can show them; unlike `sources`, they count reels saved after the entry was written.
- Obsidian notes have a `reels` property (how many reels back the idea) and `last_saved` (the date the newest one was saved), read from `reels.json`, so Bases or Dataview can sort and filter ideas the way `db.py ideas --sort` does. Ideas no reel points to get neither; a missing or damaged `reels.json` just leaves them out.
- `db.py marks` says how many reels were saved about each idea after it was last marked (`+2 new`), and names the discarded ideas that keep getting reels, with the `db.py ideas` that lists them; maybe they deserve another look. Reels with no known save date are never counted as new.
- `db.py ideas --older-than DAYS` lists only the ideas whose newest reel was saved more than DAYS days ago (ideas with no known date are left out). With `--status todo` it shows the pending ideas nothing new has been saved for, to try or discard them; it combines with `--sort` and `--collection`.
- `db.py ideas --sort recent` lists the ideas with the newest saved reel first (ideas without a known date last) and `--sort name` lists them by slug; most reels first (`--sort reels`) stays the default. It combines with `--status` and `--collection`.
- `db.py check` reports reels that back an idea but are no longer marked relevant (triaged again after merging), which `dump` and `similar` skip, with both fixes: `db.py set relevant true CODES` or `db.py set entry none CODES`.
- `db.py set relevant false` (or `maybe`, `none`) warns when one of those reels still backs an idea, names the idea and prints the `db.py set entry none` that takes it out; the triage is saved either way.
- `db.py rename --dry-run` says how many reels would move, what happens to the marks and how many headings and links would change in `digest.md`, without writing anything.
- `db.py set entry` warns when a new slug is nearly one already in use (`subagent` next to `subagents`, `mcp_servers` next to `mcp-servers`) and prints the `db.py rename` that joins them; the entry is still saved.
- `db.py check` lists digest ideas whose slugs are nearly the same under "Maybe the same idea", with the `db.py rename ... --digest` that merges the one with fewer reels into the other. It is only a hint: slugs that differ in their numbers (`step-1`, `step-2`) are skipped and `--strict` does not fail on it.
- `db.py check --fix` runs the `db.py rename` that check is sure about (exactly one slug lost its idea and exactly one idea has no reels) and moves the mark with it; in any other case it only reports, since choosing the target needs judgement.
- `db.py ideas --collection NAME` lists only the ideas with reels from that Instagram collection or YouTube playlist, counting only those reels.
- `db.py ideas SLUG ...` lists the reels behind an idea (save date, code, author, link), newest first, with its mark and note; a mistyped slug gets a "Did you mean" hint.
- `db.py mark` and `db.py rename` suggest the closest existing slug when one does not exist ("Did you mean: subagents?"), ignoring case and `-`/`_`; the guess is only shown, never applied.
- `db.py ideas` lists every idea reels point to, with how many reels back it, when the newest was saved and its mark (todo, tried or discarded), so the slugs already in use are at hand while merging. `--status todo` (or `tried`, `discarded`) lists only the ideas with that mark. The skill runs it before recording entries, so new reels reuse the existing slug instead of a near-copy that splits one idea in two.
- `db.py marks --status tried` (or `discarded`) lists only one kind of mark.
- When reels point to an idea that is no longer in the digest, `db.py check` prints the `db.py rename` that fixes it, naming the new slug when exactly one idea has no reels (almost always the same idea, renamed).
- `db.py rename OLD NEW` moves every reel of an idea, and its `db.py mark`, to another slug when the idea is renamed or merged into another one; before, each code had to go through `db.py set entry` again and the mark was lost. When both ideas are marked, the mark of NEW is kept. With `--digest` it also renames the `{#OLD}` heading and every `(#OLD)` link in `digest.md`, so both stay in agreement in one step.
- The viewer sorts ideas by their most recently saved reel or by how many reels back them (with `reels.json` open), besides the digest's own order, and keeps the choice in the URL (`#orden=recent`).
- `db.py check --strict` exits with status 1 when `digest.md` and the database disagree, so a script or CI job can stop on it; without the flag it still only reports.
- `export_digest.py --prune` deletes the vault notes it made for ideas no longer in the digest (merged or removed); notes with something written under `## My notes` are kept and listed. Without it they are still only listed.
- Obsidian notes have a `status` property (todo, tried or discarded, with the marks in `reels.json` winning over the digest text) and the `note` saved with `db.py mark`, so Bases or Dataview can list the ideas still to try. The vault's `INDEX.md` puts ✅ or 🚫 next to tried and discarded ideas and counts them.
- `install.ps1`: one-command setup on Windows (`irm .../install.ps1 | iex` or `-File install.ps1`). It finds a Python between 3.9 and 3.14 (the newest the dependencies support) while skipping the Microsoft Store alias, runs `doctor.py`, creates the environment and says what to type in Claude Code; `-CheckOnly` installs nothing. CI runs it in Windows PowerShell 5.1.
- `install.sh`: the same one-command setup for macOS and Linux (`curl -fsSL .../install.sh | sh` or `sh install.sh`), in plain POSIX sh. `--check-only` installs nothing and `SRD_PYTHON` picks the Python. CI runs it on Ubuntu and macOS.
- `install.sh --upgrade` and `install.ps1 -Upgrade` update the packages of an existing environment (they pass `--upgrade` to `setup_env.py`), the fix when an old yt-dlp stops downloading.
- The viewer keeps the search and filters in the URL (`#q=...&plataforma=tiktok`), so reloading does not lose them and a view can be bookmarked.
- The viewer filters ideas by platform (Instagram, TikTok, YouTube) when `reels.json` has reels from more than one.
- `doctor.py` warns when the yt-dlp in the environment is more than two months old and says how to update it; the skill then runs `setup_env.py --upgrade`.
- `setup_env.py --upgrade` says which yt-dlp version was installed before and which one is now, or that it already was the newest.
- `transcribe.py` and `fetch_meta.py` suggest `setup_env.py --upgrade` when they stop after several failures with the errors of an outdated yt-dlp ("Unable to extract", "Unsupported URL"...).
- A local digest viewer in TypeScript (`viewer/`): build it once with `npm run build`, open `viewer/dist/index.html`, load `digest.md` (and optionally `reels.json`) and search every idea, ignoring accents, or filter by category and tried/discarded status. Each idea shows the reels it came from and its `db.py mark` note. Nothing is uploaded.
- An online demo of the viewer with the invented sample (`examples/digest.md` + `examples/reels.json`), published to GitHub Pages with every release by `.github/workflows/pages.yml`; `npm run build:demo` builds the same page locally.
- Mark ideas as tried, discarded or pending from the viewer, with a note; it lists the `db.py mark` commands that save the marks, so `db.py` stays the only thing that writes `reels.json`.
- Optional Rust duplicate finder (`rust/`, binary `reels-similar`). `db.py similar` uses it automatically when it is installed and gives the same groups as before, much faster on large collections; `--engine python|rust` picks one explicitly.
- Releases attach ready-built `reels-similar` binaries for Linux, macOS and Windows, and CI builds and tests the Rust crate on all three, including the check that both engines give the same groups.
- `db.py status` shows how many saved reels come from Instagram, TikTok and YouTube.
- `db.py collections` marks YouTube playlists as such, and the `--collection` help says it works for them too; before, both only talked about Instagram collections.
- `db.py status` and `db.py unavailable` accept `--collection`, like `next`, `dump`, `similar` and `recent`; an unknown collection name is an error that points to `db.py collections`.
- `db.py check` compares `digest.md` with the database: ideas no reel points to, reels pointing to ideas that were renamed or lost while merging, repeated slugs, `(#slug)` links that go nowhere, marks for ideas no longer in the digest and relevant reels still waiting.

### Changed
- The skill's weekly review reads the new reels of each idea `db.py marks --new` lists with `db.py ideas SLUG --since-mark`, and the Notion export notes "N new since marked" on ideas with reels saved after their mark.
- The Notion export shows how many reels back each idea (`reels`, which also counts reels saved after the entry was written) and when the newest was saved, and the skill's weekly review runs `db.py marks --new` to bring up tried ideas with new reels and discarded ones that keep coming back.
- `setup_env.py` leaves a complete environment alone instead of running pip every time, so repeating the setup is instant and works offline; `--upgrade` updates the packages.

### Fixed
- The viewer's test that compares its digest parser with `export_digest.py --json` passes again (it failed, and with it the viewer CI job, since the JSON gained `reels`, `last_saved` and `new_since_mark`).
- `db.py mark` keeps an idea's note when it is marked again without `--note`; before, `db.py mark discarded SLUG` after `db.py mark tried SLUG --note "..."` dropped the note silently. `--note ""` clears it. The viewer's commands clear a note removed there with `db.py mark todo` first.
- `db.py next`, `dump`, `similar` and `recent` stop with an error on a `--collection` no reel is in, like `status` and `unavailable`; before, a typo looked like an empty collection ("Nothing left to triage"). All six suggest the closest name (`--collection "Ideas IA"` → "Ideas de IA").
- `db.py set entry` refuses slugs with spaces, `#`, parentheses and other characters a `{#slug}` heading or `(#slug)` link cannot hold, and suggests a valid one (`"Claude Code"` → `claude-code`); before, the reels were saved under a slug no digest idea could ever match.
- `export_digest.py --json` takes each idea's status from the marks `db.py mark` saved in `reels.json`, like the viewer, and adds their `note`; before, an idea marked as tried still went to Notion as pending unless the digest text had been edited too. A missing or damaged `reels.json` falls back to the digest's Status lines.
- The viewer labelled Instagram reels with how they were collected ("export", "live"...) instead of their platform.
- `doctor.py` warns when Python is newer than every dependency supports yet (3.15 has no onnxruntime build, so the install failed with a pip "ResolutionImpossible" error), and `setup_env.py` says which Python to install instead.
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
- `collect.py urls` reads TikTok and YouTube links too, not only Instagram ones, and names the links it skips (profiles, other sites) instead of dropping them silently.
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
