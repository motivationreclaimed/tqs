"""Render one video. Whole verses only; Arabic + English shown exactly during each verse (Quran.com timings);
graded nature clips (rotated, never looped); fades; long form adds title card, Bismillah card and quiet ending."""
import json, os, subprocess, tempfile
import numpy as np
from PIL import Image, ImageFilter
from qlib import FONTS, NAMES, ARABIC_NAMES, EN, BISM_AR, BISM_EN, arabic, write_ass, fit_size

GRADE = ("eq=contrast=1.06:saturation=0.85:gamma=0.95,colorbalance=rs=-0.02:bs=0.02:rh=-0.01:bh=0.02,"
         "colorlevels=romax=0.60:gomax=0.60:bomax=0.62,vignette=PI/4,fps=30")
AYAH_END = "۝"   # end-of-verse ornament: exactly one per verse, always last
XF = 1.0              # background crossfade


def measure(ass, size, times):
    w, h = size; top, bot = h, 0
    for t in times:
        raw = subprocess.check_output(["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i",
                                       f"color=c=black:s={w}x{h}:d=0.1:r=10",
                                       "-vf", f"setpts=PTS+{t:.3f}/TB,ass={ass}:fontsdir={FONTS}",
                                       "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "gray", "-"])
        a = np.frombuffer(raw, np.uint8).reshape(h, w); rows = np.where(a.max(1) > 40)[0]
        if len(rows): top, bot = min(top, rows[0]), max(bot, rows[-1])
    return int(top), int(bot)


def band_png(path, size, top, bot):
    w, h = size; pad = 90 if h > w else 70
    a = np.zeros((h, w), np.float32); a[max(0, top - pad):min(h, bot + pad), :] = 0.50
    m = Image.fromarray((a * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(110))
    im = Image.new("RGBA", size, (0, 0, 0, 0)); im.putalpha(m); im.save(path)


def plan_background(total, pick_clip):
    """pick_clip() -> (path, seconds). Each clip plays <=15 s and is swapped before it could run out."""
    segs, t0 = [], 0.0
    while t0 < total - 0.01:
        path, dur = pick_clip()
        use = max(2.5, min(15.0, dur - XF - 0.6))
        if total - (t0 + use) < 3.0 and (total - t0) + XF + 0.2 <= dur:
            use = total - t0
        segs.append((t0, min(total, t0 + use), path, dur)); t0 += use
    for a, b, p, d in segs:
        assert (b - a) + XF + 0.2 <= d + 0.01, "clip would run out"
    return segs


def render(kind, S, A, B, timings, audio, out, reciter_name, pick_clip, channel="The Quran Sounds"):
    vertical = kind == "short"
    T = {int(t["verse_key"].split(":")[1]): t for t in json.load(open(timings))["audio_file"]["timestamps"]}
    if not vertical: A, B = 1, max(T)
    W, H = (1080, 1920) if vertical else (1920, 1080)
    work = tempfile.mkdtemp(); ass = os.path.join(work, "s.ass")
    LEAD = 0.6
    INTRO = 0.0 if vertical else (5.0 if S in (1, 9) else 10.0)   # long: title card (+ Bismillah card)
    OUTRO = 1.8 if vertical else 18.0
    a0, a1 = T[A]["timestamp_from"] / 1000, T[B]["timestamp_to"] / 1000
    off = INTRO + LEAD - a0
    end_audio = a1 + off
    total = end_audio + OUTRO

    ay, ey, ab, eb, ae, ee = (960, 1010, 150, 96, 54, 38) if vertical else (570, 615, 165, 110, 52, 40)
    ev, mids = [], []
    for v in range(A, B + 1):
        s, e = T[v]["timestamp_from"] / 1000 + off, T[v]["timestamp_to"] / 1000 + off
        if v == A and vertical: s = 0.0
        if v == B: e = end_audio + (OUTRO - 0.3 if vertical else 3.0)
        ar = arabic(S, v)
        ev.append((s, e, "Arabic", ar + " " + AYAH_END, W // 2, ay, 2, fit_size(ar, ab, eb, 3)))
        en = EN[(S, v)]
        ev.append((s, e, "English", en + f"  ({S}:{v})", W // 2, ey, 8, fit_size(en, ae, ee, 9)))
        mids.append((T[v]["timestamp_from"] / 1000 + off + e) / 2)
    arabic_ev = [x for x in ev if x[2] == "Arabic"]
    assert len(arabic_ev) == B - A + 1 and all(x[3].count(AYAH_END) == 1 and x[3].endswith(AYAH_END) for x in arabic_ev)

    write_ass(ass, (W, H), ev, vertical)
    top, bot = measure(ass, (W, H), mids)
    gap = 70 if vertical else 45
    ref_y, brand_y = max(int(H * 0.2), top - gap), min(int(H * (0.72 if vertical else 0.9)), bot + gap)
    ref = f"Surah {NAMES[S-1]} · {S}" + ((f":{A}" + (f"-{B}" if B > A else "")) if vertical else "")
    brand = reciter_name if vertical else f"Recited by {reciter_name}"
    lf = 0.0 if vertical else INTRO
    lab = [(lf, total, "Ref", ref.upper(), W // 2, ref_y, 2, 44 if vertical else 40),
           (lf, total, "Brand", brand.upper(), W // 2, brand_y, 8, 34 if vertical else 30)]
    if channel:
        lab.append((lf, total, "Brand", channel.upper(), W // 2, brand_y + 50, 8, 26 if vertical else 24))
    intro = []
    if not vertical:
        # Title card = thumbnail (Publer/YouTube use frame 0): big, centered, only names + reciter, no fade from black
        if S in ARABIC_NAMES: intro.append((0.0, 5.0, "Arabic", ARABIC_NAMES[S], W // 2, 450, 2, 250))
        intro.append((0.0, 5.0, "Ref", f"SURAH {NAMES[S-1].upper()}", W // 2, 640, 2, 120))
        intro.append((0.0, 5.0, "Brand", reciter_name.upper(), W // 2, 690, 8, 50))
        if INTRO >= 10:
            intro.append((5.2, 9.8, "Arabic", BISM_AR, W // 2, 560, 2, 150))
            intro.append((5.4, 9.8, "English", BISM_EN, W // 2, 600, 8, 44))
    write_ass(ass, (W, H), intro + ev + lab, vertical)
    band = os.path.join(work, "band.png")
    band_png(band, (W, H), min(top, ref_y - 60), max(bot, brand_y + 70))

    segs = plan_background(total, pick_clip)
    base = ("crop=ih*9/16:ih,scale=1080:1920:flags=lanczos" if vertical
            else "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080")
    FIN, FOUT = 0.3, (1.0 if vertical else 2.5)
    audio_f = (f"atrim={a0:.3f}:{a1:.3f},asetpts=PTS-STARTPTS,adelay={int((INTRO + LEAD) * 1000)}:all=1,asetpts=N/SR/TB,apad,"
               f"atrim=0:{total:.3f},afade=out:st={end_audio + 0.3:.3f}:d=1.2")
    if vertical:  # few scenes: one pass with crossfades and a gentle zoom
        inp, fl = [], []
        for i, (s0, s1, path, dur) in enumerate(segs):
            L = s1 - s0 + XF + 0.2
            inp += ["-i", path]
            zoom = f"scale=w='trunc({W}*(1+0.06*t/{L:.2f})/2)*2':h=-2:eval=frame:flags=bicubic,crop={W}:{H}"
            fl.append(f"[{i}:v]trim=0:{L:.3f},setpts=PTS-STARTPTS,{base},{GRADE},{zoom},setsar=1[v{i}]")
        last = "v0"
        for i in range(1, len(segs)):
            fl.append(f"[{last}][v{i}]xfade=transition=fade:duration={XF}:offset={segs[i][0] - XF / 2:.3f}[x{i}]"); last = f"x{i}"
        n = len(segs)
        fl.append(f"[{n}:v]format=rgba[band]")
        fl.append(f"[{last}]trim=0:{total:.3f}[bg];[bg][band]overlay=0:0,ass={ass}:fontsdir={FONTS},"
                  f"fade=out:st={total - FOUT - 0.2:.3f}:d={FOUT},format=yuv420p[v]")
        fl.append(f"[{n+1}:a]{audio_f}[a]")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *inp, "-loop", "1", "-i", band, "-i", audio,
                        "-filter_complex", ";".join(fl), "-map", "[v]", "-map", "[a]", "-t", f"{total:.3f}",
                        "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-r", "30",
                        "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out)], check=True)
    else:  # long: build each scene separately (low memory, any length), join, then add text + audio
        parts = []
        for i, (s0, s1, path, dur) in enumerate(segs):
            L = s1 - s0; p = os.path.join(work, f"seg{i:04d}.mp4")
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", path, "-t", f"{L:.3f}", "-an", "-vf",
                            f"{base},{GRADE},fps=24," + ("" if i == 0 else "fade=in:0:d=0.7,") + f"fade=out:st={max(0, L - 0.7):.3f}:d=0.7,format=yuv420p",
                            "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", p], check=True)
            parts.append(p)
        lst = os.path.join(work, "list.txt")
        open(lst, "w").write("".join(f"file '{p}'\n" for p in parts))
        bg = os.path.join(work, "bg.mp4")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", bg], check=True)
        vbit = max(300, int(88e6 * 8 / total / 1000) - 128)   # file under ~90 MB (GitHub limit 100 MB); AV1 gives about twice the quality of H.264 at this size
        fl = (f"[1:v]format=rgba[band];[0:v]trim=0:{total:.3f},setpts=PTS-STARTPTS[bg];[bg][band]overlay=0:0,"
              f"ass={ass}:fontsdir={FONTS},fade=out:st={total - FOUT - 0.2:.3f}:d={FOUT},format=yuv420p[v];"
              f"[2:a]{audio_f}[a]")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", bg, "-loop", "1", "-i", band, "-i", audio,
                        "-filter_complex", fl, "-map", "[v]", "-map", "[a]", "-t", f"{total:.3f}",
                        "-c:v", "libsvtav1", "-preset", "8", "-b:v", f"{vbit}k", "-svtav1-params", "tune=0",
                        "-r", "24", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart",
                        str(out)], check=True)
    return {"seconds": round(total, 1), "verses": f"{S}:{A}-{B}", "clips": [os.path.basename(s[2]) for s in segs]}
