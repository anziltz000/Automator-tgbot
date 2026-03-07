import os
import time
import logging
import json
import requests
from threading import Thread
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, CallbackQueryHandler, filters

# --- CONFIGURATION ---
TOKEN = os.getenv("TELEGRAM_TOKEN")
# The URL of your new Render Video Processor
PROCESSOR_URL = os.getenv("PROCESSOR_URL", "https://processor-n8n-automator.onrender.com/process")
# Where the processor should send the final video
N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL", "YOUR_N8N_WEBHOOK_URL_HERE")

# Setup Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# --- KEEP-AWAKE FLASK SERVER ---
app = Flask(__name__)

@app.route('/')
def home():
    return "🤖 Bot is awake and running!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# --- CAMPAIGN DETAILS MESSAGE ---
CAMPAIGN_INFO_TEXT = """
💰 **ACTIVE CAMPAIGNS LIST** 💰

[$20] **Rajbet** (YT & Insta)
   South Asian content (Cricket, PUBG, Bollywood). 11 sec.
   *100 submit/per social*

[$20] **LeonBET** (YT Only)
   (1K) Any English Content. 15 sec.
   *25 submit per/social*

[$20] **TucanBit.io** (YT Only)
   (1K) Any English Content. 12 sec.
   *30 submit per/social*

[$20] **Bitz.io** (YT & Insta)
   Any English Content. 20 sec.
   *100 submit per/social*
   ⚠️ *Must tag @bitzcasino on Insta!*

[$50] **Betstrike** (YT Only)
   Gaming/Sports PIC LOGO (Smart Color Auto-Switch)

--------------------------------------------------
👇 **SELECT CAMPAIGN BELOW** 👇
"""

# --- MENUS (The Buttons) ---
def get_campaign_keyboard():
    keyboard = [
        [InlineKeyboardButton("🏏 Rajbet ($20)", callback_data="cam_rajbet"),
         InlineKeyboardButton("🦁 LeonBET ($20)", callback_data="cam_leonbet")],
        [InlineKeyboardButton("🐦 TucanBit ($20)", callback_data="cam_tucanbit"),
         InlineKeyboardButton("🎰 Bitz.io ($20)", callback_data="cam_bitz")],
        [InlineKeyboardButton("⚡ Betstrike (Smart Logo) ($50)", callback_data="cam_betstrike")],
    ]
    return InlineKeyboardMarkup(keyboard)

def get_position_keyboard():
    keyboard = [
        [InlineKeyboardButton("⬆️ Top Center", callback_data="pos_top"),
         InlineKeyboardButton("⬇️ Bottom Center", callback_data="pos_bottom")],
        [InlineKeyboardButton("↖️ Custom 1", callback_data="pos_c1"),
         InlineKeyboardButton("↘️ Custom 2", callback_data="pos_c2")],
    ]
    return InlineKeyboardMarkup(keyboard)

def get_upload_keyboard():
    keyboard = [
        [InlineKeyboardButton("📸 Insta Only", callback_data="upload_insta"),
         InlineKeyboardButton("📺 YT Only", callback_data="upload_yt")],
        [InlineKeyboardButton("🚀 Upload BOTH", callback_data="upload_both")],
    ]
    return InlineKeyboardMarkup(keyboard)

# --- STEP 1: User Sends Link ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    
    if "instagram.com" not in url and "youtube.com" not in url and "tiktok.com" not in url:
        await update.message.reply_text("❌ Invalid link. Send a valid Reel/Short link.")
        return

    context.user_data['url'] = url
    await update.message.reply_text(CAMPAIGN_INFO_TEXT, parse_mode='Markdown', reply_markup=get_campaign_keyboard())

# --- STEP 2, 3, 4: Handle Button Clicks ---
async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("cam_"):
        campaign = data.split("_")[1]
        context.user_data['campaign'] = campaign
        await query.edit_message_text(f"✅ Campaign Selected: {campaign.upper()}\n\nStep 2: Select Logo Position:", reply_markup=get_position_keyboard())

    elif data.startswith("pos_"):
        position = data.split("_")[1]
        context.user_data['position'] = position
        await query.edit_message_text(f"✅ Position: {position}\n\nStep 3: Where to upload?", reply_markup=get_upload_keyboard())

    elif data.startswith("upload_"):
        target = data.split("_")[1]
        context.user_data['target'] = target
        
        await query.edit_message_text(f"⏳ Sending instructions to Video Factory...")
        await send_to_processor(update, context)

# --- THE DISPATCHER: Send JSON to the Video Processor ---
async def send_to_processor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    video_url = context.user_data.get('url')
    campaign = context.user_data.get('campaign')
    position = context.user_data.get('position')
    
    status_msg = update.callback_query.message

    try:
        print(f"📡 Sending task to Processor: {video_url}", flush=True)
        
        # Package the instructions into a lightweight JSON payload
        payload = {
            'url': video_url,
            'campaign': campaign,
            'position': position,
            'webhook_reply_url': N8N_WEBHOOK_URL # Tells the processor where to send the final file
        }
        
        # Fire it over to the Render Video Processor
        response = requests.post(PROCESSOR_URL, json=payload)
        response.raise_for_status()
        
        # Check the queue position from the processor's response
        reply_data = response.json()
        queue_pos = reply_data.get('queue_position', 1)
        
        if queue_pos == 1:
            await status_msg.edit_text(f"✅ Success! Factory is processing your video right now.\nCampaign: {campaign.upper()}\n\nIt will arrive in your n8n workflow shortly.")
        else:
            await status_msg.edit_text(f"✅ Task queued! You are #{queue_pos} in line.\nCampaign: {campaign.upper()}\n\nThe processor will handle it automatically.")
            
        print("✅ Successfully dispatched to Video Processor!", flush=True)

    except Exception as e:
        print(f"❌ Error pinging Processor: {str(e)}", flush=True)
        await status_msg.edit_text(f"❌ Failed to reach Video Factory.\nError: {str(e)}")

if __name__ == '__main__':
    if not TOKEN:
        print("❌ Error: TELEGRAM_TOKEN not found.", flush=True)
        exit(1)

    # 1. Start the Flask Keep-Awake Server
    server_thread = Thread(target=run_flask)
    server_thread.daemon = True
    server_thread.start()

    # 2. Start the Telegram Bot
    print("🤖 Telegram Bot Started and polling...", flush=True)
    application = ApplicationBuilder().token(TOKEN).build()
    
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    application.add_handler(CallbackQueryHandler(handle_buttons))
    
    application.run_polling()
