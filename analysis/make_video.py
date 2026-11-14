"""P7: docs/script.md 내레이션(Windows TTS 'Heami') + site/index.html 섹션 스크린샷(Edge headless) + 자막 → site/video.mp4
python analysis/make_video.py
"""
import re
import subprocess
import textwrap
from pathlib import Path

import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "analysis" / "video_build"
OUT.mkdir(exist_ok=True)
FF = imageio_ffmpeg.get_ffmpeg_exe()
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
PAGE = (ROOT / "site" / "index.html").as_uri()
FONT = r"C:\Windows\Fonts\malgunbd.ttf"
W, H = 1280, 720
SECTION = {"S1": "top", "S2": "metrics", "S3": "insight", "S4": "location", "S5": "concept", "S6": "pnl"}

rows = []
for line in (ROOT / "docs" / "script.md").read_text(encoding="utf-8").splitlines():
    m = re.match(r"\|\s*(S\d)\s*\|[^|]*\|[^|]*\|\s*(.+?)\s*\|$", line)
    if m:
        rows.append((m.group(1), m.group(2)))
assert len(rows) == 6, rows

parts = []
for sid, text in rows:
    png, wav, mp4 = OUT / f"{sid}.png", OUT / f"{sid}.wav", OUT / f"{sid}.mp4"
    # 1) screenshot of the section
    url = f"{PAGE}?shot={SECTION[sid]}"
    subprocess.run([EDGE, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
                    f"--user-data-dir={OUT / 'edge'}", f"--window-size={W},{H}",
                    "--virtual-time-budget=4000", f"--screenshot={png}", url], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    # 2) caption bar
    im = Image.open(png).convert("RGB").resize((W, H))
    d = ImageDraw.Draw(im, "RGBA")
    font = ImageFont.truetype(FONT, 26)
    lines = textwrap.wrap(text, 44)[-3:] if len(text) > 132 else textwrap.wrap(text, 44)
    bh = 24 + 38 * len(lines)
    d.rectangle([0, H - bh, W, H], fill=(18, 12, 30, 215))
    for i, ln in enumerate(lines):
        d.text((40, H - bh + 12 + 38 * i), ln, font=font, fill=(255, 255, 255))
    im.save(png)
    # 3) narration
    ps = (f"Add-Type -AssemblyName System.Speech; $s=New-Object System.Speech.Synthesis.SpeechSynthesizer; "
          f"$s.SelectVoice('Microsoft Heami Desktop'); $s.Rate=1; $s.SetOutputToWaveFile('{wav}'); "
          f"$s.Speak([IO.File]::ReadAllText('{OUT / (sid + '.txt')}')); $s.Dispose()")
    (OUT / f"{sid}.txt").write_text(text, encoding="utf-8")
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=True)
    # 4) segment video
    subprocess.run([FF, "-y", "-loglevel", "error", "-loop", "1", "-i", str(png), "-i", str(wav),
                    "-c:v", "libx264", "-tune", "stillimage", "-pix_fmt", "yuv420p", "-r", "30",
                    "-c:a", "aac", "-b:a", "128k", "-af", "apad=pad_dur=0.4", "-shortest", str(mp4)], check=True)
    parts.append(mp4)
    print(sid, "ok", flush=True)

lst = OUT / "list.txt"
lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in parts), encoding="utf-8")
final = ROOT / "site" / "video.mp4"
subprocess.run([FF, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy",
                "-movflags", "+faststart", str(final)], check=True)
dur = subprocess.run([FF, "-i", str(final)], capture_output=True, text=True, errors="ignore").stderr
print(re.search(r"Duration: [\d:.]+", dur).group(0), final)
