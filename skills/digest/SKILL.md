---
name: digest
description: Turn the user's saved Instagram reels into a deduplicated knowledge base on one topic (default tech, AI, Claude, programming, dev tools). Collects saves (official export, live session or browser), transcribes locally with Whisper, triages by topic, merges reels that say the same thing, and writes a ranked digest.md. Also reads TikTok favorites from TikTok's data export and YouTube Watch Later or playlists. Use when the user asks to go through, sort, summarize, filter or "doomscroll" their Instagram saved posts or reels, their saved/favorite TikToks, or their YouTube Watch Later.
argument-hint: "[topic, e.g. 'IA y Claude'] [path to Instagram export]"
---

# Saved Reels Digest

Goal: the user saved dozens or hundreds of reels and never watched them again. You go
through them, keep only the ones about their topic, merge the ones that say the same
thing, and hand back one ranked, readable digest. Everything runs on the user's
machine for free: Whisper runs locally and the thinking is done by you in this
session. Never suggest paid APIs.

Talk to the user in their language (detect it from their messages). Write `digest.md`
in that language too, even if the reels are in English.

## Paths

- `SCRIPTS` = the `scripts/` folder next to this SKILL.md (use its absolute path).
- `WORK` = `~/saved-reels-digest` (override: env var `SRD_HOME`). Holds `reels.json`
  (the database), `digest.md` (the output), `.venv`, `.models`, `.session`, `.slides`.
- `PY` = the Python inside `WORK/.venv` (`bin/python`, or `Scripts\python.exe` on Windows).

## Step 0: setup (first run only)

Run `python3 SCRIPTS/doctor.py` (`python` or `py` on Windows) first. It needs no
dependencies and checks the Python version, free disk space, that `WORK` is writable and
whether the venv is complete. If any line says FAIL, explain the fix to the user in plain
words and stop until it is solved. Then run `python3 SCRIPTS/setup_env.py`: it creates the
venv and prints `PY`. If `WORK/reels.json` already exists, run `PY SCRIPTS/db.py status`
and continue from the first unfinished step instead of starting over.

Topic: use what the user asked for. If they gave none, use **tech: Claude and other AI
tools/models, prompting, agents, programming, dev tools, automation, startups/SaaS
building**. Say which topic you are using in one line.

## Step 1: collect the saved posts

Choose with the user (AskUserQuestion if available) and recommend in this order:

1. **Official export (safest, zero risk to the account).** Instagram app → Settings →
   Accounts Center → Your information and permissions → Download your information →
   Download or transfer information → pick the Instagram account → *Some of your
   information* → **Saved** → Download to device → format **JSON**, date range *All time*.
   Instagram emails a zip (minutes to a few hours). Then:
   `PY SCRIPTS/collect.py export PATH_TO_ZIP_OR_FOLDER`
2. **Live, reusing the browser session (instant).** The user must be logged into
   instagram.com in a desktop browser (and that browser should be closed on Windows so
   its cookie DB is readable): `PY SCRIPTS/collect.py live --browser chrome`
   (firefox, edge, brave, safari, opera, vivaldi...). It saves a session, so later runs can
   use `--username THEIR_USER --stop-at-known` to only add new saves.
3. **Browser tools in this session** (Claude in Chrome or built-in browser), when
   available and the user prefers it: follow `references/browser-collect.md`, then
   `PY SCRIPTS/collect.py urls FILE`.

If the user just pastes a handful of links (Instagram, TikTok or YouTube, mixed is fine),
save them to a file or pipe them in: `PY SCRIPTS/collect.py urls -`. It names any link it
skipped because it is not a post (a profile, another site), so tell the user about those.

**TikTok favorites** can be added too, alone or next to Instagram (same database, same
digest). Only through TikTok's official export: TikTok app → Profile → ☰ → Settings and
privacy → Account → Download your data → format **JSON** → Request data, then download the
zip from the "Download data" tab when it is ready (it can take a few days). Then:
`PY SCRIPTS/collect.py tiktok PATH_TO_ZIP_OR_FOLDER`. It reads Favorites (TikTok's saved
videos), not likes. TikTok entries have ids like `tt7400...`; use them with `db.py` exactly
like shortcodes. Captions and transcripts come from yt-dlp with no login, and
`--browser` is not needed for them.

**YouTube Watch Later and playlists** go in the same way. Use Google Takeout
(takeout.google.com → deselect all → "YouTube and YouTube Music" → keep playlists):
`PY SCRIPTS/collect.py youtube PATH_TO_ZIP_OR_FOLDER` (`--playlist "<name>"` for only one).
To read one list right now: `PY SCRIPTS/collect.py youtube --url PLAYLIST_URL`; Watch Later is
private, so that one is `--url WL --browser chrome`. Entries have ids like `ytdQw4w9WgXcQ`, and
each playlist becomes a collection, so `--collection "<name>"` works later. `transcribe.py`
skips videos over 30 minutes (`--max-minutes 0` includes them); say so if any were skipped.

Tell the user once, plainly: options 2 and 3 use their own logged-in session the way
a browser would; Instagram's terms don't allow automated access, so the scripts go
slowly and stop on the first sign of rate limiting. Option 1 has no such risk.

## Step 2: captions

`PY SCRIPTS/fetch_meta.py` (add `--browser chrome` if posts fail with login errors).
Skips posts that already have captions (live collection already includes them).
~3 s per post, so for 300 posts run it in the background and keep the user informed.
If it prints `STOPPED`, relay the reason; do not loop retries. Wait, or switch to `--browser`.

## Step 3: triage by topic (you do this)

If the user only wants one of their Instagram collections ("just my IA folder") or one
YouTube playlist, run `PY SCRIPTS/db.py collections` to see the exact names (from the
official export and the playlist titles), then add `--collection "<name>"` to every
`db.py next`, `db.py dump`, `db.py similar` and `transcribe.py` call below (`db.py status --collection "<name>"` shows
the progress of that collection alone). Mention that reels saved outside any collection
are left out.

Loop: `PY SCRIPTS/db.py next --limit 60` → decide each line → write decisions:

```
PY SCRIPTS/db.py set relevant true  CODE1 CODE2 ...
PY SCRIPTS/db.py set relevant false CODE3 CODE4 ...
PY SCRIPTS/db.py set relevant maybe CODE5 ...
```

- `true`: clearly on topic from caption, author or collection name.
- `false`: clearly off topic (recipes, travel, memes, fitness...). Be decisive.
- `maybe`: empty/vague caption ("comment GUIDE", only hashtags) from an author or
  collection that could be on topic. These get transcribed and decided afterwards.
Repeat until `next` says nothing is left. Do not print every decision to the user.

## Step 4: transcribe (local Whisper)

`PY SCRIPTS/transcribe.py` transcribes `true` + `maybe` video reels and deletes the audio.
The model is picked from the computer's RAM (`--model auto`, shown by `doctor.py`):
`tiny` under 4 GB, `base` under 8 GB, otherwise `small` (good for Spanish/English,
~460 MB once), and `medium` on an NVIDIA GPU, which is used automatically. The user can
force one with `--model small` etc. if accuracy is poor. Roughly 10–30 s
per reel on CPU, so run in the background for big batches and report progress.
If many fail with login errors, retry with `--browser chrome`.
If it prints `STOPPED: no connection`, the internet dropped for several minutes (it already
waited and retried). Nothing is lost: tell the user and re-run the same command once they are
online; it continues with the reels still missing a transcript.

Photo and carousel posts have no audio, and their caption often says little. If
`PY SCRIPTS/slides.py pending` lists any, read them yourself:

1. `PY SCRIPTS/slides.py fetch --limit 10` downloads the images and prints one `IMAGE:`
   path per image, grouped by post (`--browser chrome` if posts fail with login errors).
2. Open each image with your file reading tool and write down what it says: the text,
   plus anything in a screenshot or diagram that matters. Leave out decoration.
3. Save it, which also deletes that post's images: `PY SCRIPTS/slides.py save CODE`,
   passing the text on stdin. If the images say nothing useful, use `save CODE --empty`
   (an empty text on its own is refused, so a failed pipe never deletes the images).
4. Repeat until `pending` is empty. If it prints `STOPPED`, relay the reason; do not loop.
   If you cannot open images in this session, run `slides.py clean` and skip this.

Then resolve maybes: `PY SCRIPTS/db.py next --maybe` shows them with transcripts and image
text; set each to `true` or `false`.

## Step 5: merge duplicates and write the digest (you do this)

1. `PY SCRIPTS/db.py similar` gives candidate groups with the same wording, plus possible
   matches between reels in different languages. Treat both as hints. Then read
   everything: `PY SCRIPTS/db.py dump --undigested`. Output is capped at ~60,000
   characters per call; when it ends with `Continue with: dump --offset N`, run that
   command for the next page and keep going until no such line appears. Group by **meaning**, not wording: two creators explaining the
   same trick, tool, prompt or workflow are one entry, even in different languages.
2. For each group, keep the most complete and concrete version; add details only the
   other reels mention; flag contradictions; flag hype or likely outdated claims
   (popular is not the same as good).
3. Write/update `WORK/digest.md` with this structure:

```markdown
# <Topic>: my saved reels digest
_Updated YYYY-MM-DD · N saved · N on topic · N unique ideas after merging_

## Do these first
1. **<idea>**: one line on why (impact vs effort) → [entry](#slug)
(top 5–10, ranked by usefulness for this user: concrete, actionable, low effort first)

## Saved this week
- **<idea>** → [entry](#slug) · new / N more reels
(only entries with reels saved in the last 7 days, from `db.py recent`; omit if none)

## <Category, e.g. Claude Code / Prompting / Agents / AI tools / Dev workflow>
### <Idea title> {#slug}
<2–4 sentence summary of the technique or insight, merged from all sources>
**How to apply:** concrete steps, commands, prompts or settings mentioned.
**Seen in N reels** (saved YYYY-MM-DD → YYYY-MM-DD): [@creator](url) · [@creator2](url)
**Notes:** contradictions, caveats, "probably outdated", "mostly hype" (only if any)
```

   Merged entries list every source reel. Take the save dates from the `SAVED:` line
   of each reel in `dump` (one date if all are the same day). Entries backed by several creators are a
   signal, not proof; rank by usefulness, not by count.
4. Record which entry each reel went into (enables incremental runs):
   `PY SCRIPTS/db.py set entry <slug> CODE1 CODE2 ...`
5. Run `PY SCRIPTS/db.py recent --days 7` and rebuild "Saved this week" from it
   (it shows each recent reel and the entry it went into).
6. On later runs, merge new reels into existing entries before creating new ones,
   and refresh the header counts, "Do these first" and "Saved this week".
7. Respect what the user already did: run `PY SCRIPTS/db.py marks`. For each marked
   entry, make the first line under its `###` heading `**Status:** ✅ Tried: <note>` or
   `**Status:** 🚫 Discarded: <note>` (keep the heading itself unchanged), and leave both
   kinds out of "Do these first". Never drop a discarded entry: new reels about it still merge
   into it, so the user is not pitched the same idea again.
8. Before telling the user it is done, run `PY SCRIPTS/db.py check`. It compares
   `digest.md` with the database and lists what does not match: ideas no reel points to
   (run `db.py set entry` for their sources), reels pointing to an idea that was renamed or
   dropped (point them to the idea they now belong to), repeated `{#slug}`s, `(#slug)` links
   that go nowhere and relevant reels not merged yet. Fix each one and run it again until it
   says they agree; otherwise the next run merges new reels into the wrong ideas.

When the user says they tried an idea or it is not for them ("ya probé lo de los
subagentes", "eso no me sirve"), record it right away:
`PY SCRIPTS/db.py mark tried <slug> --note "worked for refactors"` (or `discarded`;
`todo` clears the mark) and update the entry in `digest.md`. Only slugs some reel points to
can be marked; if it says nothing was marked, pick the right slug from the list it prints.

## Optional: export to Obsidian

If the user keeps notes in Obsidian (or asks for one note per idea), run
`PY SCRIPTS/export_digest.py --vault <vault folder>` (`--folder` changes the subfolder,
default `Saved reels`). It writes one note per `### idea` with frontmatter, tags by
category, the source reels and links between ideas of the same category, plus an
`INDEX.md` map of content. Re-running updates the notes and keeps whatever the user wrote
under `## My notes`; files it did not create are never overwritten. It relies on the
digest structure above, so keep the `### Title {#slug}` headings.

## Optional: export to Notion

Only through the Notion connector of this Claude session (tools named like
`notion-create-pages` / `notion-search`); never ask for a Notion API key. If no Notion
tools are available, say the Notion connector needs to be enabled and offer the Obsidian
export or the plain `digest.md` instead.

1. `PY SCRIPTS/export_digest.py --json` prints the digest as JSON: `title`, `date`,
   `top`, `categories` and `ideas` (each with `title`, `slug`, `category`, `status`
   = todo / tried / discarded, `sources` and the markdown `body`). Use it instead of
   re-reading `digest.md`.
2. Ask where it should go (a parent page; search for it by name). Create one page titled
   like the digest with "Do these first" as a numbered list and every idea grouped under
   its category, then one child page per idea with the `body` as content, and a first line
   with category, status and the number of source reels. Link the top list to the child
   pages.
3. On later exports, search the parent page for an existing page with the same idea title
   and update it instead of creating a duplicate. Never delete pages the user made.
4. Finish with the link to the parent page and how many idea pages were created or updated.

## Finish

Tell the user in 2–3 lines: how many saves were read, how many were on topic, how
many unique ideas remained after merging, the path to `digest.md`, and the top 3
items. Offer one next step (e.g. "want me to apply #1 to this project?").

## Troubleshooting

- `reels.json is damaged`: the message names the fix. Before replacing anything, tell the user
  and keep the damaged file under another name, in case the backup is older than they expect.
- `STOPPED ... login/rate-limit`: Instagram wants a login or is throttling. Use
  `--browser <browser where they are logged in>`, or wait an hour. Never lower `--delay`
  below 2.
- Browser cookies unreadable (Chrome on Windows locks/encrypts them): close Chrome
  completely and retry, or use `--browser firefox`, or the official export.
- Export parse finds 0 links: they chose HTML or the wrong section; any file
  containing instagram.com/p|reel links works: `collect.py export path/to/file`.
- Private or deleted posts are marked `unavailable` by `fetch_meta.py` and skipped by
  triage and transcription. `PY SCRIPTS/db.py unavailable` lists them; mention the count
  in the final summary so the user knows some saves are gone.
