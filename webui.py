import gradio as gr
import os
import sys
import subprocess
import shutil
import PIL.Image
import re
from faster_whisper import WhisperModel
import torch
import torchaudio
import glob
import time
import random
import yt_dlp
from rembg import remove

# --- Kill lingering background servers ---
gr.close_all()

# --- COLAB BUG FIX: Patch torchaudio so SpeechBrain doesn't crash ---
if not hasattr(torchaudio, 'list_audio_backends'):
    torchaudio.list_audio_backends = lambda: ['soundfile']

# --- TRULY UNIVERSAL PATH LOGIC ---
# This natively detects whatever folder the script is currently inside (e.g. /app/ or /content/vcg_v2/)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

WORK_DIR = os.path.join(BASE_DIR, "VibeVoice")
OUTPUT_DIR = os.path.join(BASE_DIR, "final_outputs")
TEMP_DIR = os.path.join(BASE_DIR, "temp_assets")
STOCK_DIR = os.path.join(BASE_DIR, "stock_videos")

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(STOCK_DIR, exist_ok=True)

OUT_FILE = os.path.join(OUTPUT_DIR, "final_podcast.mp4")

# --- Helper Functions ---
def format_ass_time(seconds):
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    cs = min(int(round((seconds - int(seconds)) * 100)), 99)
    return f"{hours}:{minutes:02d}:{secs:02d}.{cs:02d}"

def get_media_duration(file_path):
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", file_path],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
        )
        return float(result.stdout.strip())
    except:
        return 0.0

def create_padded_avatar(img_path, out_filename, target_height=650, canvas_size=(1080, 1920)):
    out_path = os.path.join(TEMP_DIR, out_filename)
    img = PIL.Image.open(img_path).convert("RGBA")
    
    img = remove(img)

    aspect_ratio = img.width / img.height
    target_width = int(target_height * aspect_ratio)
    img = img.resize((target_width, target_height), PIL.Image.LANCZOS)
    
    canvas = PIL.Image.new("RGBA", canvas_size, (0, 0, 0, 0))
    x = (canvas_size[0] - target_width) // 2
    y = canvas_size[1] - target_height
    canvas.paste(img, (x, y), mask=img)
    canvas.save(out_path, "PNG")
    return out_path.replace('\\', '/')

def get_stock_video_names():
    videos = glob.glob(os.path.join(STOCK_DIR, "*.mp4"))
    return [os.path.basename(v) for v in videos] if videos else []

def archive_and_update_gallery(history):
    if os.path.exists(OUT_FILE):
        timestamp = int(time.time())
        archive_path = os.path.abspath(os.path.join(OUTPUT_DIR, f"short_{timestamp}.mp4"))
        shutil.copy(OUT_FILE, archive_path)
        
        try:
            os.chmod(archive_path, 0o777)
        except Exception as e:
            print(f"Warning: Could not change permissions on {archive_path}: {e}")
            
        new_history = history + [archive_path]
        return new_history, new_history
    return history, history

def lock_ui(btn_text="⏳ Processing..."):
    return gr.update(interactive=False, value=btn_text)

def unlock_ui(btn_text="Generate"):
    return gr.update(interactive=True, value=btn_text)

# --- TAB 3: YouTube Downloader Logic ---
def download_youtube_video(url, progress=gr.Progress()):
    if not url.strip():
        raise gr.Error("Please enter a valid YouTube URL.")
        
    progress(0.2, desc="Fetching video metadata...")
    ydl_opts = {
        'format': 'bestvideo[height=1080][ext=mp4]/bestvideo[height=720][ext=mp4]/bestvideo[height<=1080][ext=mp4]',
        'outtmpl': os.path.join(STOCK_DIR, '%(title)s.%(ext)s'),
        'restrictfilenames': True,
        'noplaylist': True,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            progress(0.6, desc="Downloading video...")
            info_dict = ydl.extract_info(url, download=True)
            video_title = ydl.prepare_filename(info_dict)
            
        filename = os.path.basename(video_title)
        gr.Info(f"Successfully downloaded: {filename}")
        progress(1.0, desc="Download Complete!")
        time.sleep(1)
        
        return gr.update(choices=get_stock_video_names(), value=filename), "✅ Download saved to Stock Library!"
    except Exception as e:
        raise gr.Error(f"Download failed: {str(e)}")

# --- TAB 1: Audio Generation Logic ---
def process_audio_only(language, script_text, ref_1, ref_2, progress=gr.Progress()):
    if not script_text or not ref_1 or not ref_2:
        raise gr.Error("Please provide the script and both audio references.")
        
    yield "⏳ Initializing VibeVoice Model...", None, None
    model_repo = "tarun7r/vibevoice-hindi-1.5B" if language == "Hindi" else "microsoft/VibeVoice-1.5B"
    progress(0.1, desc=f"Loading {model_repo}...")
    
    out_audio = os.path.join(TEMP_DIR, "vibe_podcast.wav")
    voices_dir = os.path.join(WORK_DIR, "demo/voices")
    os.makedirs(voices_dir, exist_ok=True)
    
    subprocess.run(["ffmpeg", "-y", "-i", ref_1, os.path.join(voices_dir, "SpeakerA.wav")], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["ffmpeg", "-y", "-i", ref_2, os.path.join(voices_dir, "SpeakerB.wav")], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    script_path = os.path.join(TEMP_DIR, "script.txt")
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(script_text)
        
    cmd = [
        "python", "demo/inference_from_file.py",
        "--model_path", model_repo,
        "--txt_path", script_path,
        "--speaker_names", "SpeakerA", "SpeakerB",
        "--output_dir", os.path.join(WORK_DIR, "outputs")
    ]
    
    yield "🎙️ Generating AI Voices (This takes a moment)...", None, None
    progress(0.4, desc="Generating voices...")
    try:
        result = subprocess.run(cmd, cwd=WORK_DIR, capture_output=True, text=True)
        gen_file = os.path.join(WORK_DIR, "outputs/script_generated.wav")
        if os.path.exists(gen_file):
            shutil.copy(gen_file, out_audio)
            progress(1.0, desc="Audio Generation Complete!")
            gr.Info("Audio generated successfully! Move to the Video Tab.")
            yield "✅ Audio Generation Complete! Preview available.", out_audio, out_audio
        else:
            raise gr.Error(f"Audio generation failed.\n{result.stderr}")
    except Exception as e:
        raise gr.Error(f"Execution Error: {str(e)}")

# --- TAB 2: Text Alignment & Video Compositing Logic ---
def transcribe_and_align(audio_file, script_text, language):
    unique_speakers = []
    script_words = []
    current_speaker = "SPEAKER_00"
    
    for line in script_text.split('\n'):
        line = line.strip()
        if not line:
            continue
            
        if ':' in line:
            parts = line.split(':', 1)
            if len(parts[0]) < 30: 
                spk_name = parts[0].strip().lower()
                if spk_name not in unique_speakers:
                    unique_speakers.append(spk_name)
                current_speaker = "SPEAKER_00" if unique_speakers.index(spk_name) % 2 == 0 else "SPEAKER_01"
                text_to_parse = parts[1]
            else:
                text_to_parse = line
        else:
            text_to_parse = line
            
        clean_text = re.sub(r'[^\w\s]', '', text_to_parse).lower().split()
        for w in clean_text:
            script_words.append((w, current_speaker))
            
    device = "cuda" if torch.cuda.is_available() else "cpu"
    compute_type = "float16" if device == "cuda" else "int8"
    
    model = WhisperModel("large-v3", device=device, compute_type=compute_type)
    lang_code = "hi" if language == "Hindi" else "en"
    segments, info = model.transcribe(audio_file, word_timestamps=True, language=lang_code)
    
    whisper_words = [word for segment in segments for word in segment.words]
            
    aligned_words = []
    script_idx = 0
    
    ratio = len(script_words) / max(1, len(whisper_words)) if script_words else 1
    
    for w_idx, w in enumerate(whisper_words):
        w_clean = re.sub(r'[^\w\s]', '', w.word).lower().strip()
        if not w_clean: continue
        
        best_match_idx = -1
        if script_words:
            search_end = min(script_idx + 20, len(script_words))
            for i in range(script_idx, search_end):
                if w_clean == script_words[i][0]:
                    best_match_idx = i
                    break
                    
        if best_match_idx != -1:
            script_idx = best_match_idx
            speaker = script_words[script_idx][1]
            script_idx += 1 
        else:
            expected_idx = int(w_idx * ratio)
            if expected_idx > script_idx and expected_idx < len(script_words):
                script_idx = expected_idx
            
            speaker = script_words[min(script_idx, len(script_words)-1)][1] if script_words else "SPEAKER_00"
            
        aligned_words.append({
            "word": w.word.strip().upper(),
            "start": w.start,
            "end": w.end,
            "speaker": speaker
        })
        
    phrases = []
    current_phrase = []
    for w in aligned_words:
        if not current_phrase:
            current_phrase.append(w)
        else:
            if w["speaker"] != current_phrase[-1]["speaker"] or len(current_phrase) >= 4 or (w["start"] - current_phrase[-1]["end"] > 0.8):
                phrases.append(current_phrase)
                current_phrase = [w]
            else:
                current_phrase.append(w)
    if current_phrase:
        phrases.append(current_phrase)
        
    return phrases

def process_video_only(language, script_text, audio_file, avatar_1, avatar_2, bg_video_filename, progress=gr.Progress()):
    if not audio_file or not script_text.strip():
        raise gr.Error("Missing Audio or Script! Please ensure both are provided in Tab 2.")
    if not bg_video_filename or not avatar_1 or not avatar_2:
        raise gr.Error("Please select a background video and both avatars.")

    bg_video_path = os.path.abspath(os.path.join(STOCK_DIR, bg_video_filename)).replace('\\', '/')

    yield "🧠 Transcribing Audio & Aligning Subtitles...", None
    progress(0.1, desc="Transcribing Audio...")
    phrases = transcribe_and_align(audio_file, script_text, language)

    yield "🎬 Removing backgrounds & Preparing Avatars...", None
    progress(0.4, desc="Preparing Avatars...")
    
    blank_path = os.path.abspath(os.path.join(TEMP_DIR, "blank.png")).replace('\\', '/')
    PIL.Image.new("RGBA", (1080, 1920), (0, 0, 0, 0)).save(blank_path, "PNG")
    
    spk0_png = create_padded_avatar(avatar_1, "spk0_padded.png")
    spk1_png = create_padded_avatar(avatar_2, "spk1_padded.png")

    avatar_timeline = []
    for phrase in phrases:
        spk = phrase[0]["speaker"]
        start = phrase[0]["start"]
        end = phrase[-1]["end"] + 0.2
        
        if not avatar_timeline:
            avatar_timeline.append({"speaker": spk, "start": start, "end": end})
        else:
            if avatar_timeline[-1]["speaker"] == spk:
                avatar_timeline[-1]["end"] = end
            else:
                if start > avatar_timeline[-1]["end"]:
                    avatar_timeline[-1]["end"] = start
                avatar_timeline.append({"speaker": spk, "start": start, "end": end})

    concat_path = os.path.abspath(os.path.join(TEMP_DIR, "avatars.txt")).replace('\\', '/')
    current_time = 0.0
    with open(concat_path, "w") as f:
        for clip in avatar_timeline:
            img_path = spk0_png if clip["speaker"] == "SPEAKER_00" else spk1_png
            if clip["start"] > current_time:
                gap = clip["start"] - current_time
                f.write(f"file '{blank_path}'\nduration {gap:.3f}\n")
                current_time += gap
            duration = clip["end"] - clip["start"]
            if duration > 0:
                f.write(f"file '{img_path}'\nduration {duration:.3f}\n")
                current_time += duration
        f.write(f"file '{blank_path}'\n") 

    yield "📝 Generating Karaoke Subtitle File...", None
    progress(0.6, desc="Writing ASS Subtitles...")
    ass_path = os.path.abspath(os.path.join(TEMP_DIR, "captions.ass")).replace('\\', '/')
    ass_header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,90,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,5,0,2,40,40,900,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"""
    
    with open(ass_path, "w", encoding="utf-8") as f:
        f.write(ass_header)
        for phrase_idx, phrase in enumerate(phrases):
            for i, target_word in enumerate(phrase):
                t_start = target_word["start"]
                if i + 1 < len(phrase):
                    t_end = phrase[i+1]["start"]
                else:
                    t_end = target_word["end"] + 0.2
                    if phrase_idx + 1 < len(phrases):
                        next_phrase_start = phrases[phrase_idx + 1][0]["start"]
                        if t_end > next_phrase_start:
                            t_end = next_phrase_start
                
                styled_words = []
                for j, w in enumerate(phrase):
                    if j == i:
                        styled_words.append(f"{{\\c&H00FFFF&}}{w['word']}{{\\c&HFFFFFF&}}")
                    else:
                        styled_words.append(w['word'])
                        
                line_text = " ".join(styled_words)
                f.write(f"Dialogue: 0,{format_ass_time(t_start)},{format_ass_time(t_end)},Default,,0,0,0,,{line_text}\n")

    yield "✂️ Compositing Video (This may take a minute)...", None
    progress(0.7, desc="Initiating FFmpeg Compositor...")
    
    audio_dur = get_media_duration(audio_file)
    bg_dur = get_media_duration(bg_video_path)
    
    max_start = max(0, bg_dur - audio_dur)
    random_start = random.uniform(0, max_start)
    
    ass_filter_path = ass_path.replace('\\', '/').replace(':', '\\:')
    
    vcodec = "libx264"
    if torch.cuda.is_available():
        try:
            res = subprocess.run(["ffmpeg", "-encoders"], capture_output=True, text=True)
            if "h264_nvenc" in res.stdout:
                vcodec = "h264_nvenc"
        except:
            pass

    ffmpeg_cmd = [
        "ffmpeg", "-y",
        "-stream_loop", "-1", 
        "-ss", f"{random_start:.3f}", 
        "-i", bg_video_path, 
        "-f", "concat", "-safe", "0", "-i", concat_path,                          
        "-i", os.path.abspath(audio_file).replace('\\', '/'),                     
        
        "-filter_complex", 
        f"[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=60[bg_scaled]; "
        f"[1:v]fps=60[av_sync]; "
        f"[bg_scaled][av_sync]overlay=0:0:format=auto,ass='{ass_filter_path}'[final_v]",
        
        "-map", "[final_v]",
        "-map", "2:a",
        
        "-af", "loudnorm=I=-14:LRA=11:TP=-1.0",
        "-c:v", vcodec
    ]
    
    if vcodec == "libx264":
        ffmpeg_cmd.extend(["-preset", "ultrafast", "-crf", "23"])
    else:
        ffmpeg_cmd.extend(["-preset", "p4", "-cq", "28"]) 
        
    ffmpeg_cmd.extend([
        "-pix_fmt", "yuv420p", 
        "-c:a", "aac", 
        "-b:a", "192k", 
        "-r", "60", 
        "-shortest",            
        OUT_FILE
    ])

    process = subprocess.Popen(ffmpeg_cmd, stderr=subprocess.PIPE, universal_newlines=True)
    
    ffmpeg_error_log = ""
    for line in process.stderr:
        ffmpeg_error_log += line
        if "time=" in line:
            match = re.search(r"time=(\d+):(\d+):(\d+\.\d+)", line)
            if match and audio_dur > 0:
                h, m, s = map(float, match.groups())
                current_time = h * 3600 + m * 60 + s
                percent = min(current_time / audio_dur, 0.99)
                progress(0.7 + (percent * 0.29), desc=f"Rendering: {int(percent * 100)}%")
                
    process.wait()
    
    if process.returncode != 0:
        crash_reason = "\n".join(ffmpeg_error_log.split("\n")[-15:])
        raise gr.Error(f"FFmpeg Crash: {crash_reason}")

    progress(1.0, desc="Render Complete!")
    gr.Info("Video successfully generated!")
    yield "✅ Final Render Complete!", OUT_FILE

# --- 4. Custom Black & White Theme Configuration ---
bw_theme = gr.themes.Base().set(
    body_background_fill_dark="#000000",
    block_background_fill_dark="#000000",
    block_border_color_dark="#FFFFFF",
    block_border_width="1px",
    body_text_color_dark="#FFFFFF",
    block_title_text_color_dark="#FFFFFF",
    input_background_fill_dark="#000000",
    input_border_color_dark="#FFFFFF",
    input_placeholder_color_dark="#888888",
    button_primary_background_fill_dark="#FFFFFF",
    button_primary_text_color_dark="#000000",
    button_secondary_background_fill_dark="#FFFFFF",
    button_secondary_text_color_dark="#000000",
    border_color_primary_dark="#FFFFFF",
    background_fill_secondary_dark="#000000", 
)

custom_css = """
.fixed-height-btn {
    height: 42px !important; 
    min-height: 42px !important;
}
.tab-nav {
    border-bottom: 2px solid #FFFFFF !important;
}
.black-text-radio {
    background-color: #FFFFFF !important;
    border-radius: 8px;
    padding: 10px;
}
.black-text-radio * {
    color: #000000 !important;
}
"""

dark_mode_js = """
function() { document.body.classList.add('dark'); }
"""

with gr.Blocks(theme=bw_theme, css=custom_css, js=dark_mode_js) as ui:
    
    gr.Markdown("# 🎬 Viral Conversational Shorts Generator")
    gallery_history = gr.State([])
    
    with gr.Tabs():
        
        # TAB 1: AUDIO GENERATION
        with gr.TabItem("🎙️ 1. Audio Engine"):
            with gr.Row():
                with gr.Column(scale=1):
                    language_toggle = gr.Radio(
                        choices=["English", "Hindi"], value="English", label="Script Language", elem_classes=["black-text-radio"]
                    )
                    script_in = gr.Textbox(label="Podcast Script", lines=10, max_lines=12, placeholder="Speaker 1: ...\nSpeaker 2: ...")
                    ref_audio_1 = gr.Audio(type="filepath", label="Speaker 1 Audio")
                    ref_audio_2 = gr.Audio(type="filepath", label="Speaker 2 Audio")
                    
                with gr.Column(scale=1):
                    generate_audio_btn = gr.Button("Generate Audio", variant="primary")
                    audio_status = gr.Textbox(label="Audio Engine Status", interactive=False, lines=2)
                    audio_out = gr.Audio(label="Generated Podcast Audio Preview", type="filepath")
                    
        # TAB 2: VIDEO COMPOSITING
        with gr.TabItem("🎞️ 2. Video Engine"):
            with gr.Row():
                with gr.Column(scale=1):
                    tab2_audio_in = gr.Audio(type="filepath", label="Podcast Audio (Auto-filled or Upload manually)")
                    
                    tab2_script_in = gr.Textbox(label="Podcast Script (Auto-filled or Paste manually)", lines=8, placeholder="Speaker 1: ...\nSpeaker 2: ...")
                    
                    gr.HTML("<span style='color: #FFFFFF; font-size: 14px; margin-bottom: 5px; margin-top: 15px; display: block;'>Background Video</span>")
                    with gr.Row():
                        bg_dropdown = gr.Dropdown(choices=get_stock_video_names(), show_label=False, scale=6)
                        refresh_btn = gr.Button("↻", scale=1, elem_classes=["fixed-height-btn"])
                        
                    with gr.Row():
                        avatar_1 = gr.Image(type="filepath", label="Speaker 1 Avatar (Auto BG Removal)", image_mode="RGBA")
                        avatar_2 = gr.Image(type="filepath", label="Speaker 2 Avatar (Auto BG Removal)", image_mode="RGBA")
                        
                with gr.Column(scale=1):
                    generate_video_btn = gr.Button("Generate Final Short", variant="primary")
                    video_status = gr.Textbox(label="Video Engine Status", interactive=False, lines=2)
                    
                    main_video_out = gr.Video(label="Final Generated Video", interactive=False)
                    video_gallery = gr.Gallery(label="Generated Video Library", columns=2, object_fit="contain", height="300px", allow_preview=True)

            generate_audio_btn.click(
                fn=lambda: lock_ui("⏳ Generating..."), outputs=generate_audio_btn, queue=False
            ).then(
                fn=process_audio_only, inputs=[language_toggle, script_in, ref_audio_1, ref_audio_2], outputs=[audio_status, audio_out, tab2_audio_in]
            ).then(
                fn=lambda s: s, inputs=[script_in], outputs=[tab2_script_in], queue=False
            ).then(
                fn=lambda: unlock_ui("Generate Audio"), outputs=generate_audio_btn, queue=False
            )

            refresh_btn.click(fn=lambda: gr.update(choices=get_stock_video_names()), inputs=None, outputs=bg_dropdown)

            generate_video_btn.click(
                fn=lambda: lock_ui("⏳ Compositing..."), outputs=generate_video_btn, queue=False
            ).then(
                fn=process_video_only, inputs=[language_toggle, tab2_script_in, tab2_audio_in, avatar_1, avatar_2, bg_dropdown], outputs=[video_status, main_video_out]
            ).then(
                fn=archive_and_update_gallery, inputs=[gallery_history], outputs=[gallery_history, video_gallery]
            ).then(
                fn=lambda: unlock_ui("Generate Final Short"), outputs=generate_video_btn, queue=False
            )

        # TAB 3: STOCK DOWNLOADER
        with gr.TabItem("📥 3. Stock Downloader"):
            gr.Markdown("### YouTube Video Downloader")
            with gr.Row():
                with gr.Column(scale=2):
                    yt_url_input = gr.Textbox(label="YouTube URL", placeholder="https://www.youtube.com/watch?v=...")
                    download_btn = gr.Button("Download & Add to Library", variant="primary")
                    download_status = gr.Textbox(label="Status", interactive=False)
                with gr.Column(scale=1): pass 

            download_btn.click(
                fn=lambda: lock_ui("📥 Downloading..."), outputs=download_btn, queue=False
            ).then(
                fn=download_youtube_video, inputs=[yt_url_input], outputs=[bg_dropdown, download_status]
            ).then(
                fn=lambda: unlock_ui("Download & Add to Library"), outputs=download_btn, queue=False
            )

if __name__ == "__main__":
    ui.queue().launch(
        server_name="0.0.0.0", 
        server_port=7860, 
        share=True,
        inline=False,
        allowed_paths=[OUTPUT_DIR, TEMP_DIR, WORK_DIR, STOCK_DIR]
    )
