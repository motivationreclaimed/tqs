"""The Quran Sounds — daily runner.

  python3 engine/run.py status                 # what's next, counts, schedule
  python3 engine/run.py prepare [--kind auto|short|long] [--skip UNIT ...]
        -> renders the next video, uploads it to the GitHub 'videos' release, writes /tmp/tqs_out/next.json
           (unit, caption, video_url, publer account ids). Prints that JSON.
  python3 engine/run.py posted UNIT POST_REF    # record a successful post (then commit + push the repo)
  python3 engine/run.py failed UNIT REASON      # record a failed attempt (unit is retried later; a different one is used now)

Rules (from the channel owner): whole verses only; surah <= 70 s -> one Short of the whole surah, otherwise ~30 s Shorts;
Shorts to YouTube + Instagram + TikTok as ONE Publer post; long video (16:9, whole surah) to YouTube only every 14 days;
never post the identical video twice — when everything is used, start a new cycle (different background clips);
the schedule must never stop.
"""
import datetime as dt, hashlib, json, os, random, subprocess, sys
from pathlib import Path
from qlib import ROOT, DATA, STATE, CACHE, OUT, REPO, RECITERS, NAMES, MEANINGS
import render

CFG = json.loads((ROOT / "config.json").read_text())
LOG_P = STATE / "posted.json"


def load_log():
    return json.loads(LOG_P.read_text()) if LOG_P.exists() else {"posts": [], "failures": [], "short_cycle": 1, "long_cycle": 1}


def save_log(log):
    LOG_P.write_text(json.dumps(log, indent=1, ensure_ascii=False))


# ---------------- library ----------------
def surahs():
    """verified (reciter, surah) pairs, with verse timings, honouring HOLD notes."""
    out = []
    off = set(CFG.get("disabled_reciters", []))   # e.g. Abdul Basit: strictly licensed, never posted again
    for rk in sorted(p.name for p in DATA.iterdir() if p.is_dir() and p.name in RECITERS and p.name not in off):
        for sd in sorted((DATA / rk).iterdir()):
            appr = json.loads((sd / "approval.json").read_text()) if (sd / "approval.json").exists() else {}
            if appr.get("hold_verses"):
                continue  # something still needs the owner's confirmation -> never used
            ts = json.load(open(sd / "timings.json"))["audio_file"]["timestamps"]
            out.append({"reciter": rk, "surah": int(sd.name), "ts": ts, "dir": sd})
    return out


def short_units(item, mode=30):
    """mode 30: ~30 s Shorts (whole surah if <= 70 s). mode 60: Shorts of at least 61 s (TikTok monetisation needs
    > 1 minute) made of whole verses; surahs shorter than 61 s have no 60-mode Short."""
    ts = item["ts"]; d = [(t["timestamp_to"] - t["timestamp_from"]) / 1000 for t in ts]; n = len(ts)
    if mode == 60:
        mn = CFG.get("long_short_min_seconds", 61)
        if sum(d) < mn:
            return []
        if sum(d) <= CFG.get("long_short_max_seconds", 100):
            return [(1, n)]
        units, start, cur = [], 1, 0.0
        for i, x in enumerate(d, 1):
            cur += x
            if cur >= mn:
                units.append([start, i]); start, cur = i + 1, 0.0
        if start <= n:                       # leftover shorter than 61 s joins the previous Short
            if units: units[-1][1] = n
            else: units.append([start, n])
        return [tuple(u) for u in units]
    if sum(d) <= CFG["one_short_max_seconds"]:
        return [(1, n)]
    units, start, cur = [], 1, 0.0
    for i, x in enumerate(d, 1):
        if cur > 0 and cur + x > CFG["short_target_seconds"] + 4:
            units.append((start, i - 1)); start, cur = i, 0.0
        cur += x
    units.append((start, n))
    return units


def short_sequence(mode=30):
    """Interleave surahs/reciters (round-robin) so the feed stays varied; each surah advances in order."""
    streams = []
    for it in surahs():
        s = [f"short:{it['reciter']}:{it['surah']}:{a}-{b}" for a, b in short_units(it, mode)]
        if s: streams.append(s)
    order = CFG.get("stream_priority", [])
    streams.sort(key=lambda s: (order.index(":".join(s[0].split(":")[1:3])) if ":".join(s[0].split(":")[1:3]) in order else 99))
    seq = []
    while any(streams):
        for s in streams:
            if s: seq.append(s.pop(0))
    return seq


def long_sequence():
    have = {f"{i['reciter']}:{i['surah']}" for i in surahs()}
    return [f"long:{k}" for k in CFG["long_order"] if k in have]


# ---------------- choosing ----------------
def next_unit(kind, skip=(), mode=30):
    log = load_log()
    if kind == "short":
        ck = "short_cycle" if mode == 30 else "short60_cycle"
        seq, cyc = short_sequence(mode), log.get(ck, 1)
        done = {p["unit"] for p in log["posts"] if p["unit"].startswith("short:") and p.get("mode", 30) == mode and p["cycle"] == cyc}
    else:
        ck = "long_cycle"
        seq, cyc = long_sequence(), log["long_cycle"]
        done = {p["unit"] for p in log["posts"] if p["unit"].startswith("long:") and p["cycle"] == cyc}
    if not seq:
        raise RuntimeError(f"no {kind} units available (mode {mode})")
    todo = [u for u in seq if u not in done and u not in skip]
    if not todo:  # everything used: new cycle — same audio, new background clips, so never an identical video
        log[ck] = cyc + 1; save_log(log)
        return next_unit(kind, skip, mode)
    return todo[0], cyc


def next_short_mode():
    """Half of the Shorts are 60 s+: alternate with the most recent Short."""
    shorts = sorted((p for p in load_log()["posts"] if p["unit"].startswith("short:")), key=lambda p: p.get("scheduled_at") or p["date"])
    return 30 if shorts and shorts[-1].get("mode", 30) == 60 else 60


def long_due(day=None):
    day = day or dt.date.today()
    longs = [p for p in load_log()["posts"] if p["unit"].startswith("long:")]
    if not longs:
        return day >= dt.date.fromisoformat(CFG["first_long_date"])
    last = max(dt.date.fromisoformat((p.get("scheduled_at") or p["date"])[:10]) for p in longs)
    return (day - last).days >= CFG["long_every_days"]


def slot_times(start, end):
    d = start.date()
    while d <= end.date():
        trial = d <= dt.date.fromisoformat(CFG["trial_until"])
        times = CFG["slots_utc_trial"] if trial else CFG["slots_utc"]
        if not trial and d.weekday() not in CFG.get("post_days", range(7)):
            times = []   # after the trial: 5 Shorts (Mon-Fri) + 1 long (Sunday) a week
        for hm in times:
            t = dt.datetime.combine(d, dt.time(*map(int, hm.split(":"))), tzinfo=dt.timezone.utc)
            if start <= t <= end:
                yield t
        d += dt.timedelta(days=1)


# ---------------- assets ----------------
def gh(*args, **kw):
    return subprocess.run(["gh", *args], check=True, text=True, capture_output=True, **kw).stdout


def asset(name):
    """Audio/clips live in the repo (audio/, clips/); files >95 MB are stored as byte-exact .partNN pieces.
    Works with a full or a partial (--filter=blob:none) clone: blobs are fetched on demand."""
    p = CACHE / name
    if p.exists():
        return p
    folder = "clips" if name.startswith("clip-") else "audio"
    files = subprocess.run(["git", "-C", str(ROOT), "ls-tree", "--name-only", "HEAD", f"{folder}/"],
                           check=True, text=True, capture_output=True).stdout.split()
    parts = sorted(f for f in files if f == f"{folder}/{name}" or f.startswith(f"{folder}/{name}.part"))
    if not parts:
        raise SystemExit(f"STOP: asset {name} not found in repo")
    with open(p, "wb") as out:
        for f in parts:
            out.write(subprocess.run(["git", "-C", str(ROOT), "show", f"HEAD:{f}"], check=True, capture_output=True).stdout)
    return p


def publish_video(path):
    """Put the video alone on the orphan 'media' branch (force-pushed, so the repo never grows) -> public URL."""
    import shutil, tempfile
    d = Path(tempfile.mkdtemp())
    run = lambda *a: subprocess.run(["git", *a], cwd=d, check=True, capture_output=True, text=True)
    run("init", "-q"); run("checkout", "-q", "--orphan", "media")
    shutil.copy(path, d / Path(path).name)
    run("add", "."); run("-c", "user.name=The Quran Sounds", "-c", "user.email=tqs@reclaivo.com", "commit", "-qm", "media")
    remote = subprocess.run(["git", "-C", str(ROOT), "remote", "get-url", "origin"], check=True, capture_output=True, text=True).stdout.strip()
    run("push", "-f", remote, "media")
    return f"https://raw.githubusercontent.com/{REPO}/media/{Path(path).name}"


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""): h.update(b)
    return h.hexdigest()


THUMB_CLIPS = ["clip-05.mp4", "clip-06.mp4", "clip-07.mp4", "clip-19.mp4", "clip-20.mp4", "clip-22.mp4", "clip-25.mp4"]
# ^ simple mountains/trees, no birds or animals: the first scene of a long video, because frame 0 is the thumbnail


def clip_picker(vertical):
    clips = [c for c in json.loads((DATA / "clips.json").read_text()) if c["vertical_ok"] or not vertical]
    deck_p = STATE / ("deck_v.json" if vertical else "deck_h.json")
    thumb_p = STATE / "deck_thumb.json"
    first = [not vertical]
    def pick():
        names = {c["name"]: c for c in clips}
        deck = [n for n in (json.loads(deck_p.read_text()) if deck_p.exists() else []) if n in names]
        if not deck:
            deck = list(names); random.shuffle(deck)
        if first[0]:
            first[0] = False
            td = [n for n in (json.loads(thumb_p.read_text()) if thumb_p.exists() else []) if n in names]
            if not td:
                td = [n for n in THUMB_CLIPS if n in names]; random.shuffle(td)
            n = td.pop(0); thumb_p.write_text(json.dumps(td))
            if n in deck: deck.remove(n)
        else:
            n = deck.pop(0)
        deck_p.write_text(json.dumps(deck))
        return str(asset(n)), names[n]["seconds"]
    return pick


# ---------------- captions ----------------
def caption(kind, rk, S, A, B):
    rname, sname, mean = RECITERS[rk]["name"], NAMES[S - 1], MEANINGS.get(S, "")
    rtag = {"mishary": "#MisharyAlafasy", "abdulbasit_mujawwad": "#AbdulBasit"}.get(rk, "")
    stag = "#Surah" + sname.replace("-", "").replace("'", "")
    ref = f"{S}:{A}-{B}" if A != B else f"{S}:{A}"
    if kind == "short":
        head = f"Surah {sname} ({ref}) | {rname}"
        body = (f"Beautiful Quran recitation of Surah {sname}{f' ({mean})' if mean and mean != sname else ''} by {rname}, with Arabic text and English "
                f"translation (Saheeh International). A soothing recitation to listen, reflect and find peace.")
        tags = f"#Quran #QuranRecitation {stag} {rtag} #Islam"
    else:
        head = f"Surah {sname} (Full) | {rname} | Beautiful Quran Recitation with English Translation"
        if len(head) > 95: head = f"Surah {sname} (Full) | {rname} | Beautiful Quran Recitation"
        body = (f"The complete Surah {sname} ({mean}), surah {S} of the Holy Quran, in a beautiful and emotional "
                f"recitation by {rname}. Follow along with the Arabic text and English translation (Saheeh "
                f"International). A soothing, peaceful Quran recitation for reflection, relaxation, study and sleep.")
        tags = f"#Quran #QuranRecitation {stag} {rtag} #Islam"
    contact = f"If you notice any error in this video, please let us know: {CFG['contact_email']}"
    text = f"{head}\n\n{body}\n\n{contact}\n\n{tags}"
    assert len(text.split("\n")[0]) <= 95, "YouTube title (first line) must stay under 100 characters"
    assert text.count("#") <= 5, "max 5 hashtags (Instagram/TikTok limit)"
    import re as _re
    assert not _re.search("[\u2014\u2013\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0F]", text), "no emojis or dashes"
    return text


# ---------------- commands ----------------
def prepare(kind="auto", skip=()):
    if kind == "auto":
        kind = "long" if long_due() else "short"
    unit, cyc = next_unit(kind, skip)
    parts = unit.split(":"); rk, S = parts[1], int(parts[2])
    sd = DATA / rk / f"{S:03d}"
    appr = json.loads((sd / "approval.json").read_text()) if (sd / "approval.json").exists() else {}
    ts = json.load(open(sd / "timings.json"))["audio_file"]["timestamps"]
    A, B = (map(int, parts[3].split("-")) if kind == "short" else (1, len(ts)))
    A, B = int(A), int(B)
    audio = asset(f"audio-{rk}-{S:03d}.mp3")
    if appr.get("sha256") and sha256(audio) != appr["sha256"]:
        raise SystemExit(f"STOP: audio for {rk} {S} does not match the verified file (checksum)")
    out = OUT / f"tqs-{kind}-{rk}-{S:03d}-{A}-{B}-c{cyc}-{dt.datetime.now(dt.timezone.utc):%Y%m%d%H%M}.mp4"
    pre = ROOT / "prerendered" / f"{unit.replace(':', '-')}.mp4"
    if kind == "long" and pre.exists() and cyc == 1:
        import shutil; shutil.copy(pre, out)          # made in advance (long renders take a while)
        info = {"seconds": None, "verses": f"{S}:{A}-{B}", "clips": ["prerendered"]}
    else:
        info = render.render(kind, S, A, B, sd / "timings.json", audio, out, RECITERS[rk]["name"],
                             clip_picker(kind == "short"))
    if out.stat().st_size > 95e6:
        raise SystemExit(f"STOP: {out.name} is {out.stat().st_size/1e6:.0f} MB (> GitHub's 100 MB limit)")
    url = publish_video(out)
    acc = CFG["publer"]["short_account_ids"] if kind == "short" else [CFG["publer"]["youtube_account_id"]]
    nxt = {"unit": unit, "cycle": cyc, "kind": kind, "video_url": url, "file": str(out), "caption": caption(kind, rk, S, A, B),
           "title": f"Surah {NAMES[S-1]} ({S}:{A}-{B}) | {RECITERS[rk]['name']}" if kind == "short"
                    else f"Surah {NAMES[S-1]} (Full) | {RECITERS[rk]['name']} | Beautiful Quran Recitation",
           "publer_workspace_id": CFG["publer"]["workspace_id"], "publer_account_ids": acc, **info}
    (OUT / "next.json").write_text(json.dumps(nxt, indent=1, ensure_ascii=False))
    print(json.dumps(nxt, indent=1, ensure_ascii=False))


def posted(unit, ref, at=None):
    log = load_log(); kind = unit.split(":")[0]
    mode = 30
    for f in ("plan.json", "long.json"):
        p = OUT / f
        if p.exists():
            for it in json.loads(p.read_text()).get("items", []):
                if it["unit"] == unit: mode = it.get("mode", 30); cyc_from_plan = it.get("cycle")
    cyc = log.get("short60_cycle", 1) if (kind == "short" and mode == 60) else (log["short_cycle"] if kind == "short" else log["long_cycle"])
    entry = {"unit": unit, "mode": mode, "cycle": cyc, "date": dt.date.today().isoformat(),
             "time_utc": dt.datetime.now(dt.timezone.utc).strftime("%H:%M"), "ref": ref}
    if at:
        entry["scheduled_at"] = at
    log["posts"].append(entry)
    save_log(log); print("recorded", unit)


def self_check(audio, ts, A, B):
    """Re-confirm from the audio itself that every verse boundary in this video sits on a pause and that the
    recording is the length the timings describe. Any doubt -> raise (the video is not used)."""
    import numpy as np
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(audio), "-ac", "1", "-ar", "2000", "-f", "s16le", "-"],
                         check=True, capture_output=True).stdout
    x = np.frombuffer(raw, np.int16).astype(float); w = 100; n = len(x) // w
    db = 20 * np.log10(np.sqrt((x[:n * w].reshape(n, w) ** 2).mean(1)) + 1); med = np.median(db)
    if abs(len(x) / 2000 - ts[-1]["timestamp_to"] / 1000) > 1.0:
        raise RuntimeError("audio length does not match timings")
    bounds = [ts[v - 1]["timestamp_to"] for v in range(A, B + 1)]
    if ts[A - 1]["timestamp_from"] > 0: bounds.append(ts[A - 1]["timestamp_from"])
    for b in bounds:
        i = int(b / 50)
        seg = db[max(0, i - 6):i + 6]
        if len(seg) and med - seg.min() < 15:
            raise RuntimeError(f"verse boundary at {b/1000:.2f}s is not on a pause")


def audio_purity(video, audio, ts, A, B, lead):
    """The video's sound must be the recitation and NOTHING else (no music, no clip sound, no noise)."""
    import numpy as np
    def pcm(src, ss=0, t=None):
        cmd = ["ffmpeg", "-loglevel", "error", "-ss", str(ss), "-i", str(src)] + (["-t", str(t)] if t else []) + \
              ["-ac", "1", "-ar", "16000", "-f", "s16le", "-"]
        return np.frombuffer(subprocess.run(cmd, capture_output=True, check=True).stdout, np.int16).astype(float)
    streams = subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index",
                                       "-of", "csv=p=0", str(video)]).split()
    if len(streams) != 1:
        raise RuntimeError(f"video has {len(streams)} audio tracks (must be exactly 1: the recitation)")
    a0, a1 = ts[A - 1]["timestamp_from"] / 1000, ts[B - 1]["timestamp_to"] / 1000
    a = pcm(audio, a0, a1 - a0); v = pcm(video)
    L = int(lead * 16000); seg = v[L:L + len(a)]; n = min(len(seg), len(a)); seg, a = seg[:n], a[:n]
    def score(x, ref):
        m = min(len(x), len(ref)); x, ref = x[:m], ref[:m]
        r = x - (x @ ref) / (ref @ ref) * ref
        return np.corrcoef(x, ref)[0, 1], 20 * np.log10(np.sqrt((ref ** 2).mean()) / (np.sqrt((r ** 2).mean()) + 1e-9))
    corr, extra_db = score(seg, a)
    # reference: the ORIGINAL recitation alone, compressed the same way as the video's audio track.
    # The video must match it as closely as the reference does -> any added sound shows up as a gap.
    br = subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=bit_rate",
                                  "-of", "csv=p=0", str(video)]).decode().strip()
    br = int(br) if br.isdigit() else 192000
    import tempfile
    ref_p = tempfile.mktemp(suffix=".m4a")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", str(a0), "-i", str(audio), "-t", str(a1 - a0),
                    "-c:a", "aac", "-b:a", str(br), ref_p], check=True)
    b_corr, b_db = score(pcm(ref_p), a)
    lead_db = 20 * np.log10(np.sqrt((v[:max(1, L - 800)] ** 2).mean()) + 1)
    if corr < 0.99 or corr < b_corr - 0.0005 or extra_db < b_db - 1.0 or lead_db > 6:
        raise RuntimeError(f"audio is not the pure recitation (corr {corr:.4f} vs reference {b_corr:.4f}, "
                           f"difference {extra_db:.1f} dB vs reference {b_db:.1f} dB, lead-in {lead_db:.1f} dB)")
    return {"corr": round(corr, 4), "ref_corr": round(b_corr, 4), "diff_db": round(extra_db, 1), "ref_db": round(b_db, 1)}


def make(kind, unit, cyc):
    parts = unit.split(":"); rk, S = parts[1], int(parts[2])
    sd = DATA / rk / f"{S:03d}"
    appr = json.loads((sd / "approval.json").read_text()) if (sd / "approval.json").exists() else {}
    ts = json.load(open(sd / "timings.json"))["audio_file"]["timestamps"]
    A, B = (tuple(map(int, parts[3].split("-"))) if kind == "short" else (1, len(ts)))
    audio = asset(f"audio-{rk}-{S:03d}.mp3")
    if appr.get("sha256") and sha256(audio) != appr["sha256"]:
        raise RuntimeError(f"audio checksum mismatch for {rk} {S}")
    self_check(audio, ts, A, B)
    out = OUT / f"tqs-{kind}-{rk}-{S:03d}-{A}-{B}-c{cyc}-{dt.datetime.now(dt.timezone.utc):%Y%m%d%H%M%S}.mp4"
    pre = ROOT / "prerendered" / f"{unit.replace(':', '-')}.mp4"
    if kind == "long" and pre.exists() and cyc == 1:
        import shutil; shutil.copy(pre, out)
    else:
        render.render(kind, S, A, B, sd / "timings.json", audio, out, RECITERS[rk]["name"], clip_picker(kind == "short"))
    audio_purity(out, audio, ts, A, B, 0.6 if kind == "short" else (5.6 if S in (1, 9) else 10.6))
    if out.stat().st_size > 95e6:
        raise RuntimeError(f"{out.name} is {out.stat().st_size/1e6:.0f} MB (> 100 MB limit)")
    acc = CFG["publer"]["short_account_ids"] if kind == "short" else [CFG["publer"]["youtube_account_id"]]
    return {"unit": unit, "kind": kind, "file": str(out), "caption": caption(kind, rk, S, A, B), "publer_account_ids": acc}


def plan_batch(max_items=14):
    """Fill every empty posting slot from ~30 min from now until schedule_ahead_days. Renders the videos,
    publishes them together on the media branch and writes /tmp/tqs_out/plan.json."""
    log = load_log()
    taken = {(p.get("scheduled_at") or "")[:16] for p in log["posts"]}
    now = dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=30)
    end = now + dt.timedelta(days=CFG["schedule_ahead_days"])
    items, used = [], set()
    # Publer free plan: at most 10 scheduled posts per account at a time
    pending = sum(1 for p in log["posts"] if p["unit"].startswith("short:") and (p.get("scheduled_at") or "") > now.strftime("%Y-%m-%dT%H:%M"))
    max_items = min(max_items, CFG.get("publer_max_scheduled", 10) - pending)
    mode = next_short_mode()
    for t in slot_times(now, end):
        key = t.strftime("%Y-%m-%dT%H:%M")
        if key in taken or len(items) >= max_items:
            continue
        # long videos are NOT planned here: they go straight to YouTube (python3 run.py long)
        it = None
        for m in (mode, 90 - mode):          # if one length fails or has nothing, use the other
            try:
                unit, cyc = next_unit("short", skip=used, mode=m)
                it = make("short", unit, cyc); it["mode"], it["cycle"] = m, cyc
                break
            except Exception as e:  # never stop: record it and try the other kind of Short
                failed(f"short{m}-render", str(e))
        if it is None:
            continue
        mode = 90 - it["mode"]
        used.add(it["unit"]); it["scheduled_at"] = t.strftime("%Y-%m-%dT%H:%M:00Z"); items.append(it)
    if items:
        urls = publish_batch([i["file"] for i in items])
        for i, u in zip(items, urls): i["video_url"] = u
    plan = {"workspace_id": CFG["publer"]["workspace_id"], "items": items}
    (OUT / "plan.json").write_text(json.dumps(plan, indent=1, ensure_ascii=False))
    print(json.dumps(plan, indent=1, ensure_ascii=False))


def publish_batch(paths):
    """All of this batch's videos together on the orphan 'media' branch (force-pushed; repo never grows)."""
    import shutil, tempfile
    d = Path(tempfile.mkdtemp())
    run = lambda *a: subprocess.run(["git", *a], cwd=d, check=True, capture_output=True, text=True)
    run("init", "-q"); run("checkout", "-q", "--orphan", "media")
    for p in paths: shutil.copy(p, d / Path(p).name)
    run("add", "."); run("-c", "user.name=The Quran Sounds", "-c", "user.email=tqs@reclaivo.com", "commit", "-qm", "media")
    remote = subprocess.run(["git", "-C", str(ROOT), "remote", "get-url", "origin"], check=True, capture_output=True, text=True).stdout.strip()
    (d / ".nojekyll").write_text(""); (d / "index.html").write_text("ok")
    run("add", "."); run("-c", "user.name=The Quran Sounds", "-c", "user.email=tqs@reclaivo.com", "commit", "-qm", "pages")
    run("push", "-f", remote, "media:gh-pages")
    # Publer cannot download from raw.githubusercontent.com any more (Nov 2026): files are served by GitHub Pages.
    import time, urllib.request
    owner, name = REPO.split("/")
    urls = [f"https://{owner}.github.io/{name}/{Path(p).name}" for p in paths]
    time.sleep(90)   # Pages needs about a minute to deploy
    return urls


def sheet():
    """One image: two frames from every planned video, labelled, for a visual check before scheduling."""
    from PIL import Image, ImageDraw
    plan = json.loads((OUT / "plan.json").read_text()); tiles = []
    for it in plan["items"]:
        dur = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", it["file"]]))
        for f in (0.25, 0.75):
            p = OUT / f"_f{len(tiles)}.png"
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{dur*f:.2f}", "-i", it["file"], "-frames:v", "1",
                            "-vf", "scale=-2:420", str(p)], check=True)
            tiles.append((Image.open(p), it["unit"]))
    W = sum(t[0].width for t in tiles[:6]) or 1
    rows = [tiles[i:i + 6] for i in range(0, len(tiles), 6)]
    g = Image.new("RGB", (max(sum(t[0].width for t in r) for r in rows), 440 * len(rows)), "white"); d = ImageDraw.Draw(g)
    for r, row in enumerate(rows):
        x = 0
        for im, u in row:
            g.paste(im, (x, r * 440 + 20)); d.text((x + 4, r * 440 + 4), u, fill="black"); x += im.width
    g.save(OUT / "sheet.png"); print(OUT / "sheet.png")


def failed(unit, reason):
    log = load_log()
    log["failures"].append({"unit": unit, "date": dt.date.today().isoformat(), "reason": reason[:300]})
    save_log(log); print("failure recorded", unit)


def status():
    log = load_log(); s, l = short_sequence(), long_sequence()
    print(json.dumps({"shorts_per_cycle": len(s), "longs_per_cycle": len(l), "posted": len(log["posts"]),
                      "short_cycle": log["short_cycle"], "long_cycle": log["long_cycle"],
                      "next_short": next_unit("short")[0], "next_long": next_unit("long")[0],
                      "long_due_today": long_due()}, indent=1))


# ---------------- long video: straight to YouTube (SEO title, description, tags, reciter thumbnail) ----------------
def youtube_meta(rk, S, n_verses):
    rname, sname, mean = RECITERS[rk]["name"], NAMES[S - 1], MEANINGS.get(S, "")
    m = f" ({mean})" if mean and mean != sname else ""
    title = caption("long", rk, S, 1, n_verses).split("\n")[0]
    assert len(title) <= 95
    desc = (f"Listen to the complete Surah {sname}{m}, surah {S} of the Holy Quran, recited beautifully by {rname}. "
            f"All {n_verses} verses are shown with the Arabic text and the English translation (Saheeh International), "
            f"so you can follow every word while you listen.\n\n"
            f"A calm, soothing Quran recitation for reflection, study, relaxation and sleep, set against peaceful nature scenes.\n\n"
            f"Surah: {sname}{m}\nSurah number: {S}\nVerses: {n_verses}\nReciter: {rname}\n"
            f"Translation: Saheeh International\n\n"
            f"Subscribe to The Quran Sounds for beautiful Quran recitations every day.\n\n"
            f"If you notice any error in this video, please let us know: {CFG['contact_email']}\n\n"
            f"#Quran #Surah{sname.replace('-', '').replace(chr(39), '')} #QuranRecitation")
    short = {"mishary": "Mishary Alafasy"}.get(rk, rname)
    tags = [f"Surah {sname}", f"Surah {sname} full", f"{sname} recitation", f"Surah {sname} {short}", rname, short,
            "Quran", "Quran recitation", "beautiful Quran recitation", "Quran with English translation",
            "Holy Quran", "Quran for sleep", "relaxing Quran", "Islam", "The Quran Sounds"]
    from qlib import ARABIC_NAMES
    popular = {1: "Surah Fatiha", 2: "Surah Baqarah", 18: "Surah Kahf", 36: "Surah Yaseen", 55: "Surah Rahman",
               56: "Surah Waqiah", 67: "Surah Mulk", 112: "Surah Ikhlas", 113: "Surah Falaq", 114: "Surah Nas"}
    if S in popular: tags.insert(2, popular[S])   # the spelling most people actually search for
    if S in ARABIC_NAMES: tags.insert(2, ARABIC_NAMES[S])
    while len(",".join(tags)) > 480: tags.pop()
    assert not __import__("re").search("[\u2014\u2013\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0F]", desc + title)
    return title, desc, tags


def long_job():
    """Render the due long video + its thumbnail, host both, write /tmp/tqs_out/long.json for the YouTube upload."""
    if not CFG.get("youtube_long_ok", False):
        print("SKIP: long videos paused (youtube_long_ok false)"); return
    today = dt.date.today()
    day = today + dt.timedelta(days=(6 - today.weekday()) % 7)        # the coming Sunday (long-video day)
    if not long_due(day):
        print("SKIP: no long video due on", day); return
    import thumb
    unit, cyc = next_unit("long")
    it = make("long", unit, cyc)
    rk, S = unit.split(":")[1], int(unit.split(":")[2])
    n = len(json.load(open(DATA / rk / f"{S:03d}" / "timings.json"))["audio_file"]["timestamps"])
    th = OUT / f"thumb-{rk}-{S:03d}-c{cyc}.jpg"
    thumb.make_thumb(rk, S, RECITERS[rk]["name"], asset(random.choice(THUMB_CLIPS)), th)
    title, desc, tags = youtube_meta(rk, S, n)
    urls = publish_batch([it["file"], str(th)])
    job = {"publish_at": f"{day}T{CFG.get('long_time_utc', '13:00')}:00Z",
           "items": [{"unit": unit, "cycle": cyc, "mode": 0, "kind": "long", "file": it["file"], "video_url": urls[0],
                      "thumbnail_url": urls[1], "title": title, "description": desc, "tags": tags}]}
    (OUT / "long.json").write_text(json.dumps(job, indent=1, ensure_ascii=False))
    print(json.dumps(job, indent=1, ensure_ascii=False))



def to_publish():
    """Long videos uploaded as PRIVATE whose publish time has come (the Sunday task makes them public)."""
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M")
    out = [p for p in load_log()["posts"] if p.get("youtube_private") and (p.get("scheduled_at") or "")[:16] <= now]
    print(json.dumps([{"unit": p["unit"], "youtube_id": p["youtube_private"]} for p in out], indent=1))


def made_public(unit):
    log = load_log()
    for p in log["posts"]:
        if p["unit"] == unit and p.get("youtube_private"):
            p["youtube_id"] = p.pop("youtube_private"); p["public_at"] = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    save_log(log); print("public", unit)


if __name__ == "__main__":
    c = sys.argv[1]
    if c == "prepare" and "--extra" in sys.argv:
        # second daily slot: only during the Zapier trial window ("as many as possible")
        if dt.date.today() > dt.date.fromisoformat(CFG["extra_daily_short_until"]):
            print("SKIP: extra slot is only used until", CFG["extra_daily_short_until"]); sys.exit(0)
        sys.argv += ["--kind", "short"]
    if c == "prepare":
        kind = sys.argv[sys.argv.index("--kind") + 1] if "--kind" in sys.argv else "auto"
        skip = sys.argv[sys.argv.index("--skip") + 1:] if "--skip" in sys.argv else []
        prepare(kind, skip)
    elif c == "plan": plan_batch()
    elif c == "long": long_job()
    elif c == "to_publish": to_publish()
    elif c == "made_public": made_public(sys.argv[2])
    elif c == "uploaded_private":   # UNIT YOUTUBE_ID PUBLISH_AT
        posted(sys.argv[2], f"youtube {sys.argv[3]} (private until {sys.argv[4]})", sys.argv[4])
        lg = load_log(); lg["posts"][-1]["youtube_private"] = sys.argv[3]; save_log(lg)
    elif c == "sheet": sheet()
    elif c == "posted": posted(sys.argv[2], sys.argv[3], sys.argv[sys.argv.index("--at") + 1] if "--at" in sys.argv else None)
    elif c == "failed": failed(sys.argv[2], " ".join(sys.argv[3:]))
    elif c == "status": status()
