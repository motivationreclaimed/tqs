"""Dua video builder in the Quran-channel style (dark nature bg, centred serif text)."""
import json, math, random, re, subprocess, os, glob
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = "/home/claude/dua_videos"
CAT = json.load(open("/home/claude/opendua/catalogue.json"))
AUDIO = "/home/claude/opendua/audio/"
NATURE = sorted(glob.glob(f"{ROOT}/nature/*.mp4"))
SFX = sorted(glob.glob(f"{ROOT}/sfx_loops/*.wav") + glob.glob(f"{ROOT}/sfx_loops/*.m4a"))
F_AR = f"{ROOT}/fonts/AmiriQuran-Regular.ttf"
F_B = "/usr/share/fonts/truetype/freefont/FreeSerifBold.ttf"
F_I = "/usr/share/fonts/truetype/freefont/FreeSerifItalic.ttf"
F_R = "/usr/share/fonts/truetype/freefont/FreeSerif.ttf"
RECITER = "RECITED BY MUHAMMAD JUMAH"
CHANNEL = "THE DUA HOUR"

FMT = {
    "portrait": dict(W=1080, H=1920, tw=740, top=480, bot=1440, cx=540, title=40, ar=74, tr=34, en=46, rec=30, ch=24, gap=56),
    "landscape": dict(W=1920, H=1080, tw=1350, top=120, bot=960, cx=960, title=40, ar=66, tr=30, en=42, rec=28, ch=22, gap=40),
}


def dur(p):
    return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p]))


# ---------- data ----------
def entry_segments(n):
    """Return (chapter_title, ref, [(mp3, arabic, translit, english)]) for entry n."""
    e = CAT["entries"][n - 1]
    title = re.sub(r"\s*\(\d+ of \d+\)$", "", e["title"])
    segs = []
    for s in e["variations"][0]["steps"]:
        if not s.get("recordings"):
            continue
        duas = [it["dua"] for it in s["items"] if "dua" in it]
        mp3 = AUDIO + s["recordings"][0]["url"].split("/")[-1]
        segs.append((mp3, " ".join(d["arabic"] for d in duas), " ".join(d["transliteration"] for d in duas),
                     " ".join(d["translation"] for d in duas)))
    return title, e["sourceReference"], segs


def split_words(text, n):
    """Split text into n parts near equal length, preferring punctuation breaks."""
    words = text.split()
    if n <= 1 or len(words) < n * 2:
        return [text] if n <= 1 else _even(words, n)
    total = len(text)
    parts, start = [], 0
    for k in range(1, n):
        target = total * k / n
        best, bscore, pos = None, 1e9, 0
        for i, w in enumerate(words):
            pos += len(w) + 1
            if i < start + 1 or i >= len(words) - 1:
                continue
            score = abs(pos - target) - (total * 0.06 if re.search(r"[،,.;:؛!?]$", w) else 0)
            if score < bscore:
                best, bscore = i, score
        parts.append(" ".join(words[start:best + 1]))
        start = best + 1
    parts.append(" ".join(words[start:]))
    return parts


def _even(words, n):
    k = math.ceil(len(words) / n)
    return [" ".join(words[i:i + k]) for i in range(0, len(words), k)]


# ---------- drawing ----------
def wrap(d, text, font, maxw, rtl=False):
    kw = {"direction": "rtl", "language": "ar"} if rtl else {}
    lines, cur = [], ""
    for w in text.split(" "):
        t = (cur + " " + w).strip()
        if d.textlength(t, font=font, **kw) <= maxw or not cur:
            cur = t
        else:
            lines.append(cur); cur = w
    if cur:
        lines.append(cur)
    return lines


def spaced(d, xy_center, text, font, spacing, fill, layer):
    widths = [d.textlength(c, font=font) for c in text]
    total = sum(widths) + spacing * (len(text) - 1)
    x, y = xy_center[0] - total / 2, xy_center[1]
    for c, w in zip(text, widths):
        layer.text((x, y), c, font=font, fill=fill)
        x += w + spacing


def render_page(fmt, title, ar, tr, en, ref, out):
    f = FMT[fmt]; W, H = f["W"], f["H"]
    scale = 1.0
    probe = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    while True:
        Ft = ImageFont.truetype(F_B, int(f["title"] * min(1, scale + .15)))
        Fa = ImageFont.truetype(F_AR, int(f["ar"] * scale), layout_engine=ImageFont.Layout.RAQM)
        Fr = ImageFont.truetype(F_I, int(f["tr"] * scale))
        Fe = ImageFont.truetype(F_B, int(f["en"] * scale))
        Fc = ImageFont.truetype(F_B, f["rec"]); Fch = ImageFont.truetype(F_B, f["ch"])
        sp_t = int(f["title"] * .16)
        tl = wrap(probe, title.upper(), Ft, f["tw"] - 40 - sp_t * 30)
        al = wrap(probe, ar, Fa, f["tw"], rtl=True)
        rl = wrap(probe, tr, Fr, f["tw"])
        el = wrap(probe, en + (f"  ({ref.replace(' ', chr(160))})" if ref else ""), Fe, f["tw"])
        lh = dict(t=Ft.size * 1.35, a=Fa.size * 2.05, r=Fr.size * 1.35, e=Fe.size * 1.3)
        g = f["gap"] * scale
        blocks = [("t", tl), ("a", al), ("r", rl), ("e", el)]
        total = sum(len(l) * lh[k] for k, l in blocks) + g * 3 + Fa.size * 0.45 + f["gap"] * 1.2 + f["rec"] * 1.4 + (f["ch"] * 1.6 if CHANNEL else 0)
        if total <= (f["bot"] - f["top"]) or scale < 0.45:
            break
        scale -= 0.04

    txt = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(txt)
    y = f["top"] + (f["bot"] - f["top"] - total) / 2; CX = f["cx"]
    for kind, lines in blocks:
        for ln in lines:
            if kind == "t":
                spaced(d, (CX, y), ln, Ft, sp_t, (255, 255, 255, 255), d)
            else:
                font = {"a": Fa, "r": Fr, "e": Fe}[kind]
                kw = {"direction": "rtl", "language": "ar"} if kind == "a" else {}
                tw = d.textlength(ln, font=font, **kw)
                col = (225, 225, 225, 235) if kind == "r" else (255, 255, 255, 255)
                d.text((CX - tw / 2, y), ln, font=font, fill=col, **kw)
            y += lh[kind]
        y += g + (Fa.size * 0.45 if kind == "a" else 0)
    y += f["gap"] * 0.2
    spaced(d, (CX, y), RECITER, Fc, int(f["rec"] * .18), (235, 235, 235, 240), d)
    if CHANNEL:
        y += f["rec"] * 1.6
        spaced(d, (CX, y), CHANNEL.upper(), Fch, int(f["ch"] * .18), (235, 235, 235, 220), d)
    # soft dark glow behind all text, like the Quran videos
    a = txt.split()[3]
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0)); sh.putalpha(a.filter(ImageFilter.GaussianBlur(7)).point(lambda v: min(255, int(v * 1.3))))
    sh2 = Image.new("RGBA", (W, H), (0, 0, 0, 0)); sh2.paste((0, 0, 0, 255), mask=a.filter(ImageFilter.GaussianBlur(2)))
    out_img = Image.alpha_composite(Image.alpha_composite(sh, sh2.transform((W, H), Image.AFFINE, (1, 0, -2, 0, 1, -3))), txt)
    out_img.save(out)


def render_thumb(fmt, big, arabic, out):
    """Thumbnail card shown on the first frames: channel name, big title, short Arabic line."""
    f = FMT[fmt]; W, H = f["W"], f["H"]
    img = Image.new("RGBA", (W, H), (0, 0, 0, 95)); d = ImageDraw.Draw(img)
    CX = f["cx"]; maxw = f["tw"] if fmt == "portrait" else 1500
    size = 104 if fmt == "portrait" else 112
    while True:
        Fb = ImageFont.truetype(F_B, size)
        lines = wrap(d, big.upper(), Fb, maxw)
        if len(lines) <= 3 or size < 60:
            break
        size -= 6
    Fa = ImageFont.truetype(F_AR, int(size * 0.8), layout_engine=ImageFont.Layout.RAQM)
    al = wrap(d, arabic, Fa, maxw, rtl=True)[:1]
    Fs = ImageFont.truetype(F_B, 34 if fmt == "portrait" else 34)
    block = 34 * 2.6 + len(lines) * size * 1.15 + 40 + (Fa.size * 2.0 if al else 0)
    y = f["top"] + (f["bot"] - f["top"] - block) / 2
    spaced(d, (CX, y), CHANNEL, Fs, 9, (240, 214, 150, 255), d); y += 34 * 2.6
    for ln in lines:
        tw = d.textlength(ln, font=Fb); d.text((CX - tw / 2, y), ln, font=Fb, fill=(255, 255, 255, 255)); y += size * 1.15
    y += 40
    d.line([(CX - 90, y - 18), (CX + 90, y - 18)], fill=(240, 214, 150, 230), width=3)
    for ln in al:
        tw = d.textlength(ln, font=Fa, direction="rtl", language="ar")
        d.text((CX - tw / 2, y), ln, font=Fa, fill=(255, 255, 255, 255), direction="rtl", language="ar")
    a = img.split()[3].point(lambda v: 255 if v > 95 else 0)
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0)); sh.putalpha(a.filter(ImageFilter.GaussianBlur(8)).point(lambda v: min(255, int(v * 1.4))))
    base = Image.new("RGBA", (W, H), (0, 0, 0, 95))
    Image.alpha_composite(Image.alpha_composite(base, sh), img).save(out)


# ---------- video ----------
def bg_filter(fmt):
    f = FMT[fmt]
    sc = f"scale=-2:{f['H']},crop={f['W']}:{f['H']}" if fmt == "portrait" else f"scale={f['W']}:{f['H']}:force_original_aspect_ratio=increase,crop={f['W']}:{f['H']}"
    return f"{sc},setsar=1,fps=30,colorchannelmixer=rr=0.27:gg=0.27:bb=0.27,eq=saturation=0.8,vignette=PI/4"


def make_dua(fmt, n, out, rng, max_len=None, lead=1.2, tail=1.8, thumb_title=None):
    """One dua: text pages over a random nature clip, recitation audio, low ambience."""
    title, ref, segs = entry_segments(n)
    f = FMT[fmt]
    # audio timeline
    seg_d = [dur(s[0]) for s in segs]
    voice_T = sum(seg_d) + 0.6 * (len(segs) - 1)
    T = lead + voice_T + tail
    if max_len:
        T = min(T, max_len)
    # pages
    cap = 150 if fmt == "portrait" else 210
    pages, t = [], lead
    for (mp3, ar, tr, en), sd in zip(segs, seg_d):
        n_p = max(1, math.ceil(len(ar) / cap), math.ceil(len(en) / (cap * 1.9)))
        A, R, E = split_words(ar, n_p), split_words(tr, n_p), split_words(en, n_p)
        n_p = min(len(A), len(R), len(E))
        w = [len(x) for x in A[:n_p]]
        for i in range(n_p):
            pd = sd * w[i] / sum(w)
            pages.append((t, t + pd, A[i], R[i], E[i])); t += pd
        t += 0.6
    tmp = out[:-4]
    pngs = []
    for i, (s, e, a, r, en) in enumerate(pages):
        p = f"{tmp}_p{i}.png"; render_page(fmt, title, a, r, en, f"Hisn al-Muslim {ref}", p); pngs.append(p)
    # first page appears at 0.4s, last stays to the end
    times = [(0.1 if i == 0 else s, T if i == len(pages) - 1 else pages[i + 1][0]) for i, (s, *_ ) in enumerate(pages)]
    clip = rng.choice(NATURE)
    sfx = rng.sample(SFX, rng.choice([1, 2]))
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-stream_loop", "-1", "-i", clip]
    for p in pngs:
        cmd += ["-loop", "1", "-t", f"{T:.2f}", "-i", p]
    ai = len(pngs) + 1
    for s in segs:
        cmd += ["-i", s[0]]
    for s in sfx:
        cmd += ["-stream_loop", "-1", "-i", s]
    thumb_png = f"{tmp}_thumb.png"
    first_ar = " ".join(segs[0][1].split()[:6])
    render_thumb(fmt, thumb_title or title, first_ar, thumb_png); pngs.append(thumb_png)
    cmd += ["-loop", "1", "-t", "0.2", "-i", thumb_png]
    ti = ai + len(segs) + len(sfx)
    fc = [f"[0:v]{bg_filter(fmt)},trim=0:{T:.2f},setpts=PTS-STARTPTS,fade=out:st={T-0.8:.2f}:d=0.8[b0]"]
    last = "b0"
    for i, (s, e) in enumerate(times):
        fo = min(0.6, (e - s) / 3)
        fin = "" if i == 0 else f"fade=in:st={s:.2f}:d=0.6:alpha=1,"
        fc.append(f"[{i+1}:v]format=rgba,{fin}fade=out:st={e-fo:.2f}:d={fo:.2f}:alpha=1[t{i}]")
        fc.append(f"[{last}][t{i}]overlay=0:0:enable='between(t,{s:.2f},{e:.2f})'[b{i+1}]"); last = f"b{i+1}"
    fc.append(f"[{last}][{ti}:v]overlay=0:0:enable='lt(t,0.1)'[bt]")
    fc.append(f"[bt]format=yuv420p[v]")
    # voice: segments with 0.6s gaps, delayed by lead
    vparts = []
    for k in range(len(segs)):
        pad = "apad=pad_dur=0.6," if k < len(segs) - 1 else ""
        fc.append(f"[{ai+k}:a]aformat=sample_rates=44100:channel_layouts=stereo,{pad}asetpts=PTS-STARTPTS[s{k}]"); vparts.append(f"[s{k}]")
    fc.append(f"{''.join(vparts)}concat=n={len(segs)}:v=0:a=1,loudnorm=I=-16:TP=-1.5,adelay={int(lead*1000)}:all=1,apad[voice]")
    amb = []
    for j in range(len(sfx)):
        off = rng.uniform(0, 20)
        fc.append(f"[{ai+len(segs)+j}:a]atrim=start={off:.1f},asetpts=PTS-STARTPTS,volume={-12 - 3*(len(sfx)-1)}dB[x{j}]"); amb.append(f"[x{j}]")
    fc.append(f"{''.join(amb)}amix=inputs={len(amb)}:normalize=0[amb]" if len(amb) > 1 else f"{amb[0]}anull[amb]")
    fc.append(f"[voice][amb]amix=inputs=2:normalize=0:duration=longest,atrim=0:{T:.2f},afade=in:d=0.3,afade=out:st={T-1.5:.2f}:d=1.5[aout]")
    cmd += ["-filter_complex", ";".join(fc), "-map", "[v]", "-map", "[aout]", "-t", f"{T:.2f}",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", out]
    subprocess.run(cmd, check=True)
    for p in pngs:
        os.remove(p)
    return dict(out=out, T=round(T, 1), clip=os.path.basename(clip), sfx=[os.path.basename(s) for s in sfx], pages=len(pages))
