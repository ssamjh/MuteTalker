from flask import Flask, render_template, request, send_file
from flask_socketio import SocketIO, emit
import requests
from datetime import datetime
import os

app = Flask(__name__)
app.config["SECRET_KEY"] = "your_secret_key"
socketio = SocketIO(app)

messages = []

# Set the TTS backend here: 'default' or 'new'
TTS_BACKEND = "default"


@app.route("/")
def index():
    return render_template("index.html")


def use_default_tts_backend(message_text):
    tts_url = "http://tts-api:3000"
    payload = {
        "voice": "gtts_file",
        "textToSpeech": message_text,
        "language": "en",
        "speed": "1",
    }
    response = requests.post(tts_url, json=payload)
    response.raise_for_status()
    return response.content


def use_new_tts_backend(message_text):
    tts_url = "https://sjh.at/sam-tts/process.php"
    payload = {
        "inputText": message_text,
        "version": "7.2",
        "lengthScale": "1.1",
        "noiseW": "0.95",
        "noiseScale": "0.5",
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/png,image/svg+xml,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Content-Type": "application/x-www-form-urlencoded",
        "Origin": "https://sjh.at",
        "Referer": "https://sjh.at/sam-tts/",
    }
    response = requests.post(tts_url, data=payload, headers=headers)
    response.raise_for_status()
    return response.content


@socketio.on("send_message")
def handle_message(data):
    message_text = data["message"]
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        if TTS_BACKEND == "new":
            audio_content = use_new_tts_backend(message_text)
        else:
            audio_content = use_default_tts_backend(message_text)

        with open("output.mp3", "wb") as f:
            f.write(audio_content)

        messages.insert(0, {"text": message_text, "timestamp": timestamp})
        emit(
            "new_message",
            {"text": message_text, "timestamp": timestamp},
            broadcast=True,
        )

        return {"status": "success", "timestamp": timestamp}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.route("/get-messages")
def get_messages():
    return {"messages": messages}


@app.route("/get-audio")
def get_audio():
    try:
        return send_file("output.mp3", mimetype="audio/mpeg", as_attachment=True)
    except FileNotFoundError:
        return "Audio file not found", 404


if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", debug=True, allow_unsafe_werkzeug=True)
