import os
import telebot
import time
import threading
import logging
from flask import Flask
from pymongo import MongoClient
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

# =========================================================================
# 1. RENDER SERVER SETUP (KEEP-ALIVE)
# =========================================================================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask('')

@app.route('/')
def home():
    return "Sinte VIP Admin Bot is Running!"

def run_web_server():
    # Render የሚሰጠውን PORT ይጠቀማል
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

# =========================================================================
# 2. CONFIGURATION (READING FROM RENDER ENVIRONMENT)
# =========================================================================
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID_VAL = os.getenv("ADMIN_ID")
MONGO_URI = os.getenv("MONGO_URI")

# ADMIN_ID ቁጥር መሆኑን ማረጋገጥ
try:
    ADMIN_ID = int(ADMIN_ID_VAL) if ADMIN_ID_VAL else None
except (ValueError, TypeError):
    ADMIN_ID = None
    logger.error("ADMIN_ID must be a valid number in Render environment!")

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

# MongoDB ግንኙነት
try:
    client = MongoClient(MONGO_URI)
    db = client["sinte_vip_db"]
    users_col = db["users"]
    channels_col = db["channels"]
    logger.info("Connected to MongoDB successfully!")
except Exception as e:
    logger.error(f"MongoDB connection failed: {e}")

# =========================================================================
# 3. KEYBOARDS
# =========================================================================
def admin_panel_keyboard():
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("➕ ቻናል በብዛት ጨምር", callback_data="adm_add_ch"),
        InlineKeyboardButton("👤 ተጠቃሚ ማባረር (ID/Forward)", callback_data="adm_manual_remove"),
        InlineKeyboardButton("➖ ቻናል ቀንስ (ከዝርዝር)", callback_data="adm_rem_ch")
    )
    return markup

# =========================================================================
# 4. ADMIN FUNCTIONS: BULK ADD & MANUAL REMOVE
# =========================================================================
def process_add_channel(message):
    if message.text == "✅ ጨርሻለሁ":
        bot.send_message(ADMIN_ID, "✅ የቻናል ምዝገባ ተጠናቋል።", reply_markup=admin_panel_keyboard())
        return

    if not message.forward_from_chat:
        bot.send_message(ADMIN_ID, "❌ እባክዎ ከቻናሉ መልዕክት <b>Forward</b> ያድርጉ ወይም '✅ ጨርሻለሁ' የሚለውን ይጫኑ።")
        bot.register_next_step_handler(message, process_add_channel)
        return

    ch_id = message.forward_from_chat.id
    ch_name = message.forward_from_chat.title
    
    channels_col.update_one({"id": ch_id}, {"$set": {"name": ch_name, "id": ch_id}}, upsert=True)
    
    markup = ReplyKeyboardMarkup(resize_keyboard=True).add("✅ ጨርሻለሁ")
    bot.send_message(ADMIN_ID, f"✅ <b>{ch_name}</b> ተመዝግቧል!\nቀጥል ሌላም ካለ Forward አድርግ...", reply_markup=markup)
    bot.register_next_step_handler(message, process_add_channel)

def process_manual_remove(message):
    if message.text == "/cancel":
        bot.send_message(ADMIN_ID, "ሂደቱ ተሰርዟል!", reply_markup=admin_panel_keyboard())
        return

    target_id = None
    if message.forward_from:
        target_id = message.forward_from.id
    elif message.text and message.text.isdigit():
        target_id = int(message.text)
    
    if not target_id:
        bot.send_message(ADMIN_ID, "⚠️ እባክዎ የተጠቃሚ ID ይላኩ ወይም ሜሴጅ Forward ያድርጉ።\nለመሰረዝ /cancel ይበሉ።")
        bot.register_next_step_handler(message, process_manual_remove)
        return

    users_col.update_one({"user_id": target_id}, {"$set": {"active": False, "expiry": 0}})
    
    success = 0
    all_channels = list(channels_col.find())
    for ch in all_channels:
        try:
            bot.ban_chat_member(ch["id"], target_id)
            bot.unban_chat_member(ch["id"], target_id)
            success += 1
        except: continue
        
    bot.send_message(ADMIN_ID, f"✅ ተጠቃሚ <code>{target_id}</code> ከ {success} ቻናሎች ተወግዷል።", reply_markup=admin_panel_keyboard())

# =========================================================================
# 5. MESSAGE & CALLBACK HANDLERS
# =========================================================================
@bot.message_handler(commands=['start'])
def handle_start(message):
    if message.chat.id == ADMIN_ID:
        bot.send_message(ADMIN_ID, "<b>🛠 Sinte VIP Admin Panel</b>", reply_markup=admin_panel_keyboard())
    else:
        bot.send_message(message.chat.id, "ሰላም! ይህ የVIP አስተዳዳሪ ቦት ነው።")

@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    if call.data == "adm_add_ch":
        msg = bot.send_message(ADMIN_ID, "ለመጨመር የሚፈልጓቸውን ቻናሎች አንድ በአንድ <b>Forward</b> ያድርጉልኝ፦")
        bot.register_next_step_handler(msg, process_add_channel)
    
    elif call.data == "adm_manual_remove":
        msg = bot.send_message(ADMIN_ID, "ማስወገድ የሚፈልጉትን ተጠቃሚ <b>ID ይላኩ</b> ወይም ሜሴጁን <b>Forward</b> ያድርጉ፦")
        bot.register_next_step_handler(msg, process_manual_remove)

    elif call.data == "adm_rem_ch":
        markup = InlineKeyboardMarkup()
        for ch in list(channels_col.find()):
            markup.add(InlineKeyboardButton(f"❌ {ch['name']}", callback_data=f"delch_{ch['id']}"))
        if markup.keyboard:
            bot.edit_message_text("ማስወገድ የሚፈልጉትን ቻናል ይጫኑ፦", ADMIN_ID, call.message.message_id, reply_markup=markup)
        else:
            bot.answer_callback_query(call.id, "ምንም የተመዘገበ ቻናል የለም!")

    elif call.data.startswith("delch_"):
        ch_id = int(call.data.split("_")[1])
        channels_col.delete_one({"id": ch_id})
        bot.edit_message_text("✅ ቻናሉ ተሰርዟል።", ADMIN_ID, call.message.message_id, reply_markup=admin_panel_keyboard())

# =========================================================================
# 6. EXECUTION
# =========================================================================
if __name__ == "__main__":
    # Flask thread ለ Render Keep-alive
    threading.Thread(target=run_web_server, daemon=True).start()
    
    # ቦት ፖሊንግ
    while True:
        try:
            bot.polling(none_stop=True, interval=0, timeout=20)
        except Exception as e:
            logger.error(f"Polling error: {e}")
            time.sleep(15)
