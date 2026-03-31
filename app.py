import discord
from discord import app_commands
import asyncio
import io
import tempfile
import os
import subprocess
import re
import logging

DEBUGGING = os.getenv("DEBUGGING", "False").lower() == "true"

logging.basicConfig(
    level=logging.DEBUG if DEBUGGING else logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)
VOICE_FILE = os.getenv("VOICE_FILE")
TTS_START_COMMAND = os.getenv("TTS_START_COMMAND")
TTS_STOP_COMMAND = os.getenv("TTS_STOP_COMMAND")
active_tts_users = {}
user_timers = {}
guild_queues = {}  # guild_id -> asyncio.Queue
guild_queue_tasks = {}  # guild_id -> asyncio.Task

logging.info("Bot is starting up...")


def remove_urls_and_emojis(text):
    url_pattern = re.compile(
        r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"
    )
    text = url_pattern.sub("", text)

    emoji_pattern = re.compile(r"<a?:[a-zA-Z0-9_]+:[0-9]+>")
    text = emoji_pattern.sub("", text)

    return text.strip()


def get_tts_audio(message_text, speaker_id=None):
    logging.debug(f"Attempting to convert to TTS: {message_text}")
    clean_text = remove_urls_and_emojis(message_text)
    if not clean_text:
        logging.debug("Message is empty after URL and emoji removal")
        return None

    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_file:
        temp_filename = temp_file.name

    logging.debug(f"Running piper with model: {VOICE_FILE}")

    piper_command = ["piper", "--model", VOICE_FILE, "--output_file", temp_filename]

    if speaker_id is not None:
        piper_command.extend(["--speaker", str(speaker_id)])

    logging.debug(f"Piper command: {' '.join(piper_command)}")

    try:
        result = subprocess.run(
            piper_command,
            input=clean_text.encode(),
            check=True,
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
        )
        logging.debug(f"Piper stdout: {result.stdout.decode()}")
        logging.debug(f"Piper stderr: {result.stderr.decode()}")
    except subprocess.CalledProcessError as e:
        logging.error(f"Piper command failed. Exit code: {e.returncode}")
        logging.error(f"Piper stdout: {e.stdout.decode()}")
        logging.error(f"Piper stderr: {e.stderr.decode()}")
        return None

    with open(temp_filename, "rb") as audio_file:
        audio_data = audio_file.read()
    os.unlink(temp_filename)
    logging.debug("TTS conversion successful")
    return audio_data


async def guild_audio_worker(guild_id):
    queue = guild_queues[guild_id]
    while True:
        voice_client, audio_data = await queue.get()
        try:
            if voice_client and voice_client.is_connected():
                audio_source = discord.FFmpegPCMAudio(io.BytesIO(audio_data), pipe=True)
                voice_client.play(audio_source)
                while voice_client.is_playing():
                    await asyncio.sleep(0.1)
        except Exception as e:
            logging.error(f"Error playing audio in guild {guild_id}: {e}")
        finally:
            queue.task_done()


def get_guild_queue(guild_id):
    if guild_id not in guild_queues:
        guild_queues[guild_id] = asyncio.Queue()
        guild_queue_tasks[guild_id] = asyncio.create_task(guild_audio_worker(guild_id))
    return guild_queues[guild_id]


def guild_has_active_users(guild_id):
    return any(
        data["voice_channel"].guild.id == guild_id
        for data in active_tts_users.values()
    )


@tree.command(
    name=TTS_START_COMMAND,
    description="Start TTS monitoring in the current voice channel.",
)
async def cmd_tts_start(interaction: discord.Interaction):
    logging.info(f"TTS start command invoked by {interaction.user.name}")
    if not interaction.user.voice:
        await interaction.response.send_message(
            "You must be in a voice channel to use this command.", ephemeral=True
        )
        return
    if interaction.user.id in active_tts_users:
        await interaction.response.send_message(
            "You already have TTS active.", ephemeral=True
        )
        return
    voice_channel = interaction.user.voice.channel
    text_channel = interaction.channel
    active_tts_users[interaction.user.id] = {
        "voice_channel": voice_channel,
        "text_channel": text_channel,
    }
    logging.info(f"TTS activated for {interaction.user.name} in {voice_channel.name}")
    await interaction.response.send_message(
        f"TTS monitoring started for {interaction.user.display_name} in {voice_channel.name}.",
        ephemeral=True,
    )


@tree.command(
    name=TTS_STOP_COMMAND,
    description="Stop TTS monitoring.",
)
async def cmd_tts_stop(interaction: discord.Interaction):
    logging.info(f"TTS stop command invoked by {interaction.user.name}")
    if interaction.user.id in active_tts_users:
        del active_tts_users[interaction.user.id]
        await interaction.response.send_message(
            "TTS monitoring stopped.", ephemeral=True
        )
        if not guild_has_active_users(interaction.guild.id) and interaction.guild.voice_client:
            await interaction.guild.voice_client.disconnect()
        logging.info(f"TTS deactivated for {interaction.user.name}")
    else:
        await interaction.response.send_message(
            "You are not currently using TTS.", ephemeral=True
        )


async def sync_to_guild(guild: discord.Guild):
    tree.copy_global_to(guild=guild)
    await tree.sync(guild=guild)
    logging.info(f"Commands synced to guild: {guild.name}")


@client.event
async def on_ready():
    for guild in client.guilds:
        await sync_to_guild(guild)
    logging.info(f"{client.user} has connected to Discord!")


@client.event
async def on_guild_join(guild: discord.Guild):
    await sync_to_guild(guild)


@client.event
async def on_message(message):
    logging.debug(f"Message received: {message.content}")
    if message.author.bot:
        logging.debug("Message from bot, ignoring")
        return
    for user_id, data in active_tts_users.items():
        logging.debug(f"Checking message against active TTS user {user_id}")
        if message.author.id == user_id and message.channel == data["text_channel"]:
            logging.debug(f"Message qualifies for TTS: {message.content}")
            voice_channel = data["voice_channel"]
            if voice_channel.guild.voice_client is None:
                logging.info(f"Connecting to voice channel: {voice_channel.name}")
                await voice_channel.connect()
            voice_client = voice_channel.guild.voice_client

            audio_data = get_tts_audio(message.content)

            if audio_data is None:
                logging.debug("Skipped TTS conversion: Empty message after URL removal")
                continue

            queue = get_guild_queue(voice_channel.guild.id)
            await queue.put((voice_client, audio_data))
            break


async def check_user_return(user_id, guild):
    logging.debug(f"Started timer for user {user_id}")
    await asyncio.sleep(30)
    if user_id in user_timers:
        del user_timers[user_id]
        if user_id in active_tts_users:
            del active_tts_users[user_id]
            if not guild_has_active_users(guild.id) and guild.voice_client:
                await guild.voice_client.disconnect()
            logging.info(f"User {user_id} did not return, TTS deactivated")


@client.event
async def on_voice_state_update(member, before, after):
    logging.debug(f"Voice state update for {member.name}")
    if member.id in active_tts_users:
        if before.channel and not after.channel:  # User left the voice channel
            logging.debug(f"{member.name} left voice channel, starting timer")
            user_timers[member.id] = asyncio.create_task(
                check_user_return(member.id, member.guild)
            )
        elif not before.channel and after.channel:  # User joined a voice channel
            if member.id in user_timers:
                logging.debug(
                    f"{member.name} returned to voice channel, cancelling timer"
                )
                user_timers[member.id].cancel()
                del user_timers[member.id]


logging.info("Starting bot...")
client.run(os.getenv("BOT_TOKEN"))
