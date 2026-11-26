import cv2, numpy as np
FACE = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

def _feat(f):
    g = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)
    g = cv2.resize(g, (320, max(1, int(320 * g.shape[0] / g.shape[1]))))
    sharp = cv2.Laplacian(g, cv2.CV_64F).var()
    br, over, under = g.mean(), (g > 245).mean(), (g < 15).mean()
    faces = len(FACE.detectMultiScale(g, 1.2, 5, minSize=(30, 30)))
    h = cv2.calcHist([cv2.resize(f, (64, 64))], [0, 1, 2], None, [8, 8, 8], [0, 256] * 3)
    h = cv2.normalize(h, h).flatten()
    q = .55 * min(sharp / 150, 1) + .45 * (1 - min(abs(br - 120) / 120 + 2 * over + 2 * under, 1))
    return g.astype(np.int16), q, faces, h, br

def analyze_photo(path):
    im = cv2.imread(path)
    if im is None: return None
    g, q, faces, h, br = _feat(im)
    return dict(kind="photo", path=path, start=0, dur=2.5, score=q + .2 * min(faces, 2) / 2,
                faces=faces, motion=0, h=h, portrait=im.shape[0] > im.shape[1])

def analyze_video(path, step=0.5, win=3.0, max_per_clip=4):
    cap = cv2.VideoCapture(path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    dur = cap.get(cv2.CAP_PROP_FRAME_COUNT) / fps
    portrait = cap.get(cv2.CAP_PROP_FRAME_HEIGHT) > cap.get(cv2.CAP_PROP_FRAME_WIDTH)
    S, prev, t = [], None, 0.0
    while t < dur:
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, f = cap.read()
        if not ok: break
        g, q, faces, h, br = _feat(f)
        m = float(np.abs(g - prev).mean()) if prev is not None else 0.0
        S.append(dict(t=t, q=q, m=m, f=faces, h=h)); prev = g; t += step
    cap.release()
    k = max(1, int(win / step))
    if len(S) <= k:
        return [dict(kind="video", path=path, start=0, dur=max(dur, .5), score=.3, faces=0, motion=0,
                     h=S[0]["h"] if S else None, portrait=portrait)] if dur > .5 else []
    cuts = {i for i in range(1, len(S)) if cv2.compareHist(S[i-1]["h"], S[i]["h"], cv2.HISTCMP_CORREL) < .6}
    cands = []
    for i in range(len(S) - k):
        w = S[i:i + k]
        mo = np.mean([x["m"] for x in w])
        motion_score = 1 - min(abs(mo - 12) / 12, 1)           # moderate motion preferred (stable but alive)
        shake = np.std([x["m"] for x in w]) > 15                # jerky -> penalise
        sc = .5 * np.mean([x["q"] for x in w]) + .2 * min(max(x["f"] for x in w), 2) / 2 + .3 * motion_score
        sc -= .15 * sum(1 for c in cuts if i < c < i + k) + (.1 if shake else 0)
        cands.append((sc, i, mo, max(x["f"] for x in w)))
    cands.sort(reverse=True); out = []
    for sc, i, mo, fc in cands:
        if len(out) >= max_per_clip: break
        if any(abs(i - o["_i"]) < k for o in out): continue
        out.append(dict(kind="video", path=path, start=S[i]["t"], dur=win, score=float(sc), faces=fc,
                        motion=float(mo), h=S[i]["h"], portrait=portrait, _i=i))
    return sorted(out, key=lambda o: o["start"])
