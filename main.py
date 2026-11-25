from fastapi import FastAPI, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel
import edge_tts
import uuid
import os
import re
import math
import subprocess
import traceback
import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont

app = FastAPI()

FONT_PATH = "tahoma.ttf"

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
    return {"status": "Edge TTS & Rich Animation Reels API is running!"}

@app.post("/v1/audio/speech")
async def generate_speech(req: TTSRequest):
    output_file = f"/tmp/{uuid.uuid4()}.mp3"
    communicate = edge_tts.Communicate(req.input, req.voice, rate=req.rate)
    await communicate.save(output_file)
    return FileResponse(output_file, media_type="audio/mpeg", filename="speech.mp3")

def get_text_width(draw, text, font):
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    return right - left

def wrap_thai_text(text, font, max_width, draw):
    lines = []
    current = ""
    for ch in text:
        test = current + ch
        if get_text_width(draw, test, font) <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = ch
    if current:
        lines.append(current)
    return lines

def format_srt_time(seconds):
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds - int(seconds)) * 1000)
    return f"{hrs:02d}:{mins:02d}:{secs:02d},{millis:03d}"

@app.post("/v1/video/reels")
async def generate_reels_video(req: ReelsRequest):
    try:
        if not os.path.exists(FONT_PATH):
            return Response(content=f"Font file {FONT_PATH} not found in repo!", media_type="text/plain", status_code=500)

        job_id = str(uuid.uuid4())
        audio_path = f"/tmp/{job_id}.mp3"
        srt_path = f"/tmp/{job_id}.srt"
        loop_video_path = f"/tmp/{job_id}_loop.mp4"
        final_video_path = f"/tmp/{job_id}.mp4"
        frames_dir = f"/tmp/frames_{job_id}"
        os.makedirs(frames_dir, exist_ok=True)

        # 1. สร้างเสียงพากย์และวัดความยาวจริง
        communicate = edge_tts.Communicate(req.script, req.voice, rate=req.rate)
        last_end = 0.0
        with open(audio_path, "wb") as f:
            async for chunk in communicate.stream():
                if chunk.get("type") == "audio":
                    f.write(chunk.get("data"))
                elif chunk.get("type") == "WordBoundary":
                    last_end = (chunk.get("offset") + chunk.get("duration")) / 10_000_000

        total_duration = (last_end + 0.6) if last_end > 0 else 45.0

        # 2. สร้างไฟล์ซับไตเติล (.srt) แบ่งตามประโยคและจำนวนตัวอักษร
        raw_sentences = [s.strip() for s in re.split(r'[\n\.!?]+', req.script) if s.strip()]
        total_chars = sum(len(s) for s in raw_sentences) or 1
        curr_t = 0.0
        with open(srt_path, "w", encoding="utf-8") as srt_f:
            for idx, s in enumerate(raw_sentences, start=1):
                seg_dur = (len(s) / total_chars) * total_duration
                srt_f.write(f"{idx}\n")
                srt_f.write(f"{format_srt_time(curr_t)} --> {format_srt_time(curr_t + seg_dur)}\n")
                srt_f.write(f"{s}\n\n")
                curr_t += seg_dur

        # 3. วาดแอนิเมชัน HD 720x1280 วนลูป 2 วินาที (24 เฟรม ที่ 12 FPS)
        fps = 12
        loop_seconds = 2
        loop_frames = fps * loop_seconds
        font_brand = ImageFont.truetype(FONT_PATH, 20)
        font_topic = ImageFont.truetype(FONT_PATH, 38)
        font_cta = ImageFont.truetype(FONT_PATH, 22)

        for frame_idx in range(loop_frames):
            phase = (frame_idx / loop_frames) * (2 * math.pi)
            img = Image.new("RGB", (720, 1280), (253, 244, 232))
            draw = ImageDraw.Draw(img)

            # ตาราง Grid เลื่อนชัดเจน
            offset = int((frame_idx / loop_frames) * 60)
            for gx in range(offset, 720, 60):
                draw.line(((gx, 0), (gx, 1280)), fill=(238, 218, 195), width=3)
            for gy in range(offset, 1280, 60):
                draw.line(((0, gy), (720, gy)), fill=(238, 218, 195), width=3)

            # กรอบนอกสีเปลี่ยนจังหวะ
            border_color = (249, 115, 22) if (frame_idx % 12 < 6) else (24, 24, 27)
            draw.rectangle((24, 24, 696, 1256), outline=border_color, width=10)

            # ป้ายชื่อเพจด้านบน
            draw.rounded_rectangle((56, 85, 365, 130), radius=22, fill=(249, 115, 22))
            draw.text((74, 95), "AI Work Flow Automation", fill=(255, 255, 255), font=font_brand)

            # พาดหัว Topic ด้านบน
            topic_lines = wrap_thai_text(req.topic, font_topic, 600, draw)[:2]
            ty = 155
            for line in topic_lines:
                draw.text((56, ty), line, fill=(24, 24, 27), font=font_topic)
                ty += 50

            # หุ่นยนต์ Pixel AI ลอยขึ้นลงชัดเจน (35px) + ไฟกะพริบ + ปากพูด
            bounce = int(math.sin(phase) * 35)
            cx, cy = 360, 480 + bounce
            draw.rectangle((cx - 135, cy - 135, cx + 148, cy + 148), fill=(24, 24, 27))
            draw.rectangle((cx - 145, cy - 145, cx + 138, cy + 138), fill=(255, 237, 213), outline=(24, 24, 27), width=6)
            draw.rectangle((cx - 75, cy - 60, cx + 75, cy + 60), fill=(255, 255, 255), outline=(24, 24, 27), width=6)
            eye_shift = int(math.cos(phase) * 14)
            draw.rectangle((cx - 48 + eye_shift, cy - 25, cx - 18 + eye_shift, cy + 5), fill=(249, 115, 22))
            draw.rectangle((cx + 18 + eye_shift, cy - 25, cx + 48 + eye_shift, cy + 5), fill=(249, 115, 22))
            mouth_w = 20 + int(abs(math.sin(phase * 4)) * 38)
            draw.rectangle((cx - mouth_w, cy + 22, cx + mouth_w, cy + 40), fill=(24, 24, 27))
            draw.line(((cx, cy - 60), (cx, cy - 98)), fill=(24, 24, 27), width=6)
            bulb_color = (239, 68, 68) if (frame_idx % 6 < 3) else (250, 204, 21)
            draw.ellipse((cx - 15, cy - 122, cx + 15, cy - 92), fill=bulb_color, outline=(24, 24, 27), width=4)

            # แถบคลื่นเสียง Equalizer 7 แท่งเต้นขึ้นลงตลอดเวลา (เห็นความเคลื่อนไหวชัดเจน 100%)
            bar_x = 185
            for b in range(7):
                bar_h = 20 + int(abs(math.sin(phase * 2 + b * 0.9)) * 65)
                draw.rounded_rectangle((bar_x, 735 - bar_h, bar_x + 36, 735), radius=8, fill=(249, 115, 22), outline=(24, 24, 27), width=3)
                bar_x += 52

            # กล่องพื้นหลังซับไตเติลตรงกลางล่าง
            draw.rounded_rectangle((56, 785, 672, 975), radius=18, fill=(24, 24, 27))
            draw.rounded_rectangle((48, 775, 664, 965), radius=18, fill=(255, 255, 255), outline=(24, 24, 27), width=5)

            # ข้อความ CTA ด้านล่างสุด
            draw.text((82, 1075), "กดติดตาม & คอมเมนต์ 'สนใจ' เพื่อรับเทมเพลตฟรี!", fill=(120, 53, 15), font=font_cta)

            img.save(f"{frames_dir}/frame_{frame_idx:03d}.jpg", quality=85)

        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

        # สร้างคลิปวนลูป 2 วินาที
        subprocess.run((
            ffmpeg_exe, "-y", "-framerate", str(fps),
            "-i", f"{frames_dir}/frame_%03d.jpg",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", loop_video_path
        ), check=True)

        # 4. วนลูปวิดีโอ + ใส่ซับไตเติลภาษาไทย + รวมเสียงคุณนิวัฒน์
        sub_style = "FontName=Tahoma,FontSize=15,PrimaryColour=&H001B1818,OutlineColour=&H00FFFFFF,BorderStyle=1,Outline=2,Alignment=2,MarginV=350"
        subprocess.run((
            ffmpeg_exe, "-y",
            "-stream_loop", "-1",
            "-i", loop_video_path,
            "-i", audio_path,
            "-vf", f"subtitles={srt_path}:fontsdir=.:force_style='{sub_style}'",
            "-c:v", "libx264", "-preset", "ultrafast",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-shortest",
            final_video_path
        ), check=True)

        return FileResponse(final_video_path, media_type="video/mp4", filename="reels_animation.mp4")
    except Exception:
        return Response(content=traceback.format_exc(), media_type="text/plain", status_code=500)
