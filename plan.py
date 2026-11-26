import json, os, cv2, numpy as np
MUSIC_DIR = os.path.join(os.path.dirname(__file__), "music")

def pick_segments(segs):
    ranked, kept = sorted(segs, key=lambda s: -s["score"]), []
    for s in ranked:   # drop near-duplicates
        if s["h"] is not None and any(cv2.compareHist(s["h"], k["h"], cv2.HISTCMP_CORREL) > .92 for k in kept): continue
        kept.append(s)
    good = [s for s in kept if s["score"] > .35] or kept[:3]
    target = float(np.clip(len(good) * 3.2, 15, 90))          # auto duration
    chosen, t = [], 0.0
    for s in good:
        if t >= target: break
        chosen.append(s); t += s["dur"]
    if not chosen: return []
    order = {id(s): i for i, s in enumerate(segs)}
    chosen.sort(key=lambda s: order.get(id(s), 0))             # keep upload/story order
    opener = max(chosen, key=lambda s: s["score"])             # strongest shot opens
    chosen.remove(opener); chosen.insert(0, opener)
    if len(chosen) > 3:                                        # calm, high quality scenic shot closes
        closer = max(chosen[1:], key=lambda s: s["score"] - .1 * s["faces"] - .01 * s["motion"])
        chosen.remove(closer); chosen.append(closer)
    return chosen

def aspect_for(segs):
    p = sum(s["portrait"] for s in segs)
    return "9:16" if p > len(segs) / 2 else "16:9"

def mood_for(segs):
    m = np.mean([s["motion"] for s in segs if s["kind"] == "video"] or [0])
    return "energetic" if m > 9 else "relaxing" if m < 4 else "cinematic"

def choose_music(mood, exclude=None):
    p = os.path.join(MUSIC_DIR, "music.json")
    items = [i for i in json.load(open(p)) if os.path.exists(os.path.join(MUSIC_DIR, i["file"])) and i["file"] != exclude]
    if not items: return None
    same = [i for i in items if i["mood"] == mood]
    return os.path.join(MUSIC_DIR, (same or items)[0]["file"])

def snap_to_beats(segs, music):
    """Adjust each segment duration so cuts land on musical beats."""
    import librosa
    y, sr = librosa.load(music, sr=22050, duration=180)
    _, beats = librosa.beat.beat_track(y=y, sr=sr)
    bt = list(librosa.frames_to_time(beats, sr=sr))
    cur = bt[0] if bt else 0.0; out = []
    for s in segs:
        want = cur + s["dur"]
        nxt = next((b for b in bt if b >= want - .4), want)
        s = dict(s); s["dur"] = max(1.2, nxt - cur); out.append(s); cur = nxt
    return out
