---
name: digest
description: Turn the user's saved Instagram reels into a deduplicated knowledge base on one topic (default tech, AI, Claude, programming, dev tools). Collects saves (official export, live session or browser), transcribes locally with Whisper, triages by topic, merges reels that say the same thing, and writes a ranked digest.md. Use when the user asks to go through, sort, summarize, filter or "doomscroll" their Instagram saved posts or reels.
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
  (the database), `digest.md` (the output), `.venv`, `.models`, `.session`.
- `PY` = the Python inside `WORK/.venv` (`bin/python`, or `Scripts\python.exe` on Windows).

## Step 0: setup (first run only)

Run `python3 SCRIPTS/setup_env.py` (`python` or `py` on Windows). It creates the venv
and prints `PY`. If `WORK/reels.json` already exists, run `PY SCRIPTS/db.py status`
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

Tell the user once, plainly: options 2 and 3 use their own logged-in session the way
a browser would; Instagram's terms don't allow automated access, so the scripts go
slowly and stop on the first sign of rate limiting. Option 1 has no such risk.

## Step 2: captions

`PY SCRIPTS/fetch_meta.py` (add `--browser chrome` if posts fail with login errors).
Skips posts that already have captions (live collection already includes them).
~3 s per post, so for 300 posts run it in the background and keep the user informed.
If it prints `STOPPED`, relay the reason; do not loop retries. Wait, or switch to `--browser`.

## Step 3: triage by topic (you do this)

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
Default model `small` (good for Spanish/English, ~460 MB once). On a slow machine
suggest `--model base`; with an NVIDIA GPU it uses it automatically. Roughly 10–30 s
per reel on CPU, so run in the background for big batches and report progress.
If many fail with login errors, retry with `--browser chrome`.

Then resolve maybes: `PY SCRIPTS/db.py next --maybe` shows them with transcripts;
set each to `true` or `false`.

## Step 5: merge duplicates and write the digest (you do this)

1. `PY SCRIPTS/db.py similar` gives candidate groups with the same wording. Then read
   everything: `PY SCRIPTS/db.py dump --undigested` (pipe to a file and read it in
   parts if it is long). Group by **meaning**, not wording: two creators explaining the
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

## <Category, e.g. Claude Code / Prompting / Agents / AI tools / Dev workflow>
### <Idea title> {#slug}
<2–4 sentence summary of the technique or insight, merged from all sources>
**How to apply:** concrete steps, commands, prompts or settings mentioned.
**Seen in N reels:** [@creator](url) · [@creator2](url)
**Notes:** contradictions, caveats, "probably outdated", "mostly hype" (only if any)
```

   Merged entries list every source reel. Entries backed by several creators are a
   signal, not proof; rank by usefulness, not by count.
4. Record which entry each reel went into (enables incremental runs):
   `PY SCRIPTS/db.py set entry <slug> CODE1 CODE2 ...`
5. On later runs, merge new reels into existing entries before creating new ones,
   and refresh the header counts and "Do these first".

## Finish

Tell the user in 2–3 lines: how many saves were read, how many were on topic, how
many unique ideas remained after merging, the path to `digest.md`, and the top 3
items. Offer one next step (e.g. "want me to apply #1 to this project?").

## Troubleshooting

- `STOPPED ... login/rate-limit`: Instagram wants a login or is throttling. Use
  `--browser <browser where they are logged in>`, or wait an hour. Never lower `--delay`
  below 2.
- Browser cookies unreadable (Chrome on Windows locks/encrypts them): close Chrome
  completely and retry, or use `--browser firefox`, or the official export.
- Export parse finds 0 links: they chose HTML or the wrong section; any file
  containing instagram.com/p|reel links works: `collect.py export path/to/file`.
- Private or deleted posts fail metadata; that is expected, they are skipped.
