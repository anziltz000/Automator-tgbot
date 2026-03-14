import os
import logging
import json
import requests
import asyncio
from threading import Thread
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, CallbackQueryHandler, filters

# --- CONFIGURATION ---
TOKEN = os.getenv("TELEGRAM_TOKEN")
N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL", "YOUR_N8N_WEBHOOK_URL_HERE")

PROCESSOR_POST_URL = "https://processor-n8n-automator.onrender.com/process"
PROCESSOR_WAKE_URL = "https://processor-n8n-automator.onrender.com"
N8N_WAKE_URL = "https://formidable-genovera-anziiiii-0be0ed80.koyeb.app"

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

[$20] **LeonBET** (YT Only)
   (1K) Any English Content. 15 sec.
   *25 submit per/social*

[$20] **Bitz.io** (YT & Insta)
   Any English Content. 20 sec.
   *100 submit per/social*
   ⚠️ *Must tag @bitzcasino on Insta!*

[$80] **AceBet** (YT Only)
   (1K) LIVESTREAM Tier 1 streamer clips only! (Kai Cenat, Speed, Jynxzi, FaZe guys etc).
   *25 submit per/social*

--------------------------------------------------
👇 **SELECT CAMPAIGN BELOW** 👇
"""

# --- MENUS (The Buttons) ---
def get_campaign_keyboard():
    keyboard = [
        [InlineKeyboardButton("🦁 LeonBET ($20)", callback_data="cam_leonbet"),
         InlineKeyboardButton("🎰 Bitz.io ($20)", callback_data="cam_bitz")],
        [InlineKeyboardButton("🔥 AceBet ($80)", callback_data="cam_acebet")],
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

def get_confirmation_keyboard():
    keyboard = [
        [InlineKeyboardButton("✅ I made sure they are running!", callback_data="confirm_awake")]
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
        
        await query.edit_message_text("🔍 Checking if factory is awake...")
        await check_factory_status(update, context)
        
    elif data == "confirm_awake":
        await query.edit_message_text("🚀 Sending task to factory now...")
        await send_to_processor(update, context)

# --- THE HEALTH CHECKER ---
async def check_factory_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    status_msg = update.callback_query.message
    is_awake = False

    try:
        response = await asyncio.to_thread(requests.get, PROCESSOR_WAKE_URL, timeout=3)
        if response.status_code == 200:
            is_awake = True
    except:
        pass 

    if is_awake:
        await status_msg.edit_text("✅ Factory is fully awake! Processing video...")
        await send_to_processor(update, context)
    else:
        text = (
            "⚠️ **The Factory is currently ASLEEP!**\n\n"
            "Please click both links below to wake them up. Wait until the web pages load on your phone:\n\n"
            f"1️⃣ [Wake up Processor]({PROCESSOR_WAKE_URL})\n"
            f"2️⃣ [Wake up n8n]({N8N_WAKE_URL})\n\n"
            "*(Once you are sure they are awake, click the button below!)*"
        )
        await status_msg.edit_text(text, parse_mode='Markdown', reply_markup=get_confirmation_keyboard(), disable_web_page_preview=True)

# --- THE DISPATCHER: Send JSON to the Video Processor ---
async def send_to_processor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    video_url = context.user_data.get('url')
    campaign = context.user_data.get('campaign')
    position = context.user_data.get('position')
    target = context.user_data.get('target')
    
    status_msg = update.callback_query.message

    payload = {
        'url': video_url,
        'campaign': campaign,
        'position': position,
        'target': target,
        'webhook_reply_url': N8N_WEBHOOK_URL 
    }

    try:
        response = await asyncio.to_thread(
            requests.post, 
            PROCESSOR_POST_URL, 
            json=payload, 
            timeout=60
        )
        
        if response.status_code in [502, 503, 504]:
            await status_msg.edit_text("❌ Factory wasn't fully awake yet! Please click the links again, wait 30 seconds, and try submitting a new link.")
            return
            
        response.raise_for_status() 
        
        reply_data = response.json()
        queue_pos = reply_data.get('queue_position', 1)
        
        if queue_pos == 1:
            await status_msg.edit_text(f"✅ Success! Factory is processing your video right now.\nCampaign: {campaign.upper()}")
        else:
            await status_msg.edit_text(f"✅ Task queued! You are #{queue_pos} in line.\nCampaign: {campaign.upper()}")

    except Exception as e:
        await status_msg.edit_text(f"❌ Failed to reach Factory. Error: {str(e)}")

if __name__ == '__main__':
    if not TOKEN:
        print("❌ Error: TELEGRAM_TOKEN not found.", flush=True)
        exit(1)

    server_thread = Thread(target=run_flask)
    server_thread.daemon = True
    server_thread.start()

    print("🤖 Telegram Bot Started and polling...", flush=True)
    application = ApplicationBuilder().token(TOKEN).build()
    
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    application.add_handler(CallbackQueryHandler(handle_buttons))
    
    application.run_polling()
