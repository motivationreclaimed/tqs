"""Plan and render one week (2 posts/day): 7 Shorts, 6 mids (portrait + landscape), 1 long.
Usage: python3 week.py plan <week_no> <start_date YYYY-MM-DD>   |   python3 week.py render <week_no> [id ...]"""
import json, os, random, sys, datetime as dt
from planner import *
from video2 import make_video

ROOT = "/home/claude/dua_videos"
TRIAL_LAST_DAY = dt.date(2026, 12, 8)   # Publer trial: 2 posts a day up to and including this date
ONE_A_DAY = {0: "short", 1: "mid", 2: "short", 3: "mid", 4: "short", 5: "mid", 6: "long"}  # Mon..Sun, 19:00 UK


def slots_for(day):
    """[(kind, 'HH:MM')] for one date. Long video every Sunday evening."""
    if day <= TRIAL_LAST_DAY:
        return [("short", "08:00"), ("long" if day.weekday() == 6 else "mid", "19:00")]
    return [(ONE_A_DAY[day.weekday()], "19:00")]


def plan(week, start):
    st = load_state(); E = all_entries(); rng = random.Random(1000 + week)
    d0 = dt.date.fromisoformat(start)
    items = []
    SLOTS, WHEN = [], []
    for k in range(7):
        day = d0 + dt.timedelta(days=k)
        for kind, hm in slots_for(day):
            SLOTS.append(kind); WHEN.append(f"{day}T{hm}:00")
    # long first, so shorts and mids this week avoid its duas
    lt, lc, lg = pick_long(st, rng, E)
    week_used = {x["n"] for x in lg} | {n for v in st["videos"] if v["id"].startswith(f"w{week}_") for n in v["entries"]}
    mid_cats = [lc]
    for i, kind in enumerate(SLOTS):
        when = WHEN[i]
        vid = f"w{week}_{i+1:02d}_{kind}"
        if any(v["id"] == vid for v in st["videos"]):
            continue
        if kind == "short":
            if week == 1 and i == 0:  # launch post chosen by hand
                continue
            e = pick_short(st, rng, E, week_used)[0]; m = meta_short(e, rng); week_used.add(e["n"])
            items.append(dict(id=vid, kind=kind, when=when, entries=[e["n"]], page_titles=[e["name"]], **m))
        elif kind == "mid":
            g = pick_mid(st, rng, E, week_used, mid_cats); m = meta_mid(g, rng)
            week_used |= {x["n"] for x in g}; mid_cats.append(g[0]["cat"])
            items.append(dict(id=vid, kind=kind, when=when, entries=[x["n"] for x in g], page_titles=m["names"], **m))
        else:
            title, cat, g = lt, lc, lg
            items.append(dict(id=vid, kind=kind, when=when, entries=[x["n"] for x in g], title=title, cat=cat,
                              thumb=title, page_titles=numbered([x["name"] for x in g])))
    st["videos"] += items; save_state(st)
    for it in items:
        print(it["id"], it["when"], it["entries"], it.get("thumb"))


def render(week, ids):
    st = load_state(); os.makedirs(f"{ROOT}/out_week{week}", exist_ok=True)
    for v in st["videos"]:
        if not v["id"].startswith(f"w{week}_") or (ids and v["id"] not in ids):
            continue
        rng = random.Random(hash(v["id"]) & 0xffffffff)
        shapes = {"short": ["portrait"], "mid": ["portrait"], "long": ["landscape"]}[v["kind"]]  # 16:9 only for videos over 5 minutes
        for shape in shapes:
            out = f"{ROOT}/out_week{week}/{v['id']}_{shape}.mp4"
            if os.path.exists(out):
                continue
            r = make_video(shape, v["entries"], out, rng, v["thumb"], v["page_titles"], crf=23 if v["kind"] == "long" else 21)
            v.setdefault("files", {})[shape] = out; v["T"] = r["T"]; v["starts"] = r["starts"]
            if v["kind"] == "long":
                v.update(meta_long(v["title"], v["cat"], [info(n) for n in v["entries"]], r["starts"], r["T"]))
            save_state(st)
            print(v["id"], shape, r["T"], flush=True)


if __name__ == "__main__":
    if sys.argv[1] == "plan":
        plan(int(sys.argv[2]), sys.argv[3])
    else:
        render(int(sys.argv[2]), sys.argv[3:])
