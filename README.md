# discord-chat-bot

使用 Python 打造的 Discord 聊天機器人，具備語音錄製與文字生成等功能。

## 功能特色

- 自動回應用戶訊息
- 基本指令系統
- 自訂回覆功能

## 安裝需求

- Python 3.8 或以上版本
- pip
- 安裝 `FFmpeg`、`VOICEVOX Engine` 以及系統套件 `libopus`

## 安裝步驟

1. 克隆專案
```bash
git clone https://github.com/your-username/discord-chat-bot.git
cd discord-chat-bot
```

2. 安裝相依套件
```bash
pip install -r setting/requirements.txt
```

3. 設定環境變數
- 在專案根目錄建立 `.env` 並填入 `BOT_TOKEN`、`GEMINI_API_KEY` 及 `CHARACTER_CARD`

4. 啟動機器人
```bash
python bot.py
```

## 使用方法

在 Discord 中@機器人

## 貢獻方式

歡迎提交 Pull Request 或建立 Issue。

## 授權條款

MIT License
