import os
import discord
from discord import app_commands
from dotenv import load_dotenv

# 載入 .env 檔案中的環境變數
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# 設定機器人權限
intents = discord.Intents.default()
intents.message_content = True

# 建立 Client 實例
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

@client.event
async def on_ready():
    await tree.sync()
    print(f"✅ 已登入為 {client.user}，斜線指令已同步。")

@tree.command(name="ping", description="回應 Pong!")       
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message("🏓 Pong!")

client.run(TOKEN)