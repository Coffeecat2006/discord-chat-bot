@echo off
echo 正在檢查安裝環境...

REM 檢查 Python 是否已安裝
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo 請先安裝 Python 3.8 或以上版本
    exit /b 1
)

REM 檢查 pip 是否已安裝
where pip >nul 2>nul
if %errorlevel% neq 0 (
    echo 請先安裝 pip
    exit /b 1
)

echo 正在安裝 Python 套件...
pip install discord.py python-dotenv google-cloud-aiplatform openai-whisper requests

REM 建立設定檔案目錄
if not exist "config" mkdir config

REM 建立 .env 檔案範本
echo BOT_TOKEN=your_discord_bot_token> config\.env
echo GEMINI_API_KEY=your_gemini_api_key>> config\.env
echo CHARACTER_CARD=your_character_card>> config\.env

echo 請確認已安裝以下軟體：
echo 1. FFmpeg (https://ffmpeg.org/download.html)
echo 2. VOICEVOX Engine (https://voicevox.hiroshiba.jp/)

echo 安裝完成！請設定 config\.env 檔案中的環境變數。
pause
