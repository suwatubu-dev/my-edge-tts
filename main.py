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
    node1: str = "รับข้อมูลอัตโนมัติ"
    node2: str = "AI ประมวลผล"
    node3: str = "ส่งผลลัพธ์ทันที"
    bullets: str = ""
    script: str
    voice: str = "th-TH-NiwatNeural"
    rate: str = "+5%"

@app.get("/")
def home():
    return {"status": "Dynamic Workflow Animation API is running!"}

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
            return Response(content=f"Font file {FONT_PATH} not found!", media_type="text/plain", status_code=500)

        job_id = str(uuid.uuid4())
        audio_path = f"/tmp/{job_id}.mp3"
        srt_path = f"/tmp/{job_id}.srt"
        loop_video_path = f"/tmp/{job_id}_loop.mp4"
        final_video_path = f"/tmp/{job_id}.mp4"
        frames_dir = f"/tmp/frames_{job_id}"
        os.makedirs(frames_dir, exist_ok=True)

        # 1. สร้างเสียงพากย์
        communicate = edge_tts.Communicate(req.script, req.voice, rate=req.rate)
        last_end = 0.0
        with open(audio_path, "wb") as f:
            async for chunk in communicate.stream():
                if chunk.get("type") == "audio":
                    f.write(chunk.get("data"))
                elif chunk.get("type") == "WordBoundary":
                    last_end = (chunk.get("offset") + chunk.get("duration")) / 10_000_000

        total_duration = (last_end + 0.6) if last_end > 0 else 45.0

        # 2. สร้างซับไตเติล (.srt)
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

        # 3. วาดแอนิเมชัน Workflow 3 ขั้นตอนตามเนื้อหาข่าว (วนลูป 3 วินาที = 30 เฟรม)
        fps = 10
        loop_seconds = 3
        loop_frames = fps * loop_seconds
        font_brand = ImageFont.truetype(FONT_PATH, 20)
        font_topic = ImageFont.truetype(FONT_PATH, 38)
        font_step = ImageFont.truetype(FONT_PATH, 18)
        font_node = ImageFont.truetype(FONT_PATH, 22)
        font_cta = ImageFont.truetype(FONT_PATH, 22)

        nodes_data = (
            ("STEP 1 : INPUT", req.node1, (16, 185, 129)),
            ("STEP 2 : AI AGENT", req.node2, (168, 85, 247)),
            ("STEP 3 : ACTION", req.node3, (56, 189, 248))
        )

        for frame_idx in range(loop_frames):
            phase = (frame_idx / loop_frames) * (2 * math.pi)
            active_step = frame_idx // 10  # สลับไฮไลต์ทีละกล่อง (0, 1, 2) ทุก 1 วินาที

            img = Image.new("RGB", (720, 1280), (15, 23, 42)) # พื้นหลัง Dark Tech แบบ n8n
            draw = ImageDraw.Draw(img)

            # จุด Grid พื้นหลังสไตล์ n8n Canvas เคลื่อนที่เบาๆ
            offset = int((frame_idx / loop_frames) * 40)
            for gx in range(offset, 720, 40):
                for gy in range(offset, 1280, 40):
                    draw.ellipse((gx - 2, gy - 2, gx + 2, gy + 2), fill=(51, 65, 85))

            # กรอบนอก
            draw.rectangle((20, 20, 700, 1260), outline=(56, 189, 248), width=6)

            # ป้ายชื่อเพจด้านบน
            draw.rounded_rectangle((50, 75, 375, 120), radius=22, fill=(56, 189, 248))
            draw.text((68, 85), "AI Work Flow Automation", fill=(15, 23, 42), font=font_brand)

            # พาดหัว Topic ประจำวัน
            topic_lines = wrap_thai_text(req.topic, font_topic, 610, draw)[:2]
            ty = 145
            for line in topic_lines:
                draw.text((50, ty), line, fill=(255, 255, 255), font=font_topic)
                ty += 50

            # วาดกล่อง Workflow 3 ขั้นตอนแนวตั้งที่สว่างไฮไลต์และขยับตามลำดับการทำงาน
            box_y = 285
            for idx, (step_label, node_text, accent_color) in enumerate(nodes_data):
                is_active = (idx == active_step)
                scale_offset = -8 if is_active else 0
                bg_color = (30, 41, 59) if not is_active else (51, 65, 85)
                border_w = 6 if is_active else 3

                # วาดกล่อง Node
                draw.rounded_rectangle(
                    (70 + scale_offset, box_y + scale_offset, 650 - scale_offset, box_y + 105 - scale_offset),
                    radius=18, fill=bg_color, outline=accent_color, width=border_w
                )
                # แถบสีด้านซ้ายของ Node
                draw.rounded_rectangle(
                    (70 + scale_offset, box_y + scale_offset, 92 + scale_offset, box_y + 105 - scale_offset),
                    radius=8, fill=accent_color
                )
                # ข้อความใน Node
                draw.text((115, box_y + 16), step_label, fill=accent_color, font=font_step)
                clean_node = wrap_thai_text(node_text, font_node, 500, draw)[0] if node_text else ""
                draw.text((115, box_y + 48), clean_node, fill=(255, 255, 255), font=font_node)

                # จุดไฟสถานะวิ่งด้านขวา
                if is_active:
                    pulse = int(abs(math.sin(phase * 3)) * 6)
                    draw.ellipse((605 - pulse, box_y + 42 - pulse, 625 + pulse, box_y + 62 + pulse), fill=accent_color)

                # วาดเส้นเชื่อมและจุดวิ่งระหว่างกล่อง
                if idx < 2:
                    line_top = box_y + 108
                    line_bot = box_y + 148
                    draw.line(((360, line_top), (360, line_bot)), fill=(100, 116, 139), width=4)
                    dot_y = line_top + int(((frame_idx % 10) / 10.0) * (line_bot - line_top))
                    draw.ellipse((353, dot_y - 7, 367, dot_y + 7), fill=(56, 189, 248))

                box_y += 150

            # กล่องพื้นหลังซับไตเติลตรงกลางล่าง
            draw.rounded_rectangle((48, 765, 672, 965), radius=18, fill=(15, 23, 42), outline=(56, 189, 248), width=4)

            # แถบคลื่นเสียงเล็กๆ ด้านล่างซับไตเติล
            bar_x = 225
            for b in range(7):
                bar_h = 8 + int(abs(math.sin(phase * 3 + b)) * 28)
                draw.rounded_rectangle((bar_x, 1025 - bar_h, bar_x + 24, 1025), radius=6, fill=(56, 189, 248))
                bar_x += 40

            # ข้อความ CTA ด้านล่างสุด
            draw.text((82, 1075), "กดติดตาม & คอมเมนต์ 'สนใจ' เพื่อรับเทมเพลตฟรี!", fill=(148, 163, 184), font=font_cta)

            img.save(f"{frames_dir}/frame_{frame_idx:03d}.jpg", quality=85)

        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

        # สร้างคลิปวนลูป 3 วินาที
        subprocess.run((
            ffmpeg_exe, "-y", "-framerate", str(fps),
            "-i", f"{frames_dir}/frame_%03d.jpg",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", loop_video_path
        ), check=True)

        # 4. วนลูปวิดีโอ + ใส่ซับไตเติลภาษาไทยสีขาวคมชัด + รวมเสียงคุณนิวัฒน์
        sub_style = "FontName=Tahoma,FontSize=15,PrimaryColour=&H00FFFFFF,OutlineColour=&H000F172A,BorderStyle=1,Outline=2,Alignment=2,MarginV=355"
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
import uuid
import urllib.request
import subprocess
from fastapi import HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
import edge_tts

class AnimationReelsRequest(BaseModel):
    video_url: str
    script: str
    voice: str = "th-TH-NiwatNeural"
    rate: str = "+5%"

@app.post("/v1/video/reels-animation")
async def create_animation_reels(req: AnimationReelsRequest):
    job_id = str(uuid.uuid4())
    raw_video_path = f"/tmp/{job_id}_raw.mp4"
    audio_path = f"/tmp/{job_id}_voice.mp3"
    output_path = f"/tmp/{job_id}_final.mp4"

    try:
        urllib.request.urlretrieve(req.video_url, raw_video_path)

        communicate = edge_tts.Communicate(req.script, req.voice, rate=req.rate)
        await communicate.save(audio_path)

        cmd = [
            "ffmpeg", "-y",
            "-stream_loop", "-1",
            "-i", raw_video_path,
            "-i", audio_path,
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "128k",
            "-shortest",
            output_path
        ]
        subprocess.run(cmd, check=True)

        return FileResponse(output_path, media_type="video/mp4", filename="reels_animation.mp4")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
