"""Shared helpers: downloads (via macOS's built-in curl), backgrounds, subtitles, rendering."""
import json, os, random, re, subprocess, sys, html, hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / "cache"
OUT = ROOT / "output"
STATE = ROOT / "state"
FONTS = ROOT / "fonts"
for d in (CACHE, OUT, STATE, FONTS):
    d.mkdir(exist_ok=True)

VERTICAL = (1080, 1920)
LANDSCAPE = (1920, 1080)


def load_config():
    with open(ROOT / "config.json", encoding="utf-8") as f:
        return json.load(f)


def load_state(name, default):
    p = STATE / f"{name}.json"
    return json.loads(p.read_text()) if p.exists() else default


def save_state(name, data):
    (STATE / f"{name}.json").write_text(json.dumps(data, indent=2))


# ---------- downloads ----------
def download(url, dest, headers=None):
    dest = Path(dest)
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["curl", "-fsSL", "--retry", "3", "-m", "300", "-o", str(dest) + ".part", url]
    for k, v in (headers or {}).items():
        cmd[1:1] = ["-H", f"{k}: {v}"]
    r = subprocess.run(cmd)
    if r.returncode != 0:
        Path(str(dest) + ".part").unlink(missing_ok=True)
        raise RuntimeError(f"download failed: {url}")
    os.replace(str(dest) + ".part", dest)
    return dest


def get_json(url, headers=None, cache=True):
    name = hashlib.md5((url + json.dumps(headers or {})).encode()).hexdigest() + ".json"
    p = CACHE / "json" / name
    if not cache:
        p.unlink(missing_ok=True)
    download(url, p, headers)
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        p.unlink(missing_ok=True)
        raise


def duration(path):
    out = subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                   "-of", "default=nw=1:nk=1", str(path)])
    return float(out.strip())


def clean_html(t):
    t = re.sub(r"<sup[^>]*>.*?</sup>", "", t or "", flags=re.S)
    t = re.sub(r"<[^>]+>", "", t)
    return re.sub(r"\s+", " ", html.unescape(t)).strip()


# ---------- backgrounds ----------
def pexels_background(cfg, size, min_seconds):
    """Returns (path, credit) for a free Pexels nature clip, or (None, None)."""
    key = os.environ.get("PEXELS_API_KEY") or cfg.get("pexels_api_key")
    if not key:
        return None, None
    portrait = size[1] > size[0]
    query = random.choice(cfg["background_queries"])
    try:
        data = get_json("https://api.pexels.com/videos/search?" +
                        f"query={query.replace(' ', '%20')}&per_page=40&orientation={'portrait' if portrait else 'landscape'}",
                        headers={"Authorization": key})
    except Exception as e:
        print("  (Pexels unavailable, using generated background)", e)
        return None, None
    vids = [v for v in data.get("videos", []) if v.get("duration", 0) >= min(min_seconds, 8)]
    if not vids:
        return None, None
    v = random.choice(vids)
    files = [f for f in v["video_files"] if f.get("width") and f.get("height")
             and (f["height"] > f["width"]) == portrait and f.get("file_type") == "video/mp4"]
    if not files:
        return None, None
    # smallest file that still covers the frame
    files.sort(key=lambda f: f["width"] * f["height"])
    pick = next((f for f in files if min(f["width"], f["height"]) >= min(size)), files[-1])
    path = download(pick["link"], CACHE / "bg" / f"pexels_{v['id']}_{pick['width']}.mp4")
    return path, f"Video by {v['user']['name']} on Pexels"


# ---------- subtitles (ASS, rendered by libass with proper Arabic shaping) ----------
def ass_time(t):
    t = max(0, t)
    h, m = int(t // 3600), int(t % 3600 // 60)
    return f"{h}:{m:02d}:{t % 60:05.2f}"


def ass_escape(t):
    return (t or "").replace("\\", "/").replace("{", "(").replace("}", ")").replace("\n", " ")


def write_ass(path, size, cfg, events):
    """events: list of (start, end, style, text, x, y, align, fontsize_or_None) ; align = ASS numpad alignment."""
    w, h = size
    f = cfg["fonts"]
    styles = [
        ("Arabic", f["arabic"], 80, "&H00FFFFFF"),
        ("English", f["english"], 48, "&H00FFFFFF"),
        ("Ref", f["english"], 46, "&H00FFFFFF"),
        ("Brand", f["english"], 34, "&H00E6E6E6"),
    ]
    lines = ["[Script Info]", "ScriptType: v4.00+", f"PlayResX: {w}", f"PlayResY: {h}",
             "WrapStyle: 0", "ScaledBorderAndShadow: yes", "", "[V4+ Styles]",
             "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
             "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
             "Alignment, MarginL, MarginR, MarginV, Encoding"]
    margin = int(w * 0.08)
    for name, font, fs, col in styles:
        lines.append(f"Style: {name},{font},{fs},{col},&H000000FF,&H00000000,&H64000000,"
                     f"0,0,0,0,100,100,0,0,1,2.5,2,5,{margin},{margin},0,1")
    lines += ["", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]
    for (s, e, style, text, x, y, align, fs) in events:
        tag = f"{{\\an{align}\\pos({x},{y})\\fad(300,300)" + (f"\\fs{fs}" if fs else "") + "}"
        lines.append(f"Dialogue: 0,{ass_time(s)},{ass_time(e)},{style},,0,0,0,,{tag}{ass_escape(text)}")
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def fit_size(text, base, minimum, per_chars):
    return int(max(minimum, min(base, base - len(text or "") / per_chars)))


# ---------- render ----------
def render(cfg, workdir, audio, ass_file, out, total, size, bg=None):
    w, h = size
    if bg:
        vin = ["-stream_loop", "-1", "-i", str(bg)]
        pre = (f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},fps=30,"
               f"eq=brightness={cfg['background_dim']}:saturation=0.85,")
    else:
        c = random.choice(cfg["gradient_palettes"])
        vin = ["-f", "lavfi", "-i",
               f"gradients=s={w}x{h}:c0={c[0]}:c1={c[1]}:c2={c[2]}:nb_colors=3:x0=0:y0=0:x1={w}:y1={h}"
               f":speed=0.004:rate=30:duration={total + 1}:seed={random.randint(1, 99999)}"]
        pre = "noise=alls=3:allf=t,"
    fontsdir = str(FONTS).replace("'", "")
    vf = pre + f"vignette=PI/5,ass='{Path(ass_file).name}':fontsdir='{fontsdir}',format=yuv420p"
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-stats", *vin, "-i", str(audio),
           "-map", "0:v", "-map", "1:a", "-vf", vf, "-af", "apad",
           "-t", f"{total:.2f}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
           "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(Path(out).resolve())]
    subprocess.run(cmd, check=True, cwd=workdir)


def write_meta(out_mp4, title, description, tags):
    Path(out_mp4).with_suffix(".txt").write_text(
        f"TITLE:\n{title[:100]}\n\nDESCRIPTION:\n{description}\n\nTAGS:\n{', '.join(tags)}\n", encoding="utf-8")


def selftest():
    """Renders a 6-second sample with no internet, to check ffmpeg + fonts work."""
    cfg = load_config()
    work = CACHE / "selftest"; work.mkdir(parents=True, exist_ok=True)
    audio = work / "tone.wav"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                    "sine=frequency=220:duration=5", "-af", "volume=0.05", str(audio)], check=True)
    w, h = VERTICAL
    ar = "بِسْمِ ٱللَّهِ ٱلرَّحْمَـٰنِ ٱلرَّحِيمِ"
    en = "In the name of Allah, the Entirely Merciful, the Especially Merciful."
    ev = [(0, 6, "Ref", "Surah Al-Fatihah · 1:1", w // 2, 300, 8, None),
          (0.2, 6, "Arabic", ar, w // 2, 900, 2, 84),
          (0.2, 6, "English", en, w // 2, 960, 8, 50),
          (0, 6, "Brand", cfg["channel_handle"], w // 2, 1560, 2, None)]
    write_ass(work / "subs.ass", VERTICAL, cfg, ev)
    out = OUT / "selftest.mp4"
    render(cfg, work, audio, work / "subs.ass", out, 6, VERTICAL)
    print("OK ->", out)


if __name__ == "__main__" and "--selftest" in sys.argv:
    selftest()
