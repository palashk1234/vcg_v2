# 🎬 Viral Conversational Shorts Generator (VCG_V2)

An automated, end-to-end AI pipeline for generating viral, conversational "Podcast-style" short-form videos. Provide a text script, and this engine will generate the voices, remove the backgrounds from your avatars, align the audio to the text, generate karaoke-style subtitles, and composite the final 1080p vertical video—all running locally or in the cloud.

![UI Screenshot](https://via.placeholder.com/800x400.png?text=Add+Your+Gradio+UI+Screenshot+Here)

## ✨ Features

* **🗣️ AI Voice Generation:** Powered by Microsoft's VibeVoice, generating highly expressive, conversational audio in both English and Hindi.
* **✂️ Auto Background Removal:** Drop in any standard JPG/PNG of a character, and the engine automatically uses `rembg` (U2Net) to slice out the background.
* **⏱️ Smart Subtitle Alignment:** Uses `faster-whisper` to generate word-level timestamps. Features a custom sliding-window failsafe algorithm to ensure avatars swap perfectly even if the AI hallucinates a word.
* **📥 Built-in Stock Downloader:** Paste a YouTube URL, and the engine fetches the highest-quality 1080p/720p video stream to use as your background.
* **🚀 Hardware Accelerated:** Auto-detects NVIDIA GPUs to utilize `float16` Whisper transcription and `h264_nvenc` FFmpeg video encoding.
* **🌍 Universal Deployment:** Write once, run anywhere. Path logic auto-adapts to run flawlessly inside Google Colab or a local Docker container.

---

## 🛠️ Credits & Acknowledgements

This project is a composite UI and pipeline built on top of some of the most incredible open-source AI tools available today. Massive thanks to the maintainers of the following libraries:

* **[VibeVoice](https://github.com/microsoft/VibeVoice):** By Microsoft (and community fine-tunes by Tarun7r). The core Text-to-Speech engine driving the conversational audio.
* **[Faster-Whisper](https://github.com/SYSTRAN/faster-whisper):** By SYSTRAN. Provides the lightning-fast, highly accurate word-level transcription necessary for avatar alignment.
* **[rembg](https://github.com/danielgatis/rembg):** By Daniel Gatis. The magic behind the zero-click avatar background removal.
* **[yt-dlp](https://github.com/yt-dlp/yt-dlp):** For bypassing rate limits and seamlessly pulling high-quality stock footage.
* **[Gradio](https://github.com/gradio-app/gradio):** The web framework powering the entire user interface.
* **[FFmpeg](https://ffmpeg.org/):** The undisputed king of multimedia processing, handling the final video compositing and ASS subtitle rendering.

---

## 🚀 Installation & Setup

### Option A: Run Locally via Docker (Recommended)
Running via Docker ensures you don't clutter your local machine with heavy Python dependencies, FFmpeg binaries, or conflicting libraries.

**Prerequisites:**
* Docker and Docker Compose installed.
* An NVIDIA GPU with CUDA drivers installed (for hardware acceleration).

1. Clone the repository:
   ```bash
   git clone [https://github.com/YOUR_USERNAME/VCG_V2.git](https://github.com/YOUR_USERNAME/VCG_V2.git)
   cd VCG_V2
   ```
2. Build and launch the container:
   ```bash
   docker compose up --build
   ```
3. Open your browser and go to: `http://localhost:7860`

*Note: The first time you generate a video, the engine will download the AI models (~6GB) to your local `./hf_cache` folder so they persist between restarts.*

### Option B: Run on Google Colab
If you don't have a dedicated GPU, you can run this entirely in the cloud.

1. Upload `webui.py`, `requirements.txt`, and `setup.sh` to your Google Drive or Colab environment.
2. Run the following in a Colab notebook cell:
   ```python
   !bash setup.sh
   !pip install -r requirements.txt
   !pip install --no-deps -U yt-dlp
   
   # Launch the UI
   !python webui.py
   ```
3. Click the public `gradio.live` link generated in the terminal.

---

## 📖 How to Use

### 1. Download Backgrounds (Tab 3)
* Paste a YouTube link of satisfying/gameplay footage (e.g., GTA V driving, Minecraft parkour).
* Click **Download & Add to Library**. It will fetch the video without audio.

### 2. Generate Audio (Tab 1)
* Select your language (English or Hindi).
* **IMPORTANT:** Write your script using the strict VibeVoice format: `Speaker 1:` and `Speaker 2:`. 
  * *Example:*
    ```text
    Speaker 1: I have wiped away the noise of the universe.
    Speaker 2: In a garden with no internet? How primitive.
    Speaker 1: I have no need for the networks of men.
    ```
* Upload a 5-10 second clear voice reference for Speaker 1 and Speaker 2.
* Click **Generate Audio**.

### 3. Composite Video (Tab 2)
* The audio and script from Tab 1 will automatically carry over. *(Note: If you are uploading pre-generated audio directly to Tab 2, you can use any custom names in the script box like `Thanos:` and `Ultron:`, but Tab 1 strictly requires the `Speaker 1 / Speaker 2` format).*
* Select your downloaded background video from the dropdown.
* Upload standard JPG/PNG images for Avatar 1 and Avatar 2 (the AI will remove the backgrounds automatically).
* Click **Generate Final Short**. 
* The engine will transcribe, align, and render your video. The final MP4 will appear in the UI and be saved in the `/final_outputs` folder!

---

## ⚠️ Troubleshooting

* **Black Video / No Subtitles?** Ensure your Docker environment has installed `fontconfig` and `fonts-liberation` (this is handled automatically in the provided `Dockerfile`).
* **YouTube Download Failing?** YouTube frequently updates its bot protections. If downloads fail, run `pip install -U yt-dlp --no-deps` to forcefully grab the latest patch.
* **Gradio Dependency Errors?** This project strictly pins `fastapi==0.112.2`, `starlette==0.38.2`, and `pydantic<2.10` to ensure stability against breaking UI updates.

---

## 📜 License
This project is open-source under the MIT License. Please ensure you comply with the respective licenses of the utilized models (VibeVoice, Whisper, U2Net) when using them for commercial purposes.
