# MuteTalker

A Discord bot that reads your text messages aloud in a voice channel using [Piper TTS](https://github.com/rhasspy/piper). Useful if you're muted or prefer to type while in a call.

## How it works

1. Join a voice channel and run `/tts_start` in a text channel
2. Any messages you type in that text channel will be spoken aloud in the voice channel via TTS
3. Run `/tts_stop` to stop (or the bot will auto-disconnect 30 seconds after you leave the voice channel)

URLs and custom Discord emojis are stripped before speaking.

## Setup

### 1. Get a Discord bot token

- Go to the [Discord Developer Portal](https://discord.com/developers/applications)
- Create a new application, add a bot, and copy the token
- Enable the **Message Content** and **Voice States** intents under Bot > Privileged Gateway Intents
- Invite the bot to your server with the `bot` and `applications.commands` scopes, plus `Send Messages`, `Connect`, and `Speak` permissions

### 2. Get Piper voices

Download a voice model from the [Piper voices repository](https://github.com/rhasspy/piper/blob/master/VOICES.md) or the [Hugging Face collection](https://huggingface.co/rhasspy/piper-voices/tree/main).

Each voice requires two files:
- `<voice>.onnx` - the model
- `<voice>.onnx.json` - the config

Place both files in a `voices/` directory inside the project:

```
MuteTalker/
  voices/
    en_US-libritts_r-medium.onnx
    en_US-libritts_r-medium.onnx.json
```

### 3. Configure

Copy `.env.example` to `.env` and fill in your values:

```env
BOT_TOKEN=your-discord-bot-token
VOICE_FILE=/app/voices/en_US-libritts_r-medium.onnx
TTS_START_COMMAND=tts_start
TTS_STOP_COMMAND=tts_stop
DEBUGGING=false
```

`VOICE_FILE` should be the path to your `.onnx` file as it appears **inside the container** (`/app/voices/...`).

### 4. Run with Docker Compose

Edit `docker-compose.yaml` to set your `BOT_TOKEN` and `VOICE_FILE`, then:

```bash
docker compose up -d
```

## Environment variables

| Variable | Description | Default |
|---|---|---|
| `BOT_TOKEN` | Discord bot token | *(required)* |
| `VOICE_FILE` | Path to the `.onnx` voice model | *(required)* |
| `TTS_START_COMMAND` | Slash command name to start TTS | `tts_start` |
| `TTS_STOP_COMMAND` | Slash command name to stop TTS | `tts_stop` |
| `DEBUGGING` | Enable verbose logging | `false` |
