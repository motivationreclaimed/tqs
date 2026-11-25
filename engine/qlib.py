"""Shared paths, Quran text, surah names and subtitle helpers for The Quran Sounds."""
import os, re
from pathlib import Path

ROOT = Path(os.environ.get("TQS_ROOT", Path(__file__).resolve().parents[1]))
FONTS = ROOT / "fonts"
DATA = ROOT / "data"          # verified timings + HOLD/approval notes per reciter/surah
STATE = ROOT / "state"        # posting log
CACHE = Path(os.environ.get("TQS_CACHE", "/tmp/tqs_cache"))  # downloaded audio + clips (not committed)
OUT = Path(os.environ.get("TQS_OUT", "/tmp/tqs_out"))
for d in (CACHE, OUT):
    d.mkdir(parents=True, exist_ok=True)

REPO = "motivationreclaimed/tqs"
ASSETS_TAG = "assets-v1"      # GitHub release holding audio + background clips
VIDEOS_TAG = "videos"         # GitHub release holding rendered videos (public links for Publer)

RECITERS = {
    "mishary": {"name": "Mishary Rashid Alafasy", "url_key": "mishari_al_afasy"},
    "abdulbasit_mujawwad": {"name": "Abdul Basit Abdus-Samad", "url_key": "abdul_baset/mujawwad"},
    "husary": {"name": "Mahmoud Khalil Al-Husary", "url_key": "khalil_al_husary/murattal"},
    "minshawi": {"name": "Muhammad Siddiq Al-Minshawi", "url_key": "siddiq_minshawi/murattal"},
    "shatri": {"name": "Abu Bakr Al-Shatri", "url_key": "abu_bakr_shatri/murattal"},
    "shuraim": {"name": "Saud Al-Shuraim", "url_key": "saud_ash-shuraym/murattal"},
    "sudais": {"name": "Abdul Rahman Al-Sudais", "url_key": "abdurrahmaan_as_sudais/murattal"},
}

NAMES = ("Al-Fatihah,Al-Baqarah,Aal-Imran,An-Nisa,Al-Ma'idah,Al-An'am,Al-A'raf,Al-Anfal,At-Tawbah,Yunus,Hud,"
         "Yusuf,Ar-Ra'd,Ibrahim,Al-Hijr,An-Nahl,Al-Isra,Al-Kahf,Maryam,Ta-Ha,Al-Anbiya,Al-Hajj,Al-Mu'minun,An-Nur,"
         "Al-Furqan,Ash-Shu'ara,An-Naml,Al-Qasas,Al-Ankabut,Ar-Rum,Luqman,As-Sajdah,Al-Ahzab,Saba,Fatir,Ya-Sin,"
         "As-Saffat,Sad,Az-Zumar,Ghafir,Fussilat,Ash-Shura,Az-Zukhruf,Ad-Dukhan,Al-Jathiyah,Al-Ahqaf,Muhammad,"
         "Al-Fath,Al-Hujurat,Qaf,Adh-Dhariyat,At-Tur,An-Najm,Al-Qamar,Ar-Rahman,Al-Waqi'ah,Al-Hadid,Al-Mujadilah,"
         "Al-Hashr,Al-Mumtahanah,As-Saff,Al-Jumu'ah,Al-Munafiqun,At-Taghabun,At-Talaq,At-Tahrim,Al-Mulk,Al-Qalam,"
         "Al-Haqqah,Al-Ma'arij,Nuh,Al-Jinn,Al-Muzzammil,Al-Muddaththir,Al-Qiyamah,Al-Insan,Al-Mursalat,An-Naba,"
         "An-Nazi'at,Abasa,At-Takwir,Al-Infitar,Al-Mutaffifin,Al-Inshiqaq,Al-Buruj,At-Tariq,Al-A'la,Al-Ghashiyah,"
         "Al-Fajr,Al-Balad,Ash-Shams,Al-Layl,Ad-Duha,Ash-Sharh,At-Tin,Al-Alaq,Al-Qadr,Al-Bayyinah,Az-Zalzalah,"
         "Al-Adiyat,Al-Qari'ah,At-Takathur,Al-Asr,Al-Humazah,Al-Fil,Quraysh,Al-Ma'un,Al-Kawthar,Al-Kafirun,"
         "An-Nasr,Al-Masad,Al-Ikhlas,Al-Falaq,An-Nas").split(",")
assert len(NAMES) == 114

# English meanings (for descriptions / thumbnails) and Arabic names — only for surahs in the library.
MEANINGS = {1: "The Opening", 2: "The Cow", 36: "Ya-Sin", 55: "The Most Merciful", 56: "The Inevitable Event",
            67: "The Sovereignty", 93: "The Morning Brightness", 94: "The Relief", 97: "The Night of Decree",
            103: "The Time", 112: "The Sincerity", 113: "The Daybreak", 114: "Mankind"}
ARABIC_NAMES = {1: "سورة الفاتحة", 2: "سورة البقرة", 36: "سورة يس", 55: "سورة الرحمن", 56: "سورة الواقعة",
                67: "سورة الملك", 93: "سورة الضحى", 94: "سورة الشرح", 97: "سورة القدر", 103: "سورة العصر",
                112: "سورة الإخلاص", 113: "سورة الفلق", 114: "سورة الناس"}


def load_text(p):
    d = {}
    for l in open(p, encoding="utf-8"):
        x = l.rstrip("\n").split("|")
        if len(x) == 3 and x[0].isdigit():
            d[(int(x[0]), int(x[1]))] = x[2].strip()
    return d


AR = load_text(ROOT / "text" / "quran-uthmani.txt")       # Tanzil Uthmani text (tanzil.net)
EN = load_text(ROOT / "text" / "en.sahih.txt")            # Saheeh International (via tanzil.net)
BISM_AR, BISM_EN = AR[(1, 1)], EN[(1, 1)]
MARK = re.compile(r"^[ۖ-ۭ]+$")


def _letters(s):
    return re.sub(r"[ً-ٰٟۖ-ۭـ]", "", s)


def strip_bismillah(text, bism=BISM_AR):
    """Remove the Bismillah Tanzil prefixes to verse 1 (exact or variant vowel marks, e.g. 95:1, 97:1)."""
    toks = text.split(" ")
    if len(toks) > 4 and _letters(" ".join(toks[:4])).split() == _letters(bism).split():
        return " ".join(toks[4:]).strip()
    return text


def arabic(s, v):
    t = AR[(s, v)]
    return strip_bismillah(t) if v == 1 and s not in (1, 9) else t


# ---------- ASS subtitles (libass shapes Arabic correctly) ----------
def ass_time(t):
    t = max(0, t)
    return f"{int(t // 3600)}:{int(t % 3600 // 60):02d}:{t % 60:05.2f}"


def ass_escape(t):
    return (t or "").replace("\\", "/").replace("{", "(").replace("}", ")").replace("\n", " ")


def write_ass(path, size, events, vertical):
    """events: (start, end, style, text, x, y, align, fontsize_or_None). All Latin text = bold Times-style serif."""
    w, h = size
    margin = 130 if vertical else 330
    styles = [("Arabic", "Amiri Quran", 80, "&H00FFFFFF", 0, 0),
              ("English", "Liberation Serif", 48, "&H00FFFFFF", -1, 0),
              ("Ref", "Liberation Serif", 46, "&H00FFFFFF", -1, 3),
              ("Brand", "Liberation Serif", 34, "&H00E6E6E6", -1, 3)]
    out = ["[Script Info]", "ScriptType: v4.00+", f"PlayResX: {w}", f"PlayResY: {h}", "WrapStyle: 0",
           "ScaledBorderAndShadow: yes", "", "[V4+ Styles]",
           "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
           "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, "
           "MarginR, MarginV, Encoding"]
    for name, font, fs, col, bold, sp in styles:
        out.append(f"Style: {name},{font},{fs},{col},&H000000FF,&H00000000,&H64000000,{bold},0,0,0,100,100,{sp},0,1,"
                   f"2.5,2,5,{margin},{margin},0,1")
    out += ["", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]
    for (s, e, style, text, x, y, align, fs) in events:
        tag = f"{{\\an{align}\\pos({x},{y})\\fad({0 if s <= 0.001 else 300},300)" + (f"\\fs{fs}" if fs else "") + "}"
        out.append(f"Dialogue: 0,{ass_time(s)},{ass_time(e)},{style},,0,0,0,,{tag}{ass_escape(text)}")
    Path(path).write_text("\n".join(out) + "\n", encoding="utf-8")


def fit_size(text, base, minimum, per_chars):
    return int(max(minimum, min(base, base - len(text or "") / per_chars)))
