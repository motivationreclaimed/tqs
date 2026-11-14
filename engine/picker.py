"""Endless clip rotation: shuffled deck, every clip used once before any repeats; reshuffles forever."""
import json, random
from pathlib import Path
L = Path(__file__).parent
def next_clips(n, vertical=True, min_seconds=0):
    clips = [c for c in json.load(open(L / "clips.json")) if (c["vertical_ok"] or not vertical) and c["seconds"] >= min_seconds]
    st_p = L / ("deck_v.json" if vertical else "deck_h.json")
    ok = {c["file"] for c in clips}
    deck = [f for f in (json.loads(st_p.read_text()) if st_p.exists() else []) if f in ok]
    out = []
    while len(out) < n:
        if not deck:
            deck = [c["file"] for c in clips]; random.shuffle(deck)
            if out and deck[0] == out[-1]: deck.append(deck.pop(0))
        out.append(deck.pop(0))
    st_p.write_text(json.dumps(deck)); return out
