import os
import math
import uuid
import textwrap
import subprocess
import urllib.request
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from PIL import Image, ImageDraw, ImageFont
import edge_tts

app = FastAPI()

FONT_PATH = "/tmp/NotoSansThai.ttf"

def ensure_fonts():
    font_url = "https://githubusercontent.com"
    if not os.path.exists(FONT_PATH) or os.path.getsize(FONT_PATH) < 50000:
        req = urllib.request.Request(font_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req) as resp, open(FONT_PATH, "wb") as out:
            out.write(resp.read())

class ReelsRequest(BaseModel):
    topic: str = "อัปเดต AI Automation ลดงานซ้ำซาก"
    node1: str = "รับข้อมูลอัตโนมัติ"
    node2: str = "AI ประมวลผล"
    node3: str = "ส่งผลลัพธ์ทันที"
    script: str
    voice: str = "th-TH-NiwatNeural"
    rate: str = "+5%"

def get_audio_duration(audio_path: str) -> float:
    cmd = [
        "ffprobe", "-v", "error", "-show_entries",
        "format=duration", "-of",
        "default=noprint_wrappers=1:nokey=1", audio_path
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        return float(result.stdout.strip())
    except Exception:
        return 30.0

def draw_rounded_box(draw, xy, radius, fill, outline=None, width=3):
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)

def render_animation_frames(req: ReelsRequest, frames_dir: str, fps: int = 12, loop_seconds: int = 4):
    ensure_fonts()
    W, H = 720, 1280
    total_frames = fps * loop_seconds

    font_badge = ImageFont.truetype(FONT_PATH, 22)
    font_brand = ImageFont.truetype(FONT_PATH, 22)
    font_title = ImageFont.truetype(FONT_PATH, 46)
    font_step_tag = ImageFont.truetype(FONT_PATH, 20)
    font_node = ImageFont.truetype(FONT_PATH, 30)
    font_sub = ImageFont.truetype(FONT_PATH, 24)

    wrapped_topic = "\n".join(textwrap.wrap(req.topic, width=22))[:90]

    for f in range(total_frames):
        t = f / total_frames
        img = Image.new("RGB", (W, H), (10, 15, 28))
        draw = ImageDraw.Draw(img, "RGBA")

        # 1. พื้นหลัง Cyber Grid เคลื่อนที่
        grid_size = 60
        offset_y = int(t * grid_size)
        for x in range(0, W + grid_size, grid_size):
            draw.line([(x, 0), (x, H)], fill=(30, 41, 59, 110), width=1)
        for y in range(-grid_size, H + grid_size, grid_size):
            draw.line([(0, y + offset_y), (W, y + offset_y)], fill=(30, 41, 59, 110), width=1)

        # 2. วงแสงเรือง (Ambient Glow) ขยับตามจังหวะหายใจ
        pulse = 0.5 + 0.5 * math.sin(t * 2 * math.pi)
        glow_r = int(220 + 30 * pulse)
        draw.ellipse([W//2 - glow_r, 120 - glow_r//2, W//2 + glow_r, 120 + glow_r], fill=(56, 189, 248, 25))
        draw.ellipse([W//2 - glow_r, 820 - glow_r//2, W//2 + glow_r, 820 + glow_r], fill=(168, 85, 247, 25))

        # 3. แถบหัวข้อด้านบน (Header Badge)
        draw_rounded_box(draw, [48, 60, 330, 108], radius=24, fill=(56, 189, 248, 255))
        draw.text((68, 70), "N8N AUTO WORKFLOW", font=font_badge, fill=(10, 15, 28))
        draw.text((350, 70), "AI Work Flow Automation", font=font_brand, fill=(148, 163, 184))

        # 4. พาดหัวเรื่อง (Topic)
        draw.multiline_text((48, 145), wrapped_topic, font=font_title, fill=(255, 255, 255), spacing=12)

        # 5. โครงสร้าง Workflow 3 โหนดแนวตั้ง + เส้นแสงวิ่งเชื่อมโหนด
        nodes = [
            {"tag": "STEP 1 • TRIGGER", "text": req.node1, "color": (16, 185, 129), "y": 390},
            {"tag": "STEP 2 • AI AGENT", "text": req.node2, "color": (168, 85, 247), "y": 620},
            {"tag": "STEP 3 • ACTION", "text": req.node3, "color": (56, 189, 248), "y": 850},
        ]

        # เส้นเชื่อมแนวตั้งตรงกลาง
        draw.line([(W//2, 460), (W//2, 910)], fill=(51, 65, 85, 255), width=6)

        # จุดพลังงานแสงวิ่งไหลจากบนลงล่าง
        orb_y = int(460 + (910 - 460) * t)
        draw.ellipse([W//2 - 14, orb_y - 14, W//2 + 14, orb_y + 14], fill=(56, 189, 248, 120))
        draw.ellipse([W//2 - 7, orb_y - 7, W//2 + 7, orb_y + 7], fill=(255, 255, 255, 255))

        for idx, n in enumerate(nodes):
            ny = n["y"]
            r, g, b = n["color"]
            dist = abs(orb_y - (ny + 65))
            active_boost = max(0, 1 - dist / 140)
            border_w = int(3 + 4 * active_boost)
            bg_alpha = int(215 + 35 * active_boost)

            draw_rounded_box(
                draw,
                [65, ny, W - 65, ny + 135],
                radius=22,
                fill=(20, 28, 46, bg_alpha),
                outline=(r, g, b, 255),
                width=border_w
            )
            draw.text((95, ny + 18), n["tag"], font=font_step_tag, fill=(r, g, b))
            draw.text((95, ny + 56), n["text"][:28], font=font_node, fill=(248, 250, 252))

        # 6. แถบ Audio Visualizer ด้านล่างขยับตามจังหวะเสียง
        num_bars = 28
        bar_w = 12
        gap = 8
        start_x = (W - (num_bars * (bar_w + gap))) // 2
        base_y = 1135
        for i in range(num_bars):
            wave = abs(math.sin((t * 2 * math.pi) + (i * 0.45))) * abs(math.cos((t * 4 * math.pi) - (i * 0.2)))
            bar_h = int(12 + wave * 68)
            bx = start_x + i * (bar_w + gap)
            draw_rounded_box(
                draw,
                [bx, base_y - bar_h, bx + bar_w, base_y],
                radius=6,
                fill=(56, 189, 248, 220)
            )

        # 7. ข้อความ CTA ด้านล่างสุด
        draw.text((135, 1165), "คอมเมนต์ \"สนใจ\" รับคู่มือทำตามฟรี!", font=font_sub, fill=(203, 213, 225))

        img.save(f"{frames_dir}/frame_{f:04d}.png", "PNG")

@app.get("/")
def health_check():
    return {"status": "ok", "service": "my-edge-tts-animation-v2"}

@app.post("/v1/video/reels")
async def generate_reels(req: ReelsRequest):
    job_id = str(uuid.uuid4())
    frames_dir = f"/tmp/{job_id}_frames"
    os.makedirs(frames_dir, exist_ok=True)
    audio_path = f"/tmp/{job_id}_voice.mp3"
    loop_video_path = f"/tmp/{job_id}_loop.mp4"
    output_path = f"/tmp/{job_id}_final.mp4"

    try:
        # 1. สร้างเสียงพากย์ Edge-TTS ภาษาไทย
        communicate = edge_tts.Communicate(req.script, req.voice, rate=req.rate)
        await communicate.save(audio_path)
        duration = get_audio_duration(audio_path)

        # 2. สร้างเฟรมอนิเมชั่นลูป 4 วินาที (48 เฟรม)
        fps = 12
        render_animation_frames(req, frames_dir, fps=fps, loop_seconds=4)

        # 3. รวมเฟรมภาพเป็นวิดีโอลูปสั้นๆ 4 วินาที
        subprocess.run([
            "ffmpeg", "-y",
            "-framerate", str(fps),
            "-i", f"{frames_dir}/frame_%04d.png",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            loop_video_path
        ], check=True)

        # 4. วนลูปวิดีโออนิเมชั่น + ใส่เสียงพากย์ + วิ่งแถบ Progress Bar ด้านล่างจนจบคลิป
        vf_filter = f"drawbox=x=0:y=ih-10:w=iw*(t/{duration}):h=10:color=#38bdf8@0.9:t=fill"
        subprocess.run([
            "ffmpeg", "-y",
            "-stream_loop", "-1",
            "-i", loop_video_path,
            "-i", audio_path,
            "-vf", vf_filter,
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "128k",
            "-shortest",
            output_path
        ], check=True)

        return FileResponse(output_path, media_type="video/mp4", filename="reels_animation.mp4")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
