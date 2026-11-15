# The Quran Sounds — scheduled run (follow exactly)

## The owner's non-negotiable rules
1. **Accuracy above everything.** This is the Holy Quran and a sensitive page. *If you have a gut feeling that the
   captions, text and the audio may be incorrect, you do not post it — you move to the next video. Even a slight
   feeling. Unless you have properly confirmed that everything is correct, do not post it.*
2. **Never stop.** Post every day. If the owner sends no new audio, keep reusing / recycling the surahs already in
   the library (a new cycle starts automatically with different background clips) — forever.
3. AUDIO = THE RECITATION ONLY. No music, no clip sound, no background noise — ever (checked automatically).
   Never post the identical video twice. Never cut a verse. Surah ≤ 1:10 → one Short of the whole surah; longer → ~30 s Shorts.
4. Shorts → YouTube + Instagram + TikTok as **ONE** Publer post. Long (16:9 full surah) → **YouTube only**, every 14 days.
5. Captions: NO emojis, NO em dashes, MAX 5 HASHTAGS (Instagram/TikTok limit). Surah, reciter, "beautiful Quran recitation" wording, the error-report email, hashtags (the code writes them).

## Accounts — use ONLY these
- Zapier: the **ZapierTQS** connector (`mcp__ZapierTQS__*`). NEVER the plain "Zapier" connector (another channel's).
- Publer app `App232404CLIAPI`, connection **tqs@reclaivo.com**, workspace **TQS** `6af8e43b1740237b1ce2be92`.
  Accounts: Instagram `6af8e513d185a8df1464578f`, TikTok `6af8e58de39d7f4bffa83578`, YouTube `6af8e6b029e54cb125a68757`.
- First call `mcp__ZapierTQS__list_zapier_connections` (selected_api `App232404CLIAPI`) and confirm the title is
  `tqs@reclaivo.com`. If ZapierTQS is missing, disabled or shows another account: STOP, post nothing, report it.

## Steps
1. `git clone --depth 1 --filter=blob:none https://github.com/motivationreclaimed/tqs /tmp/tqs && cd /tmp/tqs/engine`
   `git config user.name "The Quran Sounds"; git config user.email "tqs@reclaivo.com"`
2. `python3 run.py plan` — fills every empty slot for the next 5 days (renders each video, runs the accuracy
   self-check, publishes the batch on the `media` branch) and prints `plan.json` (`items`: unit, kind,
   scheduled_at, caption, publer_account_ids, video_url). If there are no items, the schedule is already full: done.
3. **Visual check (rule 1):** `python3 run.py sheet`, then Read `/tmp/tqs_out/sheet.png`. For every video confirm:
   the surah name + verse numbers on screen match its unit, Arabic and English are present and readable, nothing
   is cut off, no person/face or un-Islamic image in the background. Any doubt about an item → do not schedule it:
   `python3 run.py failed "<unit>" "<reason>"` and leave its slot for the next run.
4. For each approved item, via ZapierTQS (Publer):
   a. `execute_zapier_write_action` `upload_media`: workspace_id, upload_type `url`, file_urls `[video_url]`,
      in_library `true` → take `results[0].payload[0].id` (status should be `complete`).
   b. `execute_zapier_write_action` `create_post` — ONE call: workspace_id, text = caption,
      account_ids = publer_account_ids, media_ids = [media id], state `scheduled`, scheduled_at = item's scheduled_at.
   c. If a call **times out**, it may still have succeeded: check with `inspect_zapier_actions`
      (tool_name `publer_find_post`, enum_property `post_id`) for a post with this caption before retrying —
      never create duplicates.
   d. Success → `python3 run.py posted "<unit>" "<post ids>" --at "<scheduled_at>"`.
      Failure → `python3 run.py failed "<unit>" "<reason>"` (the slot is refilled next run with another video).
5. `cd /tmp/tqs && git add -A && git commit -m "Scheduled posts" && git push` (always push the log, even after failures).
6. Report briefly: what was scheduled (unit + time), anything skipped and why.

## YouTube long videos (15 Nov 2026)
YouTube removed the first long video "because it was too long": the channel was not verified, so the limit is 15 minutes.
Long videos are paused while config.json "youtube_long_ok" is false. Set it to true ONLY after the owner confirms
the channel is verified at youtube.com/verify. Ar-Rahman (Abdul Basit) never went public, so it is posted first after that.

## Changes 15 Nov 2026 (owner)
- Long video EVERY 7 DAYS (Sundays). After the trial: Shorts Mon-Fri 16:00 UTC + long on Sunday, Saturday off (about 5 Shorts + 1 long a week).
- Thumbnails: Publer/YouTube take FRAME 0. Videos no longer fade in from black. Long videos open on the title card
  (big Arabic name, SURAH NAME, reciter) over a mountain/tree clip (THUMB_CLIPS, no birds/animals). Shorts open on the first verse.
- Long videos are encoded in AV1 (Publer and YouTube accept it): about twice the quality of H.264 at the same file size (<95 MB).
- Do NOT add rain/nature sounds or anything else to the audio. Recitation only, always.
