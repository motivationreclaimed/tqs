"""Verify a Quran.com recording against its timings and the Tanzil text. Prints PASS/FAIL with reasons.
usage: verify.py reciter_key surah audio.mp3 timings.json   (copies both into surahs/<reciter>/<sss>/ when PASS)"""
import json, os, re, shutil, subprocess, sys
import numpy as np

import re as _re
def _letters(s): return _re.sub(r"[\u064B-\u065F\u0670\u06D6-\u06ED\u0640]", "", s)
def strip_bismillah(text, bism):
    """Remove the Bismillah Tanzil prefixes to verse 1 (exact or with variant vowel marks, e.g. 95:1, 97:1)."""
    toks = text.split(" ")
    if len(toks) > 4 and _letters(" ".join(toks[:4])).split() == _letters(bism).split():
        return " ".join(toks[4:]).strip()
    return text
U = "/mnt/user-data/uploads/"
rk, S, mp3, tj = sys.argv[1], int(sys.argv[2]), sys.argv[3], sys.argv[4]
EXPECT = {"mishary": "mishari_al_afasy", "abdulbasit": "abdul_baset", "abdulbasit_mujawwad": "abdul_baset/mujawwad", "abdulbasit_murattal": "abdul_baset/murattal"}
raw = open(tj, encoding="utf-8").read()
j = json.loads(raw)["audio_file"]; ts = j["timestamps"]
txt = open(U + "f3c19cef-quran-uthmani.txt", encoding="utf-8").read().splitlines()
Q = {int(l.split("|")[1]): l.split("|")[2].strip() for l in txt if l.startswith(f"{S}|")}
b = [l.split("|")[2].strip() for l in txt if l.startswith("1|1|")][0]
if S not in (1, 9): Q[1] = strip_bismillah(Q[1], b)

mark = re.compile(r"^[ۖ-ۭ]+$")
dur = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", mp3]))
fails, notes = [], []
if EXPECT[rk] not in j["audio_url"]: fails.append(f"audio_url is not {rk}: {j['audio_url']}")
if j.get("chapter_id") != S or f"/{S}.mp3" not in j["audio_url"]: fails.append("surah number mismatch")
if abs(ts[-1]["timestamp_to"] / 1000 - dur) > 0.5: fails.append(f"length mismatch: timings {ts[-1]['timestamp_to']/1000:.2f}s vs file {dur:.2f}s")
if [t["verse_key"] for t in ts] != [f"{S}:{i}" for i in range(1, len(Q) + 1)]: fails.append("verses missing / out of order")
for t in ts:
    v = int(t["verse_key"].split(":")[1]); n = len([w for w in Q[v].split() if not mark.match(w)])
    idx = [x[0] for x in t["segments"] if len(x) == 3]
    if not idx or max(idx) != n: fails.append(f"{S}:{v} word count text {n} vs audio {max(idx) if idx else 0}")
subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", mp3, "-ac", "1", "-ar", "2000", "-f", "s16le", "/tmp/v.raw"], check=True)
x = np.fromfile("/tmp/v.raw", np.int16).astype(float); w = 100; n = len(x) // w
db = 20 * np.log10(np.sqrt((x[:n * w].reshape(n, w) ** 2).mean(1)) + 1); med = np.median(db)
dips = [round(med - db[max(0, int(t["timestamp_to"] / 50) - 6):int(t["timestamp_to"] / 50) + 6].min(), 1) for t in ts[:-1]]
weak = [f"{S}:{i+1}" for i, d in enumerate(dips) if d < 15]
if weak: fails.append(f"verse ends not on a pause: {weak}")
mins = dur / 60
if mins > 20 and S != 2 and os.environ.get("ALLOW_LONG") != "1": fails.append(f"longer than 20 min ({mins:.1f}) - skipped by rule")  # Al-Baqarah approved by user
print(("PASS" if not fails else "FAIL"), f"{rk} surah {S}: {len(ts)} verses, {mins:.1f} min, weakest pause {min(dips) if dips else '-'} dB")
for f in fails: print("  -", f)
if not fails:
    d = f"/home/claude/surahs/{rk}/{S:03d}"; os.makedirs(d, exist_ok=True)
    if os.path.abspath(mp3) != os.path.abspath(f"{d}/audio.mp3"): shutil.copy(mp3, f"{d}/audio.mp3")
    open(f"{d}/timings.json", "w", encoding="utf-8").write(raw)
    print("  saved ->", d)
