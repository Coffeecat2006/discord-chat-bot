import os
from dotenv import load_dotenv
import discord
from discord.ext import commands
from discord import app_commands
from google import genai
from google.genai import types

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
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=user_input,
        config=config
    )
    return response.text

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f'Logged in as {bot.user}')

@bot.tree.command(name='chat', description='與機器人聊天')
@app_commands.describe(message='與夜璃(Yeli)聊天')
async def chat(interaction: discord.Interaction, message: str):
    await interaction.response.defer()
    reply = await generate_response(message)
    await interaction.followup.send(reply)

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return
    if message.reference and isinstance(message.reference, discord.MessageReference):
        ref = message.reference
        if ref.cached_message:
            prev = ref.cached_message
        else:
            prev = await message.channel.fetch_message(ref.message_id)
        prompt = (
            f"前文：{prev.author.display_name}：{prev.content}\n"
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


bot.run(TOKEN)
