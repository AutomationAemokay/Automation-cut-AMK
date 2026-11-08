import os
import subprocess
import asyncio
import nest_asyncio
import edge_tts
from google import genai
from faster_whisper import WhisperModel
import gradio as gr

nest_asyncio.apply()

client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

def dur(f):
    res = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", f], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return float(res.stdout)

def run(cmd):
    subprocess.run(cmd, check=True)

def ass_time(secs):
    h = int(secs // 3600)
    m = int((secs % 3600) // 60)
    s = int(secs % 60)
    cs = int(int((secs % 1) * 100))
    return f"{h:d}:{m:02d}:{s:02d}.{cs:02d}"

def ass_color(hex_str):
    h = hex_str.lstrip('#')
    rgb = tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
    return f"&H00{rgb[2]:02x}{rgb[1]:02x}{rgb[0]:02x}"

async def process_video(video_file):
    if video_file is None:
        return "ကျေးဇူးပြု၍ ဗီဒီယိုဖိုင် တင်ပေးပါ။"
    
    p_file = video_file.name if hasattr(video_file, 'name') else video_file
    total_dur = dur(p_file)
    seg_sec = 5 * 60
    
    part_name = "part_000.mp4"
    cmd = ["ffmpeg", "-y", "-ss", "0", "-i", p_file, "-t", str(seg_sec), "-c", "copy", part_name]
    run(cmd)
    
    prompt = "Translate the video context into natural Burmese narration suitable for a movie recap. Keep it engaging."
    response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
    script_text = response.text.strip()
    
    audio_file = "output_audio.mp3"
    communicate = edge_tts.Communicate(script_text, "my-MM-NilarNeural", rate="+0%")
    await communicate.save(audio_file)
    
    model = WhisperModel("base", device="cpu", compute_type="int8")
    segments, _ = model.transcribe(audio_file, beam_size=5)
    
    ass_file = "subtitles.ass"
    with open(ass_file, "w", encoding="utf-8") as af:
        af.write("[Script Info]\nScriptType: v4.00+\nPlayResX: 1920\nPlayResY: 1080\n\n")
        af.write("[V4+ Styles]\n")
        af.write("Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, Italic, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n")
        af.write(f"Style: Default,Noto Sans Myanmar,56,{ass_color('#FFFFFF')},{ass_color('#7A2BFF')},&H00000000,-1,0,1,4,0,2,10,10,30,1\n\n")
        af.write("[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
        for seg in segments:
            start_str = ass_time(seg.start)
            end_str = ass_time(seg.end)
            text = seg.text.strip().replace("\n", " ")
            af.write(f"Dialogue: 0,{start_str},{end_str},Default,,0,0,0,,{text}\n")
            
    out_part = "final_recap_video.mp4"
    ass_escaped = ass_file.replace(":", "\\:")
    vf_str = f"hflip,eq=brightness=0.0:contrast=1.0:saturation=1.0:gamma=1.0,ass='{ass_escaped}'"
    
    cmd = [
        "ffmpeg", "-y", "-i", part_name, "-i", audio_file,
        "-vf", vf_str, "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "aac", "-b:a", "192000", "-map", "0:v:0", "-map", "1:a:0",
        "-shortest", out_part
    ]
    run(cmd)
    return out_part

demo = gr.Interface(
    fn=lambda v: asyncio.run(process_video(v)),
    inputs=gr.Video(label="ဗီဒီယိုဖိုင် တင်ရန်"),
    outputs=gr.Video(label="ထွက်လာမည့် ရုပ်ရှင်ဇာတ်လမ်းပြန် ဗီဒီယို"),
    title="AEMOKAY Movie Recap Generator",
    description="ဖုန်း သို့မဟုတ် ကွန်ပျူတာမှ ဗီဒီယိုတင်ကာ Movie Recap အလိုအလျောက် ပြုလုပ်နိုင်သော Public Website"
)

if __name__ == "__main__":
    demo.launch()
