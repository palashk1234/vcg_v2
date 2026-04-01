FROM pytorch/pytorch:2.2.1-cuda12.1-cudnn8-runtime

# Install full FFmpeg and fonts, then NUKE the crippled Conda FFmpeg that PyTorch hides in the PATH
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    wget \
    fontconfig \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/* \
    && rm -f /opt/conda/bin/ffmpeg /opt/conda/bin/ffprobe

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir --no-deps -U yt-dlp

COPY setup.sh entrypoint.sh webui.py ./
RUN chmod +x setup.sh entrypoint.sh

EXPOSE 7860
ENTRYPOINT ["./entrypoint.sh"]