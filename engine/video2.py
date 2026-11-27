"""Multi-dua video builder: each dua is a 'part' on its own nature clip, parts are joined,
then the thumbnail frame, ambience and fade-out are added in a final pass."""
import math, os, subprocess, json
from build import (FMT, NATURE, SFX, entry_segments, split_words, render_page, render_thumb, bg_filter, dur)

# Echo on the recitation (owner request). "" = off.
ECHO_PRESETS = {
    "off": "",
    "light": "aecho=0.85:0.8:70|140:0.22|0.12",
    "medium": "aecho=0.85:0.85:90|180|270:0.32|0.2|0.1",
    "strong": "aecho=0.8:0.9:110|220|330|440|550:0.45|0.33|0.23|0.15|0.09",
}
ECHO = ECHO_PRESETS["strong"]  # owner chose stronger than medium (27 Nov)

ENC = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p", "-r", "30"]


def _run(cmd):
    subprocess.run(cmd, check=True)


def make_part(fmt, n, out, clip, page_title, lead=1.0, tail=1.2, first_start=0.0):
    """One dua over one clip with recitation; no ambience, no fades at the edges."""
    _, ref, segs = entry_segments(n)
    seg_d = [dur(s[0]) for s in segs]
    T = lead + sum(seg_d) + 0.6 * (len(segs) - 1) + tail
    cap = 150 if fmt == "portrait" else 210
    pages, t = [], lead
    for (mp3, ar, tr, en), sd in zip(segs, seg_d):
        n_p = max(1, math.ceil(len(ar) / cap), math.ceil(len(en) / (cap * 1.9)))
        A, R, E = split_words(ar, n_p), split_words(tr, n_p), split_words(en, n_p)
        n_p = min(len(A), len(R), len(E))
        w = [len(x) for x in A[:n_p]]
        for i in range(n_p):
            pd = sd * w[i] / sum(w)
            pages.append((t, A[i], R[i], E[i])); t += pd
        t += 0.6
    pngs = []
    for i, (s, a, r, e) in enumerate(pages):
        p = f"{out[:-4]}_p{i}.png"
        render_page(fmt, page_title, a, r, e, f"Hisn al-Muslim {ref}", p); pngs.append(p)
    times = [(first_start if i == 0 else s, T if i == len(pages) - 1 else pages[i + 1][0]) for i, (s, *_) in enumerate(pages)]
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-stream_loop", "-1", "-i", clip]
    for p in pngs:
        cmd += ["-loop", "1", "-t", f"{T:.2f}", "-i", p]
    ai = len(pngs) + 1
    for s in segs:
        cmd += ["-i", s[0]]
    fc = [f"[0:v]{bg_filter(fmt)},trim=0:{T:.3f},setpts=PTS-STARTPTS[b0]"]
    last = "b0"
    for i, (s, e) in enumerate(times):
        fo = min(0.6, (e - s) / 3)
        fin = "" if i == 0 else f"fade=in:st={s:.2f}:d=0.6:alpha=1,"
        fout = "" if i == len(times) - 1 else f"fade=out:st={e-fo:.2f}:d={fo:.2f}:alpha=1"
        chain = (fin + fout).rstrip(",") or "null"
        fc.append(f"[{i+1}:v]format=rgba,{chain}[t{i}]")
        fc.append(f"[{last}][t{i}]overlay=0:0:enable='between(t,{s:.2f},{e:.2f})'[b{i+1}]"); last = f"b{i+1}"
    fc.append(f"[{last}]format=yuv420p[v]")
    parts = []
    for k in range(len(segs)):
        pad = "apad=pad_dur=0.6," if k < len(segs) - 1 else ""
        fc.append(f"[{ai+k}:a]aformat=sample_rates=44100:channel_layouts=stereo,{pad}asetpts=PTS-STARTPTS[s{k}]"); parts.append(f"[s{k}]")
    fc.append(f"{''.join(parts)}concat=n={len(segs)}:v=0:a=1,{ECHO + "," if ECHO else ""}loudnorm=I=-16:TP=-1.5,aresample=44100,adelay={int(lead*1000)}:all=1,apad,atrim=0:{T:.3f}[a]")
    cmd += ["-filter_complex", ";".join(fc), "-map", "[v]", "-map", "[a]", "-t", f"{T:.3f}", *ENC,
            "-c:a", "aac", "-b:a", "160k", "-ar", "44100", out]
    _run(cmd)
    for p in pngs:
        os.remove(p)
    return T


def make_video(fmt, entries, out, rng, thumb_title, page_titles, crf=21):
    """entries: list of entry numbers, page_titles: matching on-screen titles."""
    work = out[:-4] + "_work"; os.makedirs(work, exist_ok=True)
    clips = rng.sample(NATURE, min(len(entries), len(NATURE)))
    while len(clips) < len(entries):
        clips += rng.sample(NATURE, min(len(entries) - len(clips), len(NATURE)))
    part_files, starts, t = [], [], 0.0
    for k, (n, pt) in enumerate(zip(entries, page_titles)):
        pf = f"{work}/part_{k:03d}.mp4"
        T = make_part(fmt, n, pf, clips[k], pt, first_start=0.1 if k == 0 else 0.0)
        part_files.append(pf); starts.append(t); t += T
    total = t
    lst = f"{work}/list.txt"
    with open(lst, "w") as fh:
        fh.writelines(f"file '{os.path.abspath(p)}'\n" for p in part_files)
    joined = f"{work}/joined.mp4"
    _run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", joined])
    # final pass: thumbnail frame, ambience, fade-out
    _, _, segs0 = entry_segments(entries[0])
    thumb = f"{work}/thumb.png"
    render_thumb(fmt, thumb_title, " ".join(segs0[0][1].split()[:6]), thumb)
    sfx = rng.sample(SFX, rng.choice([1, 2]))
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", joined, "-loop", "1", "-t", "0.2", "-i", thumb]
    for s in sfx:
        cmd += ["-stream_loop", "-1", "-i", s]
    fc = [f"[0:v][1:v]overlay=0:0:enable='lt(t,0.1)',fade=out:st={total-0.8:.2f}:d=0.8,format=yuv420p[v]"]
    amb = []
    for j in range(len(sfx)):
        fc.append(f"[{2+j}:a]atrim=start={rng.uniform(0, 20):.1f},asetpts=PTS-STARTPTS,aresample=44100,volume={-12 - 3*(len(sfx)-1)}dB[x{j}]"); amb.append(f"[x{j}]")
    fc.append(f"{''.join(amb)}amix=inputs={len(amb)}:normalize=0[amb]" if len(amb) > 1 else f"{amb[0]}anull[amb]")
    fc.append(f"[0:a][amb]amix=inputs=2:normalize=0:duration=first,afade=in:d=0.3,afade=out:st={total-1.5:.2f}:d=1.5[a]")
    enc = list(ENC); enc[enc.index("-crf") + 1] = str(crf)
    cap = "1250k" if total > 300 else "5M"   # keeps long videos under ~95 MB, the hosting limit
    enc += ["-maxrate", cap, "-bufsize", str(int(cap[:-1]) * 2) + cap[-1]]
    cmd += ["-filter_complex", ";".join(fc), "-map", "[v]", "-map", "[a]", "-t", f"{total:.3f}", *enc,
            "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", out]
    _run(cmd)
    subprocess.run(["rm", "-rf", work])
    return dict(out=out, T=round(total, 1), starts=[round(s, 1) for s in starts],
                sfx=[os.path.basename(s)[:-4] for s in sfx])
