import os
import telebot
import threading
from flask import Flask
from telebot import types
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from pymongo import MongoClient

# --- RENDER PORT SETUP ---
app = Flask('')

@app.route('/')
def home():
    return "Sinte VIP Bot is Alive!"

def run_web():
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

# --- CONFIGURATION ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
MONGO_URI = os.getenv("MONGO_URI")

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

# --- DATABASE SETUP ---
try:
    client = MongoClient(MONGO_URI)
    db = client["sinte_vip_db"]
    channels_col = db["channels"]
    users_col = db["users"]
except Exception:
    pass

# --- ADMIN KEYBOARD ---
def admin_panel_keyboard():
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("➕ ቻናል ለመጨመር", callback_data="adm_add_ch"),
        InlineKeyboardButton("➖ ቻናል ለመቀነስ", callback_data="adm_rem_ch"),
        InlineKeyboardButton("👤 ተጠቃሚ ለማስወገድ", callback_data="adm_manual_remove")
    )
    return markup

# --- COMMANDS & HANDLERS ---
@bot.message_handler(commands=['start'])
def handle_start(message):
    if message.chat.id == ADMIN_ID:
        bot.send_message(ADMIN_ID, "<b>🛠 የ Sinte VIP አድሚን ፓነል</b>", reply_markup=admin_panel_keyboard())

@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    if call.from_user.id != ADMIN_ID: return
    if call.data == "adm_add_ch":
        msg = bot.send_message(ADMIN_ID, "እባክዎ ከቻናሉ መልዕክት <b>Forward</b> ያድርጉልኝ፦")
        bot.register_next_step_handler(msg, process_add_channel)
    elif call.data == "adm_rem_ch":
        markup = InlineKeyboardMarkup()
        for ch in list(channels_col.find()):
            markup.add(InlineKeyboardButton(f"❌ {ch.get('name', 'Channel')}", callback_data=f"del_ch_{ch['id']}"))
        bot.send_message(ADMIN_ID, "መሰረዝ የሚፈልጉትን ይምረጡ፦", reply_markup=markup)
    elif call.data.startswith("del_ch_"):
        ch_id = int(call.data.split("_")[2])
        channels_col.delete_one({"id": ch_id})
        bot.send_message(ADMIN_ID, "✅ ቻናሉ ተሰርዟል።")
    elif call.data == "adm_manual_remove":
        msg = bot.send_message(ADMIN_ID, "ID ይላኩ ወይም <b>Forward</b> ያድርጉ፦")
        bot.register_next_step_handler(msg, process_remove_user)

def process_add_channel(message):
    if message.forward_from_chat:
        ch_id, ch_name = message.forward_from_chat.id, message.forward_from_chat.title
        channels_col.update_one({"id": ch_id}, {"$set": {"name": ch_name, "id": ch_id}}, upsert=True)
        bot.send_message(ADMIN_ID, f"✅ {ch_name} ተጨምሯል!")

def process_remove_user(message):
    target_id = message.forward_from.id if message.forward_from else (int(message.text) if message.text.isdigit() else None)
    if target_id:
        users_col.update_one({"user_id": target_id}, {"$set": {"active": False}})
        bot.send_message(ADMIN_ID, f"✅ ተጠቃሚ {target_id} ታግዷል።")

# --- START BOT & WEB SERVER ---
if __name__ == "__main__":
    # Flaskን በሌላ Thread ማስነሳት ለ Render Port Binding
    threading.Thread(target=run_web).start()
    print("Sinte VIP Bot is starting...")
    bot.infinity_polling()
