from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel
import edge_tts
import uuid
import os
import re
import math
import subprocess
import requests
import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont

app = FastAPI()

FONT_PATH = "/tmp/Prompt-Bold.ttf"

def ensure_thai_font():
    if not os.path.exists(FONT_PATH):
        url = "https://github.com"
        r = requests.get(url, timeout=30)
        with open(FONT_PATH, "wb") as f:
            f.write(r.content)

class TTSRequest(BaseModel):
    input: str
    voice: str = "th-TH-NiwatNeural"
    rate: str = "+5%"

class ReelsRequest(BaseModel):
    topic: str = "AI Work Flow Automation"
    script: str
    voice: str = "th-TH-NiwatNeural"
    rate: str = "+5%"

@app.get("/")
def home():
    return {"status": "Edge TTS & Reels Animation API is running!"}

@app.post("/v1/audio/speech")
async def generate_speech(req: TTSRequest):
    output_file = f"/tmp/{uuid.uuid4()}.mp3"
    communicate = edge_tts.Communicate(req.input, req.voice, rate=req.rate)
    await communicate.save(output_file)
    return FileResponse(output_file, media_type="audio/mpeg", filename="speech.mp3")

def wrap_thai_text(text, font, max_width, draw):
    lines = []
    current = ""
    for ch in text:
        test = current + ch
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = ch
    if current:
        lines.append(current)
    return lines

@app.post("/v1/video/reels")
async def generate_reels_video(req: ReelsRequest):
    ensure_thai_font()
    job_id = str(uuid.uuid4())
    audio_path = f"/tmp/{job_id}.mp3"
    video_path = f"/tmp/{job_id}.mp4"
    frames_dir = f"/tmp/frames_{job_id}"
    os.makedirs(frames_dir, exist_ok=True)

    # 1. สร้างเสียงพากย์และเก็บเวลา (Timestamps) ของแต่ละประโยค
    communicate = edge_tts.Communicate(req.script, req.voice, rate=req.rate)
    subtitles = []
    with open(audio_path, "wb") as f:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                start_sec = chunk["offset"] / 10_000_000
                dur_sec = chunk["duration"] / 10_000_000
                subtitles.append({"start": start_sec, "end": start_sec + dur_sec, "text": chunk["text"]})

    # จัดกลุ่มคำเป็นประโยคสั้นๆ สำหรับขึ้นซับไตเติลให้อ่านง่าย
    raw_sentences = [s.strip() for s in re.split(r'[\n\.!?]+', req.script) if s.strip()]
    total_duration = subtitles[-1]["end"] + 0.8 if subtitles else 10.0
    total_chars = sum(len(s) for s in raw_sentences) or 1

    timed_captions = []
    curr_t = 0.0
    for s in raw_sentences:
        seg_dur = (len(s) / total_chars) * total_duration
        timed_captions.append((curr_t, curr_t + seg_dur, s))
        curr_t += seg_dur

    # 2. วาดเฟรมแอนิเมชัน 1080x1920 ที่ 15 FPS (ประหยัด RAM และลื่นไหล)
    fps = 15
    total_frames = int(math.ceil(total_duration * fps))
    font_brand = ImageFont.truetype(FONT_PATH, 28)
    font_topic = ImageFont.truetype(FONT_PATH, 54)
    font_sub = ImageFont.truetype(FONT_PATH, 46)
    font_cta = ImageFont.truetype(FONT_PATH, 30)

    for frame_idx in range(total_frames):
        t = frame_idx / fps
        img = Image.new("RGB", (1080, 1920), (253, 244, 232)) # พื้นหลังครีมสไตล์ Retro Tech
        draw = ImageDraw.Draw(img)

        # วาดตาราง Grid เคลื่อนไหวเบาๆ ด้านหลัง
        offset = int((t * 30) % 80)
        for gx in range(offset, 1080, 80):
            draw.line([(gx, 0), (gx, 1920)], fill=(242, 228, 210), width=2)
        for gy in range(offset, 1920, 80):
            draw.line([(0, gy), (1080, gy)], fill=(242, 228, 210), width=2)

        # กรอบนอกสไตล์การ์ด Modern Retro
        draw.rectangle([36, 36, 1044, 1884], outline=(24, 24, 27), width=10)

        # ป้ายชื่อเพจด้านบน
        draw.rounded_rectangle([80, 130, 560, 195], radius=30, fill=(249, 115, 22))
        draw.text((110, 143), "AI Work Flow Automation", fill=(255, 255, 255), font=font_brand)

        # พาดหัว Topic ด้านบน
        topic_lines = wrap_thai_text(req.topic, font_topic, 900, draw)[:2]
        ty = 230
        for line in topic_lines:
            draw.text((85, ty), line, fill=(24, 24, 27), font=font_topic)
            ty += 72

        # กล่องแอนิเมชันหุ่นยนต์ AI ขยับขึ้นลงตรงกลางจอ
        bounce = int(math.sin(t * 4) * 18)
        cx, cy = 540, 780 + bounce
        # เงากล่อง
        draw.rectangle([cx - 210, cy - 210, cx + 230, cy + 230], fill=(24, 24, 27))
        # ตัวกล่องสีส้ม-ครีม
        draw.rectangle([cx - 225, cy - 225, cx + 215, cy + 215], fill=(255, 237, 213), outline=(24, 24, 27), width=8)
        # วาดหน้าหุ่นยนต์ Pixel AI ขยับตา
        draw.rectangle([cx - 110, cy - 90, cx + 110, cy + 90], fill=(255, 255, 255), outline=(24, 24, 27), width=8)
        eye_shift = int(math.cos(t * 3) * 10)
        draw.rectangle([cx - 65 + eye_shift, cy - 35, cx - 25 + eye_shift, cy + 5], fill=(249, 115, 22))
        draw.rectangle([cx + 25 + eye_shift, cy - 35, cx + 65 + eye_shift, cy + 5], fill=(249, 115, 22))
        mouth_w = 40 + int(abs(math.sin(t * 10)) * 45) # ปากขยับตามจังหวะพูด
        draw.rectangle([cx - mouth_w, cy + 35, cx + mouth_w, cy + 55], fill=(24, 24, 27))
        # เสาอากาศ
        draw.line([(cx, cy - 90), (cx, cy - 145)], fill=(24, 24, 27), width=8)
        draw.ellipse([cx - 18, cy - 175, cx + 18, cy - 139], fill=(249, 115, 22), outline=(24, 24, 27), width=5)

        # แถบ Progress Bar วิ่งตามเวลาจริง
        progress = min(1.0, t / total_duration)
        draw.rectangle([85, 1100, 995, 1122], fill=(228, 228, 231), outline=(24, 24, 27), width=4)
        draw.rectangle([85, 1100, 85 + int(910 * progress), 1122], fill=(249, 115, 22))

        # 3. กล่องซับไตเติลวิ่งตามเสียงพูดทีละประโยค
        active_caption = ""
        for st, et, cap_text in timed_captions:
            if st <= t <= et:
                active_caption = cap_text
                break
        if not active_caption and timed_captions:
            active_caption = timed_captions[-1][2]

        sub_lines = wrap_thai_text(active_caption, font_sub, 860, draw)[:3]
        box_h = max(140, len(sub_lines) * 65 + 50)
        box_top = 1210
        # เงากล่องซับไตเติล
        draw.rounded_rectangle([85, box_top + 12, 1005, box_top + box_h + 12], radius=24, fill=(24, 24, 27))
        # ตัวกล่องซับไตเติลสีขาวขอบดำ
        draw.rounded_rectangle([75, box_top, 995, box_top + box_h], radius=24, fill=(255, 255, 255), outline=(24, 24, 27), width=6)

        sy = box_top + 25
        for sl in sub_lines:
            bbox = draw.textbbox((0, 0), sl, font=font_sub)
            sw = bbox[2] - bbox[0]
            draw.text(((1080 - sw) // 2, sy), sl, fill=(24, 24, 27), font=font_sub)
            sy += 62

        # ข้อความ CTA ด้านล่างสุด
        draw.text((135, 1610), "กดติดตาม & คอมเมนต์ 'สนใจ' เพื่อรับเทมเพลตฟรี!", fill=(120, 53, 15), font=font_cta)

        img.save(f"{frames_dir}/frame_{frame_idx:05d}.jpg", quality=85)

    # 4. รวมเฟรมทั้งหมดกับเสียงพูด .mp3 เป็นไฟล์ .mp4 ด้วย FFmpeg
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [
        ffmpeg_exe, "-y",
        "-framerate", str(fps),
        "-i", f"{frames_dir}/frame_%05d.jpg",
        "-i", audio_path,
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-shortest",
        video_path
    ]
    subprocess.run(cmd, check=True)

    return FileResponse(video_path, media_type="video/mp4", filename="reels_animation.mp4")
