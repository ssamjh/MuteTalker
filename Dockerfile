FROM python:3.13-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip
RUN pip install discord.py[voice] PyNaCl piper-tts pathvalidate

COPY voices/*.onnx voices/*.onnx.json ./voices/
COPY app.py .

CMD ["python", "app.py"]
