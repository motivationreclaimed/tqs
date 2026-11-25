"""Pick duas for each video slot (no repeats until a pool runs out) and write titles/captions."""
import json, os, random, re
from build import CAT, entry_segments, dur
from names import NAMES

STATE = "/home/claude/dua_videos/state.json"
EMAIL_LINE = "If you notice any mistake or issue in this video, please contact us at tdh@reclaivo.com"
CREDITS = ("Recitation: Muhammad Jumah for OpenDua\n"
           "Arabic, transliteration and translation: OpenDua (opendua.org), CC BY 4.0\n"
           "Source: Hisn al-Muslim (Fortress of the Muslim) by Sa'id bin Ali bin Wahf Al-Qahtani")
EXCLUDE_SHORT = {192}  # dua before intimacy: keep off short-form feeds
BASE_TAGS = ["#dua", "#islam", "#hisnulmuslim", "#theduahour", "#muslim", "#sunnah"]
CAT_TAGS = {
    "Waking & Daily Life": ["#dailyduas", "#morningroutine"], "Wudu & the Masjid": ["#wudu", "#masjid"],
    "Duas in Salah": ["#salah", "#prayer"], "After Salah": ["#salah", "#dhikr"],
    "Morning & Evening": ["#adhkar", "#morningadhkar"], "Sleep & Night": ["#sleep", "#nightdua"],
    "Worry, Hardship & Guidance": ["#anxiety", "#tawakkul"], "Protection": ["#protection", "#ruqyah"],
    "Family & Relationships": ["#family", "#marriage"], "Sickness & Death": ["#shifa", "#akhirah"],
    "Weather & Nature": ["#rain", "#nature"], "Food & Fasting": ["#ramadan", "#fasting"],
    "Manners & Social Life": ["#adab", "#akhlaq"], "Travel": ["#travel", "#safar"],
    "Hajj & Umrah": ["#hajj", "#umrah"], "Dhikr & Forgiveness": ["#dhikr", "#istighfar"],
}


SPECIAL = {75: "Ayat al-Kursi", 76: "The Three Quls", 79: "Sayyid al-Istighfar", 88: "Ya Hayyu Ya Qayyum",
           86: "Bismillahilladhi La Yadurru", 83: "Hasbiyallahu La Ilaha Illa Huwa", 87: "Raditu Billahi Rabba",
           82: "Dua for Health of Body, Hearing and Sight", 84: "Dua for Pardon and Wellbeing", 70: "The Three Quls After Salah", 71: "Ayat al-Kursi After Salah", 73: "Dua for Beneficial Knowledge After Fajr",
           95: "Dua for Beneficial Knowledge",
           99: "The Three Quls Before Sleeping", 100: "Ayat al-Kursi Before Sleeping",
           101: "Last Two Verses of Surah Al-Baqarah", 102: "Bismika Rabbi Wada'tu Janbi",
           103: "Dua Entrusting Your Soul to Allah", 104: "Dua for Protection on the Day of Resurrection",
           105: "Bismika Allahumma Amutu wa Ahya", 106: "Tasbih, Tahmid and Takbir Before Sleeping",
           107: "Dua to the Lord of the Seven Heavens", 108: "Praise for Food, Drink and Shelter",
           109: "Dua for Refuge from the Evil of the Self", 111: "Dua of Complete Reliance on Allah"}


def info(n):
    title, ref, segs = entry_segments(n)
    name, cat = NAMES[title]
    if n in SPECIAL:
        name = SPECIAL[n]
    d = sum(dur(s[0]) for s in segs) + 0.6 * (len(segs) - 1)
    return dict(n=n, name=name, cat=cat, ref=ref, d=d, segs=segs,
                tr=" ".join(s[2] for s in segs), en=" ".join(s[3] for s in segs))


def all_entries():
    out = []
    for n in range(1, len(CAT["entries"]) + 1):
        e = CAT["entries"][n - 1]
        if e["type"] == "invocation" and entry_segments(n)[2]:
            out.append(info(n))
    return out


def load_state():
    if os.path.exists(STATE):
        return json.load(open(STATE))
    return {"used_short": [], "used_mid": [], "used_long_cats": [], "videos": []}


def save_state(st):
    json.dump(st, open(STATE, "w"), indent=1)


def numbered(names):
    """Disambiguate repeated names in one video: 'Dua Before Sleeping (2)'."""
    seen, out = {}, []
    tot = {x: names.count(x) for x in names}
    for x in names:
        seen[x] = seen.get(x, 0) + 1
        out.append(f"{x} ({seen[x]})" if tot[x] > 1 else x)
    return out


# ---------- picking ----------
def pick_short(st, rng, E, avoid=(), avoid_cats=()):
    pool = [e for e in E if 8 <= e["d"] <= 27 and e["n"] not in EXCLUDE_SHORT and e["n"] not in st["used_short"]
            and e["n"] not in avoid and e["cat"] not in avoid_cats]
    if not pool:
        st["used_short"] = []; return pick_short(st, rng, E, avoid)
    e = rng.choice(pool); st["used_short"].append(e["n"]); return [e]


def pick_mid(st, rng, E, avoid=(), avoid_cats=()):
    """60-90s: one dua that fits, or 2-4 duas from one category."""
    free = [e for e in E if e["n"] not in st["used_mid"] and e["n"] not in EXCLUDE_SHORT and e["d"] <= 85
            and e["n"] not in avoid and e["cat"] not in avoid_cats and e["cat"] != "Sickness & Death"]
    over = lambda es: sum(x["d"] for x in es) + 2.2 * len(es)
    for _ in range(400):
        seed = rng.choice(free)
        group = [seed]
        same = [e for e in free if e["cat"] == seed["cat"] and e["n"] != seed["n"]]
        rng.shuffle(same)
        for e in same:
            if over(group) >= 60 or len(group) >= 4:
                break
            if over(group + [e]) <= 90:
                group.append(e)
        if 60 <= over(group) <= 90:
            group.sort(key=lambda x: x["n"])
            st["used_mid"] += [g["n"] for g in group]
            return group
    st["used_mid"] = []
    return pick_mid(st, rng, E, avoid, avoid_cats)


LONG_PLAN = [  # weekly long videos (~10 min), one category each, in order
    ("Duas Before Sleeping", "Sleep & Night", lambda e: e["name"] in ("Dua Before Sleeping", "Dua When Waking at Night", "Dua for Fear and Loneliness at Night")),
    ("Dhikr After Salah", "After Salah", lambda e: e["cat"] == "After Salah" or e["name"] == "Dua Before Salam"),
    ("Morning & Evening Adhkar (Part 1)", "Morning & Evening", lambda e: e["name"] == "Morning & Evening Adhkar" and e["n"] <= 86),
    ("Morning & Evening Adhkar (Part 2)", "Morning & Evening", lambda e: e["name"] == "Morning & Evening Adhkar" and e["n"] > 86),
    ("Duas for Anxiety, Worry and Hardship", "Worry, Hardship & Guidance", lambda e: e["cat"] == "Worry, Hardship & Guidance"),
    ("Duas for Protection", "Protection", lambda e: e["cat"] == "Protection"),
    ("Duas of Salah", "Duas in Salah", lambda e: e["cat"] == "Duas in Salah" and e["name"] != "Dua Before Salam"),
    ("Duas for Travel", "Travel", lambda e: e["cat"] == "Travel"),
    ("Daily Life Duas from Waking Up to Leaving Home", "Waking & Daily Life", lambda e: e["cat"] in ("Waking & Daily Life", "Wudu & the Masjid")),
    ("Duas for Sickness, Death and the Grave", "Sickness & Death", lambda e: e["cat"] == "Sickness & Death"),
    ("Duas for Food, Fasting, Rain and Nature", "Food & Fasting", lambda e: e["cat"] in ("Food & Fasting", "Weather & Nature")),
    ("Duas for Family, Manners and Everyday Situations", "Family & Relationships", lambda e: e["cat"] in ("Family & Relationships", "Manners & Social Life") and e["n"] != 192),
]


def pick_long(st, rng, E, target=600, max_len=720):
    k = len(st["used_long_cats"]) % len(LONG_PLAN)
    title, cat, test = LONG_PLAN[k]
    es = [e for e in E if test(e)]
    group, t = [], 0
    for e in es:  # keep book order
        if t + e["d"] + 2.2 > max_len:
            continue
        group.append(e); t += e["d"] + 2.2
    st["used_long_cats"].append(title)
    return title, cat, group


# ---------- text ----------
MID_TITLE = {
    "Waking & Daily Life": "Duas for Your Daily Routine", "Wudu & the Masjid": "Duas for Wudu and the Masjid",
    "Duas in Salah": "Duas to Say in Salah", "After Salah": "Duas After Salah", "Morning & Evening": "Morning and Evening Duas",
    "Sleep & Night": "Duas for the Night", "Worry, Hardship & Guidance": "Duas for Hard Times",
    "Protection": "Duas for Protection", "Family & Relationships": "Duas for Your Family",
    "Sickness & Death": "Duas for Illness and Loss", "Weather & Nature": "Duas for Rain and Weather",
    "Food & Fasting": "Duas for Eating and Fasting", "Manners & Social Life": "Duas for Everyday Manners",
    "Travel": "Duas for Travel", "Hajj & Umrah": "Duas for Hajj and Umrah", "Dhikr & Forgiveness": "Duas of Dhikr and Forgiveness",
}
SHORT_OPENERS = ["Learn this dua from the Sunnah:", "A dua every Muslim should know:", "Save this dua for later:",
                 "Recite this and share the reward:", "Make this dua part of your day:", "From Hisn al-Muslim:"]


def hashtags(cat, extra=()):
    """Max 5 hashtags (Instagram/TikTok limit)."""
    return " ".join((["#dua", "#islam", "#hisnulmuslim", "#theduahour"] + CAT_TAGS.get(cat, ["#muslim"]))[:5])


def check(text):
    assert len(text.split("\n")[0]) <= 95, "first line is the YouTube title"
    assert text.count("#") <= 5, "max 5 hashtags"
    assert not re.search("[\u2014\u2013\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0F]", text), "no emojis or dashes"
    assert EMAIL_LINE in text
    return text


def meta_short(e, rng):
    yt_title = f"{e['name']} | Hisn al-Muslim {e['ref']}"
    caption = check(f"{yt_title}\n\n{e['name']} (Hisn al-Muslim {e['ref']}). {rng.choice(SHORT_OPENERS)}\n{e['en']}\n\n"
                    f"{EMAIL_LINE}\n\n{CREDITS}\n\n{hashtags(e['cat'])}")
    return dict(yt_title=yt_title, thumb=e["name"], caption=caption)


def meta_mid(group, rng):
    names = numbered([g["name"] for g in group])
    if len(group) == 1:
        title = group[0]["name"]
    else:
        title = f"{len(group)} {MID_TITLE[group[0]['cat']]}"
    lines = "\n".join(f"- {nm} (Hisn al-Muslim {g['ref']})" for nm, g in zip(names, group))
    intro = rng.choice(["Duas in this video:", "In this video you will learn:", "What you will hear:"])
    yt = f"{title} | Arabic, Transliteration & English"
    caption = check(f"{yt}\n\n{intro}\n{lines}\n\n{EMAIL_LINE}\n\n{CREDITS}\n\n{hashtags(group[0]['cat'])}")
    return dict(yt_title=yt, thumb=title, caption=caption, names=names)


def ts(s):
    s = int(round(s)); return f"{s//60}:{s%60:02d}" if s < 3600 else f"{s//3600}:{(s%3600)//60:02d}:{s%60:02d}"


def meta_long(title, cat, group, starts, total):
    names = numbered([g["name"] for g in group])
    chapters = "\n".join(f"{ts(s)} {nm}" for s, nm in zip(starts, names))
    mins = round(total / 60)
    yt = f"{title} | {mins} Minutes of Authentic Duas | Hisn al-Muslim"
    desc = (f"{title} from Hisn al-Muslim, with Arabic, transliteration and English translation. "
            f"{len(group)} authentic duas in about {mins} minutes, recited calmly over nature sounds.\n\n"
            f"{EMAIL_LINE}\n\n"
            f"Duas in this video:\n{chapters}\n\n{CREDITS}\n\n{EMAIL_LINE}\n\n{hashtags(cat)}")
    check(f"{yt}\n\n{desc}")
    return dict(yt_title=yt, thumb=title, caption=desc, names=names)
