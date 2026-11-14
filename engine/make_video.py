"""Quran video renderer v2.
  make_video.py short SURAH FIRST LAST timings.json audio.mp3 out.mp4 [reciter] [channel]
  make_video.py long  SURAH 0 0        timings.json audio.mp3 out.mp4 [reciter] [channel]
Rules: whole verses only; text/timings from Tanzil + the same Quran.com recording; word highlight only where the
word timings are perfectly regular (otherwise the verse is shown without it); exactly one ۝ per verse, at its end.
"""
import json, os, re, subprocess, sys, tempfile
import numpy as np
from PIL import Image, ImageFilter
sys.path.insert(0, "/home/claude/deen-shorts"); sys.path.insert(0, "/home/claude/library")
from common import write_ass, fit_size
from quran import NAMES
import picker

U = "/mnt/user-data/uploads/"
FONTS = "/home/claude/fonts"
GRADE = ("eq=contrast=1.06:saturation=0.85:gamma=0.95,colorbalance=rs=-0.02:bs=0.02:rh=-0.01:bh=0.02,"
         "colorlevels=romax=0.60:gomax=0.60:bomax=0.62,vignette=PI/4,fps=30")
ENABLE_HIGHLIGHT = False  # off: libass mis-orders a re-coloured word in RTL lines (failed visual check)
GOLD = "&H50C8F5&"                      # ASS colour (BGR) for the word being recited
ARABIC_NAMES = {67: "سورة الملك"}       # only names I am certain of; others need the Quran.com chapters list
MARK = re.compile(r"^[ۖ-ۭ]+$")  # stand-alone pause marks are not words
DIG = str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")


def load_text(p):
    d = {}
    for l in open(p, encoding="utf-8"):
        x = l.rstrip("\n").split("|")
        if len(x) == 3 and x[0].isdigit(): d[(int(x[0]), int(x[1]))] = x[2].strip()
    return d


AR, EN = load_text(U + "f3c19cef-quran-uthmani.txt"), load_text(U + "63033ce3-en.sahih.txt")
BISM_AR, BISM_EN = AR[(1, 1)], EN[(1, 1)]



import re as _re
def _letters(s): return _re.sub(r"[\u064B-\u065F\u0670\u06D6-\u06ED\u0640]", "", s)
def strip_bismillah(text, bism):
    """Remove the Bismillah Tanzil prefixes to verse 1 (exact or with variant vowel marks, e.g. 95:1, 97:1)."""
    toks = text.split(" ")
    if len(toks) > 4 and _letters(" ".join(toks[:4])).split() == _letters(bism).split():
        return " ".join(toks[4:]).strip()
    return text

def arabic(s, v):
    t = AR[(s, v)]
    if v == 1 and s not in (1, 9): t = strip_bismillah(t, BISM_AR)
    return t


def ayah_end(v):
    # ornament only: with this renderer the number does not sit inside the ornament, so it is left out
    return "\u06DD"


def word_plan(s, v, tsv, a0, off):
    """[(start, end, token_index)] for each recited word, or None if the timings are not perfectly regular."""
    toks = arabic(s, v).split(" ")
    words = [i for i, t in enumerate(toks) if not MARK.match(t)]
    seg = tsv["segments"]
    if not (seg and all(len(x) == 3 for x in seg) and [x[0] for x in seg] == list(range(1, len(words) + 1))
            and all(seg[i][1] <= seg[i + 1][1] for i in range(len(seg) - 1))
            and seg[0][1] >= tsv["timestamp_from"] - 150 and seg[-1][2] <= tsv["timestamp_to"] + 150):
        return None
    out = []
    for i, (w, st, en) in enumerate(seg):
        nxt = seg[i + 1][1] if i + 1 < len(seg) else en
        out.append((st / 1000 - a0 + off, max(en, nxt) / 1000 - a0 + off, words[w - 1]))
    return out


def highlight_text(s, v, tok_i):
    toks = arabic(s, v).split(" ")
    parts = [("{\\alpha&H00&\\1c" + GOLD + "}" + t + "{\\alpha&HFF&}") if i == tok_i else t for i, t in enumerate(toks)]
    return "{\\alpha&HFF&}" + " ".join(parts) + " " + ayah_end(v)


def ass_fix(path, vertical):
    out = []
    for l in open(path, encoding="utf-8").read().splitlines():
        if l.startswith(("Style: English", "Style: Ref", "Style: Brand")):
            l = l.replace("&H64000000,0,0,0,0", "&H64000000,-1,0,0,0")
        if l.startswith(("Style: Ref", "Style: Brand")):
            l = l.replace(",100,100,0,0,1,", ",100,100,3,0,1,")  # all Latin text: bold Times New Roman style
        l = l.replace(",86,86,0,1", ",130,130,0,1") if vertical else l.replace(",153,153,0,1", ",330,330,0,1")
        out.append(l)
    open(path, "w", encoding="utf-8").write("\n".join(out) + "\n")


def add_raw_events(path, lines):
    with open(path, "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def at(t):
    t = max(0, t); return f"{int(t // 3600)}:{int(t % 3600 // 60):02d}:{t % 60:05.2f}"


def measure(ass, size, times):
    w, h = size; top, bot = h, 0
    for t in times:
        raw = subprocess.check_output(["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", f"color=c=black:s={w}x{h}:d={t+0.2}:r=10",
                                       "-vf", f"ass={ass}:fontsdir={FONTS}", "-ss", f"{t}", "-frames:v", "1",
                                       "-f", "rawvideo", "-pix_fmt", "gray", "-"])
        a = np.frombuffer(raw, np.uint8).reshape(h, w); rows = np.where(a.max(1) > 40)[0]
        if len(rows): top, bot = min(top, rows[0]), max(bot, rows[-1])
    return int(top), int(bot)


def band_png(path, size, top, bot):
    """soft dark band behind the text so it reads clearly while the scenery stays visible"""
    w, h = size; pad = 90 if h > w else 70
    a = np.zeros((h, w), np.float32); a[max(0, top - pad):min(h, bot + pad), :] = 0.50
    m = Image.fromarray((a * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(110))
    im = Image.new("RGBA", size, (0, 0, 0, 0)); im.putalpha(m); im.save(path)


def main():
    mode, S, A, B = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
    raw = json.load(open(sys.argv[5]))["audio_file"]["timestamps"]
    T = {int(t["verse_key"].split(":")[1]): t for t in raw}
    audio, out = sys.argv[6], sys.argv[7]
    reciter = sys.argv[8] if len(sys.argv) > 8 else "Mishary Rashid Alafasy"
    channel = sys.argv[9] if len(sys.argv) > 9 else ""
    vertical = mode == "short"
    if not vertical: A, B = 1, max(T)
    W, H = (1080, 1920) if vertical else (1920, 1080)
    work = tempfile.mkdtemp(); ass = os.path.join(work, "s.ass")
    cfg = {"fonts": {"arabic": "Amiri Quran", "english": "Liberation Serif"}}

    LEAD = 0.6
    INTRO = 0.0 if vertical else 10.0          # long form: 5 s title card + 5 s Bismillah (text only)
    if not vertical and S in (1, 9): INTRO = 5.0  # Al-Fatihah: Bismillah is verse 1; At-Tawbah: no Bismillah
    OUTRO = 1.8 if vertical else 18.0           # long form: quiet ending for YouTube end screens
    a0, a1 = T[A]["timestamp_from"] / 1000, T[B]["timestamp_to"] / 1000
    off = INTRO + LEAD - a0                     # output time = recording time + off
    end_audio = a1 + off
    total = end_audio + OUTRO

    if vertical: ay, ey, ab, eb, ae, ee = 960, 1010, 150, 96, 54, 38
    else: ay, ey, ab, eb, ae, ee = 570, 615, 165, 110, 52, 40
    ev, hl, mids, bounds, ayah_marks = [], [], [], [], 0
    no_hl = []
    for v in range(A, B + 1):
        s, e = T[v]["timestamp_from"] / 1000 + off, T[v]["timestamp_to"] / 1000 + off
        if v == A and vertical: s = 0.0                       # text on screen from the very first frame
        if v == B: e = end_audio + (OUTRO - 0.3 if vertical else 3.0)
        ar = arabic(S, v); fs = fit_size(ar, ab, eb, 3)
        ev.append((s, e, "Arabic", ar + " " + ayah_end(v), W // 2, ay, 2, fs)); ayah_marks += 1
        en = EN[(S, v)]
        ev.append((s, e, "English", en + f"  ({S}:{v})", W // 2, ey, 8, fit_size(en, ae, ee, 9)))
        mids.append((T[v]["timestamp_from"] / 1000 + off + e) / 2)
        plan = word_plan(S, v, T[v], a0, INTRO + LEAD) if ENABLE_HIGHLIGHT else None
        if plan is None: no_hl.append(v)
        else:
            for ws, we, ti in plan:
                hl.append(f"Dialogue: 1,{at(ws)},{at(we)},Arabic,,0,0,0,,{{\\an2\\pos({W//2},{ay})\\fs{fs}}}{highlight_text(S, v, ti)}")
        if v > A: bounds.append(T[v]["timestamp_from"] / 1000 + off)

    # sanity: exactly one end-of-ayah symbol per verse, always the last thing in the verse text
    assert ayah_marks == B - A + 1 and all(x[3].count("۝") == 1 and x[3].split(" ")[-1].startswith("۝")
                                            for x in ev if x[2] == "Arabic")

    write_ass(ass, (W, H), cfg, ev); ass_fix(ass, vertical)
    top, bot = measure(ass, (W, H), mids)
    gap = 70 if vertical else 45
    ref_y, brand_y = max(int(H * 0.2), top - gap), min(int(H * (0.72 if vertical else 0.9)), bot + gap)
    ref = f"Surah {NAMES[S-1]} · {S}" + ((f":{A}" + (f"-{B}" if B > A else "")) if vertical else "")
    brand = reciter if vertical else f"Recited by {reciter}"
    lab_from = 0.0 if vertical else INTRO
    lab = [(lab_from, total, "Ref", ref.upper(), W // 2, ref_y, 2, 44 if vertical else 40),
           (lab_from, total, "Brand", brand.upper(), W // 2, brand_y, 8, 34 if vertical else 30)]
    if channel: lab.append((lab_from, total, "Brand", channel, W // 2, brand_y + 48, 8, 28 if vertical else 26))
    intro = []
    if not vertical:  # title card, then Bismillah as text only (not a verse, no number)
        if S in ARABIC_NAMES:
            intro.append((0.3, 5.0, "Arabic", ARABIC_NAMES[S], W // 2, 500, 2, 190))
        intro.append((0.6, 5.0, "Ref", f"SURAH {NAMES[S-1].upper()} · {S}", W // 2, 560, 8, 52))
        intro.append((0.9, 5.0, "Brand", f"RECITED BY {reciter.upper()}", W // 2, 640, 8, 32))
        if INTRO >= 10:
            intro.append((5.2, 9.8, "Arabic", BISM_AR, W // 2, 560, 2, 150))
            intro.append((5.4, 9.8, "English", BISM_EN, W // 2, 600, 8, 44))
    write_ass(ass, (W, H), cfg, intro + ev + lab); ass_fix(ass, vertical); add_raw_events(ass, hl)

    band = os.path.join(work, "band.png")
    band_png(band, (W, H), min(top, ref_y - 60), max(bot, brand_y + 50))

    # background: all clips in rotation; each plays up to 15 s, or less if the clip is shorter,
    # and is replaced before it could ever run out (no looping, no replay)
    XF = 1.0
    durs = {c["file"]: c["seconds"] for c in json.load(open("/home/claude/library/clips.json"))}
    segs, clips, t0 = [], [], 0.0
    while t0 < total - 0.01:
        c = picker.next_clips(1, vertical=vertical)[0]
        use = max(2.5, min(15.0, durs[c] - XF - 0.6))
        if total - (t0 + use) < 3.0: use = total - t0          # absorb a tiny remainder
        if use > durs[c] - XF - 0.3:                            # remainder too long for this clip: take another
            use = max(2.5, min(15.0, durs[c] - XF - 0.6)); 
        segs.append((t0, min(total, t0 + use))); clips.append(c); t0 += use
    for (a, b), c in zip(segs, clips):
        assert (b - a) + XF + 0.2 <= durs[c] + 0.01, "clip would run out"
    FIN, FOUT = 0.3, (1.0 if vertical else 2.5)
    base = ("crop=ih*9/16:ih,scale=1080:1920:flags=lanczos" if vertical
            else "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080")
    inp, fl = [], []
    for i, (s0, s1) in enumerate(segs):
        L = s1 - s0 + XF + 0.2
        inp += ["-i", clips[i]]  # no looping
        zoom = (f"scale=w='trunc({W}*(1+0.06*t/{L:.2f})/2)*2':h=-2:eval=frame:flags=bicubic,crop={W}:{H}")  # gentle zoom-in
        fl.append(f"[{i}:v]trim=0:{L:.3f},setpts=PTS-STARTPTS,{base},{GRADE},{zoom},setsar=1[v{i}]")
    last = "v0"
    for i in range(1, len(segs)):
        fl.append(f"[{last}][v{i}]xfade=transition=fade:duration={XF}:offset={segs[i][0] - XF / 2:.3f}[x{i}]"); last = f"x{i}"
    n = len(segs)
    fl.append(f"[{n}:v]format=rgba[band]")
    fl.append(f"[{last}]trim=0:{total:.3f}[bg];[bg][band]overlay=0:0,ass={ass}:fontsdir={FONTS},"
              f"fade=in:0:d={FIN},fade=out:st={total - FOUT - 0.2:.3f}:d={FOUT},format=yuv420p[v]")
    fl.append(f"[{n+1}:a]atrim={a0:.3f}:{a1:.3f},asetpts=PTS-STARTPTS,adelay={int((INTRO + LEAD) * 1000)}:all=1,apad,"
              f"atrim=0:{total:.3f},afade=out:st={end_audio + 0.3:.3f}:d=1.2[a]")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *inp, "-loop", "1", "-i", band, "-i", audio,
                    "-filter_complex", ";".join(fl), "-map", "[v]", "-map", "[a]", "-t", f"{total:.3f}",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "21" if vertical else "23",
                    "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", out], check=True)
    print(json.dumps({"out": out, "verses": f"{S}:{A}-{B}", "seconds": round(total, 1), "ayah_symbols": ayah_marks,
                      "highlight_off_for": no_hl, "clips": [os.path.basename(c) for c in clips]}))


if __name__ == "__main__":
    main()
