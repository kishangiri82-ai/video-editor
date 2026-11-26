import subprocess, os
SIZES = {"9:16": (1080, 1920), "16:9": (1920, 1080), "1:1": (1080, 1080)}

def run(cmd): subprocess.run(cmd, check=True, capture_output=True)

def render(segs, aspect, quality, music, workdir, out, progress=lambda p: None):
    W, H = SIZES[aspect]
    if quality == "720p": W, H = int(W * 2 / 3) // 2 * 2, int(H * 2 / 3) // 2 * 2
    parts = []
    for i, s in enumerate(segs):
        o = os.path.join(workdir, f"s{i}.mp4"); d = s["dur"]
        fade = f"fade=t=in:d=.2,fade=t=out:st={max(d-.2,0):.2f}:d=.2"
        grade = "eq=contrast=1.07:saturation=1.12:brightness=0.01,unsharp=3:3:.4"
        if s["kind"] == "photo":
            n = int(d * 30)
            vf = (f"scale={W*2}:{H*2}:force_original_aspect_ratio=increase,crop={W*2}:{H*2},"
                  f"zoompan=z='min(zoom+0.0012,1.15)':d={n}:s={W}x{H}:fps=30,{grade},{fade},format=yuv420p")
            cmd = ["ffmpeg", "-y", "-loop", "1", "-i", s["path"], "-t", f"{d:.2f}", "-vf", vf]
        else:
            vf = (f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps=30,{grade},{fade},format=yuv420p")
            cmd = ["ffmpeg", "-y", "-ss", f"{s['start']:.2f}", "-t", f"{d:.2f}", "-i", s["path"], "-vf", vf]
        run(cmd + ["-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", o])
        parts.append(o); progress((i + 1) / (len(segs) + 1))
    lst = os.path.join(workdir, "list.txt")
    open(lst, "w").write("".join(f"file '{p}'\n" for p in parts))
    silent = os.path.join(workdir, "silent.mp4")
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", silent])
    total = sum(s["dur"] for s in segs)
    if music:
        af = f"atrim=0:{total:.2f},afade=t=in:d=1,afade=t=out:st={max(total-2,0):.2f}:d=2,volume=0.9"
        run(["ffmpeg", "-y", "-i", silent, "-stream_loop", "-1", "-i", music, "-af", af, "-map", "0:v", "-map", "1:a",
             "-t", f"{total:.2f}", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", out])
    else:
        run(["ffmpeg", "-y", "-i", silent, "-c", "copy", "-movflags", "+faststart", out])
    progress(1.0)
