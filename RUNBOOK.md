# The Dua Hour: DAILY top-up run (follow exactly)

Publer stays on the FREE plan (owner's decision, permanent): max 10 scheduled posts per social account.
So this run happens every day and tops the queue back up, one slot at a time, in plan order.

## Owner's rules (non-negotiable)
1. **Accuracy first.** These are duas from the Quran and Sunnah. If anything on screen, in the audio or in a caption
   might be wrong (wrong text for the title, cut-off text, wrong reference), do NOT schedule it. Skip it and report it.
2. LANDSCAPE (16:9) ONLY FOR VIDEOS OVER 5 MINUTES. Shorts and mids are portrait only, posted to Instagram, TikTok and YouTube.
   Format per week: 3 Shorts (up to about 30 s, portrait), 3 mid videos (1:00 to 1:30, portrait only),
   1 long video (about 10 minutes, landscape, one category only, every Sunday).
   During the Publer trial (up to and including 8 Dec 2026): 2 posts a day (08:00 and 19:00 UK).
   After the trial: 1 post a day at 19:00 UK (Mon short, Tue mid, Wed short, Thu mid, Fri short, Sat mid, Sun long).
3. Every 4 weeks: a 1-hour video combining that month's Shorts plus more duas, grouped by category
   (not mixed). Over 100 MB, so it cannot be hosted automatically: render it and tell the owner.
4. Style: dark tinted nature clip, Amiri Arabic, transliteration, English, "RECITED BY MUHAMMAD JUMAH",
   "THE DUA HOUR". Frame 0 is the thumbnail (no fade-in). Fade-out at the end. Quiet nature sound under the
   recitation (fire, rain, stream, birds, wind; 1 or 2 at random). Portrait text block is centred on the screen (x 540, y 960) inside y 480 to 1440 with about 170 px clear on each side (TikTok/Instagram buttons); never move it towards the top.
5. Captions: NO emojis, NO em or en dashes, MAX 5 hashtags, first line = YouTube title (max 95 characters),
   every title unique, and ALWAYS the line
   "If you notice any mistake or issue in this video, please contact us at tdh@reclaivo.com".
   Long videos list every dua with a timestamp in the description.
6. When every dua has been used, reuse them in a new random order (the planner does this).

## Accounts (use ONLY these)
- Zapier connector **ZapierTDH** (`mcp__ZapierTDH__*`). Never ZapierTQS or any other Zapier connector.
- Publer app `App232404CLIAPI`, connection **tdh@reclaivo.com**, workspace **TDH** `6b06453d20c12d0489e7764e`.
  Accounts: Instagram `6b0645f14e667d7eb997d0bf`, TikTok `6b064625e9a6a63318d8e109`, YouTube `6b06464ac225c1163f0ce0ef`.
- YouTube channel "The Dua Hour" UCPPR1ZnA7ti4-FvC1QItjlg.
- First call `mcp__ZapierTDH__list_zapier_connections` (selected_api `App232404CLIAPI`) and confirm the title is
  `tdh@reclaivo.com`. If not: STOP, post nothing, report it.

## Daily top-up steps
1. Setup (below, step 1 of the full steps).
2. Count scheduled posts per account with the ZapierTDH code action `list_scheduled_posts`
   (action `code_action_app232404cliapi__list_scheduled_posts`, workspace_id). Count only state `scheduled`.
3. Work through `pending.json` first, then the next planned videos in state.json (by `when`) that have no
   `scheduled` flag. For each slot whose `when` is in the future AND whose target accounts all have fewer than
   10 scheduled posts: render it if needed, visual check, publish.py, upload_media, create_post, then set
   `"scheduled": true` on that video in state.json (and remove it from pending.json). Stop when any needed
   account is full. If a slot's time has already passed, skip it and mark it `"skipped": "time passed"`.
4. If fewer than 7 unscheduled planned videos remain, plan the next week (`week.py plan`).
5. Commit state.json and pending.json to tdh-engine and push. Report in 3 lines: what was scheduled, what is
   queued next, any problem.

## Full steps (reference)
1. Setup: `git clone --depth 1 -b tdh-engine https://github.com/motivationreclaimed/tqs /home/claude/tdh_engine`
   then `bash /home/claude/tdh_engine/setup.sh` (links everything into /home/claude/dua_videos and /home/claude/opendua).
2. `cd /home/claude/dua_videos && python3 week.py plan <N> <first day YYYY-MM-DD>`: N is the next week number
   (one more than the highest `wN_` id in state.json); the first day is the day after the last scheduled `when`.
3. `python3 week.py render <N>` (about 40 min; run in chunks under 10 minutes with the ids if needed).
4. Visual check: grab frame 0 and a middle frame of every file in out_week<N>/ and Read them. Rule 1 applies.
5. `python3 publish.py <ids>` then, for each line of posts.json, via ZapierTDH (Publer):
   a. `upload_media`: workspace_id, upload_type `url`, file_urls `[url]` (ONE url per call), in_library `true`
      -> `results[0].payload[0].id`. If it says "not publicly accessible" for a github.io url, the Quran run
      overwrote Pages: run publish.py again for those ids and retry.
   b. `create_post`: workspace_id, text, account_ids, media_ids `[id]`, state `scheduled`, scheduled_at `when`.
   c. Check with the code action `list_scheduled_posts` that every post is there. Never create duplicates.
6. Commit state.json to the tdh-engine branch and push (`git push origin HEAD:tdh-engine`).
7. Report briefly: what was scheduled (title + time), anything skipped and why.

## Hosting
- Files < 19 MB: branch `tdh-media` (force-pushed per batch) served by jsDelivr pinned to the commit.
- Bigger files: GitHub Pages folder `tdh/` on the shared gh-pages branch. The Quran Sounds run force-pushes
  gh-pages, so upload to Publer right after publishing. Never touch the Quran files or its branches.

## Sources and credits
Arabic, transliteration and translation: OpenDua (CC BY 4.0). Recitation: Muhammad Jumah for OpenDua.
Book: Hisn al-Muslim by Sa'id bin Ali bin Wahf Al-Qahtani. Nature clips and sounds: Pexels / Pixabay (owner's downloads).
