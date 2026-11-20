"""Long-video thumbnail (1280x720 JPEG < 2 MB): dark mountain/forest background, reciter portrait in a circle on
the right, big centered names on the left: Arabic surah name, SURAH NAME, RECITER. Times-style bold, white/silver."""
import subprocess, tempfile
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance
from qlib import ROOT, FONTS, NAMES, ARABIC_NAMES, write_ass
import render

W, H = 1280, 720


def make_thumb(rk, S, reciter_name, clip_path, out):
    tmp = Path(tempfile.mkdtemp())
    bg = tmp / "bg.png"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", "2", "-i", str(clip_path), "-frames:v", "1", "-vf",
                    f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},{render.GRADE},eq=brightness=-0.08",
                    str(bg)], check=True)
    im = Image.open(bg).convert("RGB")
    # soft dark panel behind the text block
    shade = Image.new("L", (W, H), 0); d = ImageDraw.Draw(shade)
    d.rectangle([0, 0, 800, H], fill=110); shade = shade.filter(ImageFilter.GaussianBlur(90))
    im = Image.composite(Image.new("RGB", (W, H), (0, 0, 0)), im, shade)
    # reciter portrait: circle with a thin silver ring
    p = ROOT / "reciters" / f"{rk}.png"
    if p.exists():
        D = 470; cx, cy = 1000, 360
        por = Image.open(p).convert("RGB")
        s = min(por.size); por = por.crop(((por.width - s) // 2, 0, (por.width - s) // 2 + s, s)).resize((D, D), Image.LANCZOS)
        por = ImageEnhance.Brightness(por).enhance(0.92)
        mask = Image.new("L", (D * 4, D * 4), 0); ImageDraw.Draw(mask).ellipse([0, 0, D * 4 - 1, D * 4 - 1], fill=255)
        mask = mask.resize((D, D), Image.LANCZOS)
        glow = Image.new("L", (W, H), 0); ImageDraw.Draw(glow).ellipse([cx - D // 2 - 30, cy - D // 2 - 30, cx + D // 2 + 30, cy + D // 2 + 30], fill=140)
        im = Image.composite(Image.new("RGB", (W, H), (0, 0, 0)), im, glow.filter(ImageFilter.GaussianBlur(30)))
        ring = ImageDraw.Draw(im); ring.ellipse([cx - D // 2 - 7, cy - D // 2 - 7, cx + D // 2 + 7, cy + D // 2 + 7], fill=(215, 215, 220))
        im.paste(por, (cx - D // 2, cy - D // 2), mask)
        tx = 400
    else:
        tx = W // 2
    im.save(bg)
    ass = tmp / "t.ass"
    name = NAMES[S - 1].upper()
    fs = 96 if len(name) <= 12 else (84 if len(name) <= 15 else 72)
    ev = []
    if S in ARABIC_NAMES: ev.append((0, 5, "Arabic", ARABIC_NAMES[S], tx, 300, 2, 185))
    ev += [(0, 5, "Ref", "SURAH", tx, 385, 2, 46), (0, 5, "Ref", name, tx, 485, 2, fs),
           (0, 5, "Brand", reciter_name.upper(), tx, 560, 8, 34)]
    write_ass(str(ass), (W, H), ev, False)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-i", str(bg), "-frames:v", "1",
                    "-vf", f"setpts=PTS+0.5/TB,ass={ass}:fontsdir={FONTS}", "-q:v", "2", str(out)], check=True)
    assert Path(out).stat().st_size < 2e6
    return out
