import os, uuid, shutil, glob, traceback
from fastapi import FastAPI, UploadFile, File, BackgroundTasks, HTTPException, Header
from fastapi.responses import FileResponse
from pydantic import BaseModel
import analyze, plan, render as rd

API_KEY = os.environ.get("API_KEY", "change-me")
DATA = os.environ.get("DATA_DIR", "/tmp/vlog")
VID, IMG = {".mp4", ".mov", ".mkv", ".avi"}, {".jpg", ".jpeg", ".png", ".webp"}
app, JOBS = FastAPI(title="AI Auto Video Editor"), {}

def auth(k):
    if k != API_KEY: raise HTTPException(401, "bad key")

@app.post("/projects")
def new_project(x_api_key: str = Header("")):
    auth(x_api_key); pid = uuid.uuid4().hex[:12]; os.makedirs(f"{DATA}/{pid}/media", exist_ok=True); return {"id": pid}

@app.post("/projects/{pid}/media")
async def upload(pid: str, file: UploadFile = File(...), x_api_key: str = Header("")):
    auth(x_api_key); ext = os.path.splitext(file.filename)[1].lower()
    if ext not in VID | IMG: raise HTTPException(400, "unsupported type")
    dst = f"{DATA}/{pid}/media/{uuid.uuid4().hex[:6]}{ext}"
    with open(dst, "wb") as f: shutil.copyfileobj(file.file, f)    # streamed, not loaded in RAM
    return {"ok": True}

class RenderReq(BaseModel):
    aspect: str | None = None      # "9:16" | "16:9" | "1:1" ; None = AI decides
    quality: str = "1080p"
    avoid_music: str | None = None  # used by "replace music"

def job(pid, req, jid):
    J = JOBS[jid]
    try:
        files = sorted(glob.glob(f"{DATA}/{pid}/media/*")); segs = []
        for n, p in enumerate(files):
            J.update(stage="Analyzing your clips", progress=.4 * n / len(files))
            ext = os.path.splitext(p)[1].lower()
            r = analyze.analyze_photo(p) if ext in IMG else analyze.analyze_video(p)
            segs += [r] if isinstance(r, dict) else (r or [])
        J.update(stage="Finding the best moments", progress=.45)
        chosen = plan.pick_segments(segs)
        if not chosen: raise RuntimeError("No usable footage found")
        aspect = req.aspect or plan.aspect_for(chosen)
        J.update(stage="Selecting background music", progress=.5)
        mood = plan.mood_for(chosen); music = plan.choose_music(mood, req.avoid_music)
        if music: chosen = plan.snap_to_beats(chosen, music)
        J.update(stage="Creating your video", progress=.55, music=os.path.basename(music or ""), mood=mood, aspect=aspect,
                 clips=len(chosen), duration=round(sum(s["dur"] for s in chosen), 1))
        out = f"{DATA}/{pid}/out_{jid}.mp4"; os.makedirs(f"{DATA}/{pid}/w{jid}", exist_ok=True)
        rd.render(chosen, aspect, req.quality, music, f"{DATA}/{pid}/w{jid}", out,
                  lambda p: J.update(progress=.55 + .45 * p))
        shutil.rmtree(f"{DATA}/{pid}/w{jid}", ignore_errors=True)
        J.update(status="done", progress=1.0, file=out)
    except Exception as e:
        traceback.print_exc(); J.update(status="error", error=str(e))

@app.post("/projects/{pid}/render")
def start(pid: str, req: RenderReq, bg: BackgroundTasks, x_api_key: str = Header("")):
    auth(x_api_key); jid = uuid.uuid4().hex[:8]
    JOBS[jid] = dict(status="running", stage="Queued", progress=0.0); bg.add_task(job, pid, req, jid); return {"job": jid}

@app.get("/jobs/{jid}")
def status(jid: str, x_api_key: str = Header("")):
    auth(x_api_key); j = dict(JOBS.get(jid) or {}); j.pop("file", None); return j

@app.get("/jobs/{jid}/video")
def video(jid: str, k: str = ""):
    auth(k); return FileResponse(JOBS[jid]["file"], media_type="video/mp4", filename="my_video.mp4")
