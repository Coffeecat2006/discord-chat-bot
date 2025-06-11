import os
import shutil
import asyncio
import whisper
import wave
import audioop
from collections import deque
import threading

from dotenv import load_dotenv
import discord
from discord.ext import commands
from discord.ext import voice_recv

import discord.ext.voice_recv.opus as _vropus
_orig_decode = _vropus.Decoder.decode
def _safe_decode(self, data, fec=False):
    try:
        return _orig_decode(self, data, fec)
    except Exception as e:
        # 當補丁生效時，我們可以在這裡印出一個日誌，但暫時保持安靜
        # logging.warning(f"Opus decode error caught by patch: {e}")
        return b''
_vropus.Decoder.decode = _safe_decode

# Monkey-patch PacketDecryptor to support xchacha20_poly1305_rtpsize using xsalsa20 fallback
import discord.ext.voice_recv.reader as _vr_reader
if not hasattr(_vr_reader.PacketDecryptor, '_decrypt_rtp_aead_xchacha20_poly1305_rtpsize'):
    _vr_reader.PacketDecryptor._decrypt_rtp_aead_xchacha20_poly1305_rtpsize = _vr_reader.PacketDecryptor._decrypt_rtp_xsalsa20_poly1305
if not hasattr(_vr_reader.PacketDecryptor, '_decrypt_rtcp_aead_xchacha20_poly1305_rtpsize'):
    _vr_reader.PacketDecryptor._decrypt_rtcp_aead_xchacha20_poly1305_rtpsize = _vr_reader.PacketDecryptor._decrypt_rtcp_xsalsa20_poly1305

from google import genai
from google.genai import types
import tempfile
import requests
import json
import re

load_dotenv()
TOKEN = os.getenv('BOT_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
CHARACTER_CARD = os.getenv('CHARACTER_CARD')

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='/', intents=intents)

client = genai.Client(api_key=GEMINI_API_KEY)
config = types.GenerateContentConfig(system_instruction=CHARACTER_CARD)

async def generate_response(user_input: str) -> str:
    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=user_input,
            config=config
        )
        return response.text
    except Exception as e:
        print(f"Error generating response: {e}")
        return "抱歉，我無法處理您的請求。請稍後再試。"

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f'Logged in as {bot.user}')

@bot.tree.command(name='chat', description='與紗月聊天')
async def chat(interaction: discord.Interaction, message: str):
    await interaction.response.defer()
    reply = await generate_response(message)
    await interaction.followup.send(reply)

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return
    content = message.content.lower()
    if '紗月' in content or 'sayuki' in content:
        reply = await generate_response(message.content.strip())
        await message.channel.send(reply)
        return
    if message.reference and isinstance(message.reference, discord.MessageReference):
        prev = message.reference.cached_message or await message.channel.fetch_message(message.reference.message_id)
        # 只有當被回覆的訊息是紗月發送時才回覆
        if prev.author.id == bot.user.id:
            prompt = (
                f"前文：{prev.author.display_name}：{prev.content}\n" +
                f"使用者：{message.content.strip()}"
            )
            reply = await generate_response(prompt)
            await message.channel.send(reply)
            return
    if bot.user in message.mentions:
        content = message.content.replace(f"<@{bot.user.id}>", "").strip()
        reply = await generate_response(content)
        await message.channel.send(reply)
    await bot.process_commands(message)

class VoiceState:
    def __init__(self):
        self.voice_client: discord.VoiceClient | None = None
        self.recording = False
        self.audio_queue = deque(maxlen=5)
        self.whisper_model = None
        self.model_ready = asyncio.Event()
        self.loop = asyncio.get_event_loop()

    # 載入 Whisper 模型
    async def initialize_whisper(self):
        if not self.whisper_model:
            self.whisper_model = whisper.load_model("base")
            self.model_ready.set()

    # 開始錄音
    async def start_recording(self, voice_client: discord.VoiceClient):
        if not self.whisper_model:
            asyncio.create_task(self.initialize_whisper())
        self.voice_client = voice_client
        self.recording = True

        # 自訂錄音接收器
        class AudioReceiver(voice_recv.AudioSink):
            def __init__(self, vs: VoiceState):
                super().__init__()
                self.voice_state = vs
            def wants_opus(self) -> bool:
                return False
            def write(self, user, data: voice_recv.VoiceData):
                pcm_bytes = data.pcm
                if pcm_bytes:
                    self.voice_state.audio_queue.append(pcm_bytes)
                    if len(self.voice_state.audio_queue) >= 5:
                        self.voice_state.loop.call_soon_threadsafe(self.voice_state.loop.create_task,self.voice_state.process_audio())
            def cleanup(self):
                pass

        receiver = AudioReceiver(self)
        voice_client.listen(receiver, after=self.recording_finished)
        while self.recording and voice_client.is_listening():
            await asyncio.sleep(0.1)
        voice_client.stop_listening()
        self.recording = False

    def recording_finished(self, error=None):
        print("錄音結束", error if error else "")
    
    async def process_audio(self):
        if not self.audio_queue:
            return
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.wav')
        with wave.open(temp_file.name, 'wb') as wf:
            wf.setnchannels(2)
            wf.setsampwidth(2)
            wf.setframerate(48000)
            for chunk in self.audio_queue:
                wf.writeframes(chunk)
        try:
            result = self.whisper_model.transcribe(temp_file.name)
            text = result.get("text", "").lower()
            print(f"辨識結果：{text}")
            if '紗月' in text or 'sayuki' in text:
                reply = await generate_response(text)
                voice_temp = tempfile.NamedTemporaryFile(delete=False, suffix='.wav')
                success = await text_to_speech(reply, voice_temp.name)
                if success and self.voice_client:
                    def _delayed_cleanup(path):
                        try:
                            os.remove(path)
                        except Exception as exc:
                            print(f"延遲刪除失敗：{exc}")
                    self.voice_client.play(
                        discord.FFmpegPCMAudio(
                            voice_temp.name,
                            executable=FFMPEG_PATH,
                            before_options="-analyzeduration 0",
                            options="-vn -b:a 128k"
                        ),
                        after=lambda e: threading.Timer(1.0, _delayed_cleanup, args=(voice_temp.name,)).start()
                    )
        except Exception as e:
            print(f"語音辨識錯誤：{e}")
        finally:
            def _del(path):
                try:
                    os.remove(path)
                except Exception as e:
                    print(f"延遲刪除失敗：{e}")
            threading.Timer(5.0, _del, args=(temp_file.name,)).start()
            self.audio_queue.clear()

voice_states: dict[int, VoiceState] = {}

@bot.tree.command(name='join', description='加入語音頻道')
async def join(interaction: discord.Interaction):
    if not interaction.user.voice:
        return await interaction.response.send_message("你必須先加入語音頻道！")
    channel = interaction.user.voice.channel
    state = voice_states.get(interaction.guild.id)
    if state and state.voice_client and state.voice_client.channel.id == channel.id:
        return await interaction.response.send_message("我已經在這個語音頻道中了！")
    if state and state.voice_client:
        state.recording = False
        await state.voice_client.disconnect(force=True)
    state = VoiceState()
    voice_states[interaction.guild.id] = state
    state.voice_client = await channel.connect(cls=voice_recv.VoiceRecvClient)
    asyncio.create_task(state.start_recording(state.voice_client))
    await interaction.response.send_message(f"已加入 {channel.name} 頻道")

@bot.tree.command(name='leave', description='離開語音頻道')
async def leave(interaction: discord.Interaction):
    state = voice_states.get(interaction.guild.id)
    if state and state.voice_client:
        state.recording = False
        await state.voice_client.disconnect()
        voice_states.pop(interaction.guild.id, None)
        return await interaction.response.send_message("已離開語音頻道")
    await interaction.response.send_message("我目前不在任何語音頻道中")

async def text_to_speech(text: str, output_path: str) -> bool:
    base_url = "http://localhost:50021"
    speaker = 8
    params = {"text": text, "speaker": speaker}
    query_resp = requests.post(f"{base_url}/audio_query", params=params)
    if query_resp.status_code != 200:
        return False
    synth_resp = requests.post(
        f"{base_url}/synthesis",
        headers={"Content-Type": "application/json"},
        params={"speaker": speaker},
        data=json.dumps(query_resp.json())
    )
    if synth_resp.status_code != 200:
        return False
    with open(output_path, "wb") as f:
        f.write(synth_resp.content)
    return True

FFMPEG_PATH = None

def find_ffmpeg():
    global FFMPEG_PATH
    path = shutil.which('ffmpeg')
    if path:
        FFMPEG_PATH = path
        return True
    candidates = [
        r"D:\environment\ffmpeg\bin\ffmpeg.exe",
        os.path.join(os.getenv('LOCALAPPDATA',''), 'Programs', 'ffmpeg', 'bin', 'ffmpeg.exe')
    ]
    for p in candidates:
        if os.path.isfile(p):
            FFMPEG_PATH = p
            return True
    return False

if not find_ffmpeg():
    print("error: can't find FFmpeg. Please install FFmpeg and ensure it's in your PATH.")
else:
    ffdir = os.path.dirname(FFMPEG_PATH)
    os.environ["PATH"] = ffdir + os.pathsep + os.environ.get("PATH", "")

@bot.tree.command(name='speak', description='使用語音回應')
async def speak(interaction: discord.Interaction, text: str):
    state = voice_states.get(interaction.guild.id)
    if not state or not state.voice_client:
        return await interaction.response.send_message("我必須先加入語音頻道！")
    loop = state.loop
    if not FFMPEG_PATH:
        return await interaction.response.send_message("找不到 FFmpeg，無法使用語音功能！")
    await interaction.response.defer()
    try:
        reply = await generate_response("$speak{ " + text + " }$")
        jp_match = re.search(r'jp\{(.*?)\}', reply, re.DOTALL | re.IGNORECASE)
        zh_match = re.search(r'zh-tw\{(.*?)\}', reply, re.DOTALL | re.IGNORECASE)
        jp_reply = jp_match.group(1).strip() if jp_match else reply
        zh_reply = zh_match.group(1).strip() if zh_match else ""
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.wav')
        success = await text_to_speech(jp_reply, temp_file.name)
        if success and state.voice_client:
            def _delayed_cleanup(path):
                try:
                    os.remove(path)
                except Exception as exc:
                    print(f"延遲刪除失敗：{exc}")
            state.voice_client.play(
                discord.FFmpegPCMAudio(
                    temp_file.name,
                    executable=FFMPEG_PATH,
                    before_options="-analyzeduration 0",
                    options="-vn -b:a 128k"
                ),
                after=lambda e: threading.Timer(5.0, _delayed_cleanup, args=(temp_file.name,)).start()
            )
            await interaction.followup.send(f"正在說話: {zh_reply}")
        else:
            await interaction.followup.send("語音合成失敗，請稍後再試。")
    except Exception as e:
        await interaction.followup.send(f"發生錯誤：{e}")
        if os.path.exists(temp_file.name):
            os.remove(temp_file.name)

# 啟動 Bot
bot.run(TOKEN)
