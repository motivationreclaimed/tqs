# The Quran Sounds — daily run (for the scheduled Claude session)

Follow exactly. This is religious scripture: accuracy beats everything. If anything is unclear or any
check fails, do not post that video — use the next one, and report.

## Accounts — use ONLY these
- Zapier: the **ZapierTQS** connector (tools `mcp__ZapierTQS__*`). NEVER the plain "Zapier" connector
  (that belongs to a different channel).
- Publer app `App232404CLIAPI`, connection **tqs@reclaivo.com**, workspace **TQS** (`6af8e43b1740237b1ce2be92`).
- Before posting, confirm with `mcp__ZapierTQS__list_zapier_connections` (selected_api `App232404CLIAPI`)
  that the connection title is `tqs@reclaivo.com`. If not, STOP and report.

## Steps
1. Clone: `git clone --depth 1 https://github.com/motivationreclaimed/tqs /tmp/tqs && cd /tmp/tqs/engine`
   Set git identity: `git config user.name "The Quran Sounds"; git config user.email "tqs@reclaivo.com"`.
2. `python3 run.py prepare` (decides Short vs long by the schedule, renders, uploads to the `videos` release).
   It prints JSON with `unit`, `video_url`, `caption`, `title`, `publer_account_ids`.
   If it exits with `STOP`, do not post; report.
3. Publer via ZapierTQS:
   a. `execute_zapier_write_action` App232404CLIAPI `upload_media`:
      workspace_id = `6af8e43b1740237b1ce2be92`, upload_type `url`, file_urls = [video_url], in_library true.
      Get the media id from the result (if the media is still processing, wait ~1 min and use `find_media`).
   b. `execute_zapier_write_action` App232404CLIAPI `create_post` — ONE post:
      workspace_id as above, text = caption, account_ids = publer_account_ids, media_ids = [media id],
      state `published`.
4. On success: `python3 run.py posted "<unit>" "<publer post id or ref>"`, then
   `git add -A && git commit -m "Posted <unit>" && git push`.
5. On failure: `python3 run.py failed "<unit>" "<reason>"`, then
   `python3 run.py prepare --skip "<unit>"` and repeat step 3 once with the new video. Commit + push the log
   either way. Never leave the day without a post if any video can be posted.

## Rules (from the channel owner)
- Whole verses only; never cut a verse. Text and timings come from Tanzil + Quran.com (verified, checksummed).
- Surah ≤ 1:10 → one Short of the whole surah; longer → ~30 s Shorts.
- Shorts → YouTube + Instagram + TikTok in ONE Publer post. Long (16:9 full surah) → YouTube only, every 14 days.
- Never post an identical video twice. When everything is used, a new cycle starts (new background clips).
- Captions always: surah, reciter, "beautiful Quran recitation"-style wording, the error-report email, hashtags.
- The schedule must never stop.
