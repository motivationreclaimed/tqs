"""Host finished videos and write posts.json for Publer.
Files < 19 MB -> branch tdh-media, served by jsDelivr pinned to the commit (the Quran run never touches it).
Bigger files  -> GitHub Pages folder tdh/ (shared with The Quran Sounds, which force-pushes Pages: upload to
                 Publer straight after this script, and re-run it if Publer says the file is not reachable).
Usage: python3 publish.py <id> [<id> ...]"""
import json, os, random, shutil, subprocess, sys, tempfile
from planner import load_state, info, meta_short, meta_mid, meta_long

REPO = "motivationreclaimed/tqs"
REMOTE = f"https://github.com/{REPO}"
IG, TT, YT = "6b0645f14e667d7eb997d0bf", "6b064625e9a6a63318d8e109", "6b06464ac225c1163f0ce0ef"
OUT = "/home/claude/dua_videos"
SMALL = 19 * 1024 * 1024


def git(d, *a):
    return subprocess.run(["git", "-C", d, *a], check=True, capture_output=True, text=True).stdout.strip()


def captions(v):
    rng = random.Random(v["id"])
    es = [info(n) for n in v["entries"]]
    if v["kind"] == "short":
        return meta_short(es[0], rng)
    if v["kind"] == "mid":
        return meta_mid(es, rng)
    return meta_long(v["title"], v["cat"], es, v["starts"], v["T"])


def push_small(files):
    d = tempfile.mkdtemp()
    git(d, "init", "-q"); git(d, "remote", "add", "origin", REMOTE)
    git(d, "checkout", "-q", "--orphan", "tdh-media")  # only this batch, force-pushed: the repo never grows
    for src, name in files:
        shutil.copy(src, os.path.join(d, name))
    git(d, "add", "-A"); git(d, "-c", "user.name=The Dua Hour", "-c", "user.email=tdh@reclaivo.com", "commit", "-qm", "tdh media")
    git(d, "push", "-q", "-f", "origin", "HEAD:tdh-media")
    sha = git(d, "rev-parse", "HEAD")
    return {name: f"https://cdn.jsdelivr.net/gh/{REPO}@{sha}/{name}" for _, name in files}


def push_big(files):
    d = tempfile.mkdtemp()
    git(d, "init", "-q"); git(d, "remote", "add", "origin", REMOTE)
    git(d, "fetch", "-q", "--depth", "1", "origin", "gh-pages"); git(d, "checkout", "-q", "-b", "gh-pages", "FETCH_HEAD")
    os.makedirs(f"{d}/tdh", exist_ok=True)
    for src, name in files:
        shutil.copy(src, f"{d}/tdh/{name}")
    git(d, "add", "tdh"); git(d, "-c", "user.name=The Dua Hour", "-c", "user.email=tdh@reclaivo.com", "commit", "-qm", "The Dua Hour media")
    git(d, "push", "-q", "origin", "HEAD:gh-pages")
    owner, name_ = REPO.split("/")
    return {name: f"https://{owner}.github.io/{name_}/tdh/{name}" for _, name in files}


def main(ids):
    st = load_state(); byid = {v["id"]: v for v in st["videos"]}
    posts, small, big = [], [], []
    for vid in ids:
        v = byid[vid]; week = vid.split("_")[0][1:]
        m = captions(v)
        shapes = {"short": ["portrait"], "mid": ["portrait"], "long": ["landscape"]}[v["kind"]]  # 16:9 only for videos over 5 minutes
        for shape in shapes:
            src = f"{OUT}/out_week{week}/{vid}_{shape}.mp4"
            assert os.path.exists(src), src
            name = f"tdh-{vid.replace('_', '-')}-{shape}.mp4"
            (small if os.path.getsize(src) < SMALL else big).append((src, name))
            accts = [YT] if v["kind"] == "long" else [IG, TT, YT]
            text = m["caption"] if v["kind"] != "long" else f"{m['yt_title']}\n\n{m['caption']}"
            posts.append(dict(id=vid, shape=shape, name=name, accounts=accts, when=v["when"] + "Z", text=text))
    urls = {}
    if small:
        urls.update(push_small(small))
    if big:
        urls.update(push_big(big))
        print("Pages needs about 90 s to deploy before Publer can fetch the big files.")
    for p in posts:
        p["url"] = urls[p["name"]]
    json.dump(posts, open(f"{OUT}/posts.json", "w"), indent=1, ensure_ascii=False)
    for p in posts:
        print(p["id"], p["shape"], p["when"], p["url"])


if __name__ == "__main__":
    main(sys.argv[1:])
