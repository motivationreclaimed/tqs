# The Quran Sounds — scheduled run (follow exactly)

## The owner's non-negotiable rules
1. **Accuracy above everything.** This is the Holy Quran and a sensitive page. *If you have a gut feeling that the
   captions, text and the audio may be incorrect, you do not post it — you move to the next video. Even a slight
   feeling. Unless you have properly confirmed that everything is correct, do not post it.*
2. **Never stop.** Post every day. If the owner sends no new audio, keep reusing / recycling the surahs already in
   the library (a new cycle starts automatically with different background clips) — forever.
3. AUDIO = THE RECITATION ONLY. No music, no clip sound, no background noise — ever (checked automatically).
   Never post the identical video twice. Never cut a verse. Surah ≤ 1:10 → one Short of the whole surah; longer → ~30 s Shorts.
4. Shorts → YouTube + Instagram + TikTok as **ONE** Publer post. Long (16:9 full surah) → **YouTube only, uploaded
   directly with the YouTube connector** (title, SEO description, tags, reciter thumbnail), **every week on Sunday**.
4b. **NEVER post Abdul Basit** (strictly licensed). The code excludes him (`disabled_reciters`). If anything with
   "abdulbasit" ever appears in a plan: do not post it, report it.
4c. Half of the Shorts are 61 s or longer (they alternate automatically; `mode` 60 vs 30 in plan.json).
5. Captions: NO emojis, NO em dashes, MAX 5 HASHTAGS (Instagram/TikTok limit). Surah, reciter, "beautiful Quran recitation" wording, the error-report email, hashtags (the code writes them).

## Accounts — use ONLY these
- Zapier: the **ZapierTQS** connector (`mcp__ZapierTQS__*`). NEVER the plain "Zapier" connector (another channel's).
- Publer app `App232404CLIAPI`, connection **tqs@reclaivo.com**, workspace **TQS** `6af8e43b1740237b1ce2be92`.
  Accounts: Instagram `6af8e513d185a8df1464578f`, TikTok `6af8e58de39d7f4bffa83578`, YouTube `6af8e6b029e54cb125a68757`.
- YouTube app `YouTubeV4CLIAPI` (channel "The Quran Sounds", UCdTannqu76hMX-9phScnpEg): long videos only.
- First call `mcp__ZapierTQS__list_zapier_connections` (selected_api `App232404CLIAPI`) and confirm the title is
  `tqs@reclaivo.com`. If ZapierTQS is missing, disabled or shows another account: STOP, post nothing, report it.

## Steps
1. `git clone --depth 1 --filter=blob:none https://github.com/motivationreclaimed/tqs /tmp/tqs && cd /tmp/tqs/engine`
   `git config user.name "The Quran Sounds"; git config user.email "tqs@reclaivo.com"`
2. `python3 run.py plan` — fills every empty slot for the next 7 days (renders each video, runs the accuracy
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
6. **Long video (only in the Wednesday/Thursday runs; skip on other days):** `python3 run.py long`.
   If it prints SKIP, there is nothing to do. Otherwise it rendered the coming Sunday's long video and its thumbnail
   and wrote `/tmp/tqs_out/long.json` (`publish_at`, items[0]: unit, video_url, thumbnail_url, title, description, tags).
   a. Visual check: grab 3 frames (start, middle, end) of items[0].file and Read the thumbnail; same rule-1 checks.
   b. ZapierTQS YouTube (`YouTubeV4CLIAPI`) `upload_video`: title, description, video = video_url,
      thumbnail = thumbnail_url, tags, privacy_status **private**, category_id `27` (Education),
      default_language `en`, default_audio_language `ar`, made_for_kids `false`, notify_subscribers `true`.
      Timeout → check with `find_video` (channel UCdTannqu76hMX-9phScnpEg) before retrying. Never duplicate.
   c. If the thumbnail was not applied, `upload_video_thumbnail` (video_id, thumbnail = thumbnail_url).
   d. `python3 run.py uploaded_private "<unit>" "<youtube video id>" "<publish_at>"`, then commit + push.
   The Sunday task makes it public at publish_at (`python3 run.py to_publish` lists it).
7. Report briefly: what was scheduled (unit + time), anything skipped and why.

## Sunday: make the week's long video public
`python3 run.py to_publish` → for each item: ZapierTQS YouTube `_zap_raw_request`, method PUT,
url `https://www.googleapis.com/youtube/v3/videos?part=status`, fail_on_errors true, body
`{"id":"<youtube_id>","status":{"privacyStatus":"public","embeddable":true,"publicStatsViewable":true,"selfDeclaredMadeForKids":false}}`
→ then `python3 run.py made_public "<unit>"`, commit + push. If it fails, report it: the owner can switch it to Public in YouTube Studio.

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

## Changes 20 Nov 2026
- Abdul Basit is never posted again (strictly licensed). Only reciters in the library minus `disabled_reciters`.
- Half of the Shorts are 61 s or longer (alternating), for TikTok monetisation.
- Publer's free plan allows at most 10 scheduled posts per account: `plan` only fills up to that. Runs on Sunday and
  Wednesday keep it topped up. "free plan allows up to 10 scheduled posts" from Publer = schedule is full: stop, not an error.
- Video hosting: Publer can no longer download raw.githubusercontent.com links. `publish_batch` force-pushes the batch to
  the `gh-pages` branch and returns https://motivationreclaimed.github.io/tqs/<file> URLs (it waits 90 s for Pages).
- Renderer fix: Shorts that start mid-surah had the audio 0.55 s early (caught by the audio check, never posted). Fixed.

## 25 Nov 2026 (owner): reciters
Only Mahmoud Khalil Al-Husary, Muhammad Siddiq Al-Minshawi and Abu Bakr Al-Shatri are used, for Shorts and long videos
(`disabled_reciters`: mishary, abdulbasit_mujawwad). Hani Ar-Rifai failed verification (verse ends not on pauses).
Long-video thumbnails for these reciters have no photo (text only). The Mishary Ar-Rahman long video (V1RxExsYOnQ)
stays PRIVATE and must never be made public.
- Long videos over 25 minutes are rendered in CALM mode (backgrounds 2.5x slower, 12 fps, 720p, AAC 96k) so the
  full surah fits the 100 MB hosting limit with sharp text. Owner wants full length, fully automatic.

## 27 Nov 2026 (owner): current rules, these override older sections
- Reciters: ONLY Mishary Alafasy and Abdul Basit (every Quran.com reciter tested got blocked). Others are in
  `disabled_reciters`.
- Shorts only, about 30 s (`force_short_mode` 30). NO long / 16:9 videos (`youtube_long_ok` false): skip step 6
  (`run.py long` prints SKIP) and the Sunday publish task has nothing to do.
- A Short longer than 40 s goes to Instagram + TikTok only (plan.json `publer_account_ids` already leaves YouTube out).
- Never repeat verses already posted (any reciter): `next_unit` picks units with no verse that was posted before.
- 27 Nov 2026 (owner): ALL audio must have a strong echo. render.py `ECHO` adds it; the audio check compares the video
  against the original recitation with the same echo, so anything else added still fails.
