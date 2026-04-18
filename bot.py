import os
import telebot
import time
import threading
import logging
from flask import Flask
from pymongo import MongoClient
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

# =========================================================================
# 1. SETUP & RENDER KEEP-ALIVE
# =========================================================================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask('')
@app.route('/')
def home(): return "Admin Bot is Running!"

def run_web_server():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

# =========================================================================
# 2. CONFIGURATION (RENDER ENV VARIABLES)
# =========================================================================
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
MONGO_URI = os.getenv("MONGO_URI")

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")
client = MongoClient(MONGO_URI)
db = client["vip_management_db"]
users_col = db["users"]
channels_col = db["channels"]

# =========================================================================
# 3. ADMIN KEYBOARD
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
# 4. ADMIN LOGIC: ADD CHANNELS (BULK)
# =========================================================================
def process_add_channel(message):
    if message.text == "✅ ጨርሻለሁ":
        bot.send_message(ADMIN_ID, "✅ የቻናል ምዝገባ ተጠናቋል።", reply_markup=admin_panel_keyboard())
        return

    if not message.forward_from_chat:
        bot.send_message(ADMIN_ID, "❌ እባክዎ ከቻናሉ መልዕክት Forward ያድርጉ ወይም '✅ ጨርሻለሁ' የሚለውን ይጫኑ።")
        bot.register_next_step_handler(message, process_add_channel)
        return

    ch_id = message.forward_from_chat.id
    ch_name = message.forward_from_chat.title
    
    channels_col.update_one({"id": ch_id}, {"$set": {"name": ch_name, "id": ch_id}}, upsert=True)
    
    markup = ReplyKeyboardMarkup(resize_keyboard=True).add("✅ ጨርሻለሁ")
    bot.send_message(ADMIN_ID, f"✅ <b>{ch_name}</b> ተመዝግቧል!\nቀጥል ሌላም ካለ Forward አድርግ...", reply_markup=markup)
    bot.register_next_step_handler(message, process_add_channel)

# =========================================================================
# 5. ADMIN LOGIC: REMOVE USER (ID OR FORWARD)
# =========================================================================
def process_manual_remove(message):
    if message.text == "/cancel":
        bot.send_message(ADMIN_ID, "ሂደቱ ተሰርዟል!", reply_markup=admin_panel_keyboard())
        return

    target_id = None
    # ከ Forwarded ሜሴጅ ID መውሰድ
    if message.forward_from:
        target_id = message.forward_from.id
    # በቁጥር (ID) ከተላከ
    elif message.text and message.text.isdigit():
        target_id = int(message.text)
    
    if not target_id:
        bot.send_message(ADMIN_ID, "⚠️ እባክዎ የተጠቃሚ ID ይላኩ ወይም ሜሴጅ Forward ያድርጉ።\nለመሰረዝ /cancel ይበሉ።")
        bot.register_next_step_handler(message, process_manual_remove)
        return

    # ዳታቤዝ ላይ አክቲቭነቱን ማጥፋት
    users_col.update_one({"user_id": target_id}, {"$set": {"active": False, "expiry": 0}})
    
    # ከሁሉም የተመዘገቡ ቻናሎች ማስወጣት
    success = 0
    all_channels = list(channels_col.find())
    
    for ch in all_channels:
        try:
            bot.ban_chat_member(ch["id"], target_id)
            bot.unban_chat_member(ch["id"], target_id)
            success += 1
        except: continue
        
    bot.send_message(ADMIN_ID, f"✅ ተጠቃሚ <code>{target_id}</code> ከ {success} ቻናሎች ተወግዷል፤ አገልግሎቱም በዳታቤዝ ተዘግቷል።", reply_markup=admin_panel_keyboard())

# =========================================================================
# 6. HANDLERS
# =========================================================================
@bot.message_handler(commands=['start'])
def handle_start(message):
    if message.chat.id == ADMIN_ID:
        bot.send_message(ADMIN_ID, "<b>🛠 Master Admin Panel</b>", reply_markup=admin_panel_keyboard())
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
        bot.edit_message_text("ማስወገድ የሚፈልጉትን ቻናል ይምረጡ፦", ADMIN_ID, call.message.message_id, reply_markup=markup)

    elif call.data.startswith("delch_"):
        ch_id = int(call.data.split("_")[1])
        channels_col.delete_one({"id": ch_id})
        bot.answer_callback_query(call.id, "ቻናሉ ተሰርዟል!")
        bot.edit_message_text("✅ ቻናሉ በተሳካ ሁኔታ ተሰርዟል።", ADMIN_ID, call.message.message_id, reply_markup=admin_panel_keyboard())

# =========================================================================
# 7. RUN BOT
# =========================================================================
if __name__ == "__main__":
    threading.Thread(target=run_web_server, daemon=True).start()
    bot.polling(none_stop=True)
