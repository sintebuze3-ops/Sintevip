import os
import telebot
import logging
import time
from telebot import types
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from pymongo import MongoClient

# --- CONFIGURATION ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
MONGO_URI = os.getenv("MONGO_URI")

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

# --- DATABASE SETUP ---
try:
    client = MongoClient(MONGO_URI)
    db = client["sinte_vip_db"] # የዳታቤዙን ስም ወደ Sinte ቀይሬዋለሁ
    channels_col = db["channels"]
    users_col = db["users"]
    print("Connected to MongoDB for Sinte VIP!")
except Exception as e:
    print(f"Database Error: {e}")

# --- ADMIN KEYBOARD ---
def admin_panel_keyboard():
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("➕ ቻናል ለመጨመር", callback_data="adm_add_ch"),
        InlineKeyboardButton("➖ ቻናል ለመቀነስ", callback_data="adm_rem_ch"),
        InlineKeyboardButton("👤 ተጠቃሚ ለማስወገድ (በ ID/Forward)", callback_data="adm_manual_remove")
    )
    return markup

# --- COMMANDS ---
@bot.message_handler(commands=['start'])
def handle_start(message):
    if message.chat.id == ADMIN_ID:
        bot.send_message(ADMIN_ID, "<b>🛠 የ Sinte VIP አድሚን ፓነል</b>\n\nእንኳን ደህና መጡ! ከታች ያሉትን አማራጮች በመጠቀም ቻናሎችን እና አባላትን ያስተዳድሩ፦", 
                         reply_markup=admin_panel_keyboard())
    else:
        bot.send_message(message.chat.id, "ይህ ቦት ለ Sinte VIP አድሚን ብቻ የሚያገለግል ነው።")

# --- CALLBACK HANDLERS ---
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    if call.from_user.id != ADMIN_ID: return

    if call.data == "adm_add_ch":
        msg = bot.send_message(ADMIN_ID, "እባክዎ መጨመር ከሚፈልጉት ቻናል አንድ መልዕክት <b>Forward</b> ያድርጉልኝ፦")
        bot.register_next_step_handler(msg, process_add_channel)

    elif call.data == "adm_rem_ch":
        markup = InlineKeyboardMarkup()
        all_ch = list(channels_col.find())
        if not all_ch:
            bot.send_message(ADMIN_ID, "ምንም የተመዘገበ ቻናል የለም።")
            return
        for ch in all_ch:
            markup.add(InlineKeyboardButton(f"❌ {ch.get('name', 'Channel')}", callback_data=f"del_ch_{ch['id']}"))
        bot.edit_message_text("መሰረዝ የሚፈልጉትን ቻናል ይምረጡ፦", ADMIN_ID, call.message.message_id, reply_markup=markup)

    elif call.data.startswith("del_ch_"):
        ch_id = int(call.data.split("_")[2])
        channels_col.delete_one({"id": ch_id})
        bot.answer_callback_query(call.id, "ቻናሉ ተሰርዟል!")
        bot.send_message(ADMIN_ID, "✅ ቻናሉ ከ Sinte VIP ዝርዝር ውስጥ ተሰርዟል።", reply_markup=admin_panel_keyboard())

    elif call.data == "adm_manual_remove":
        msg = bot.send_message(ADMIN_ID, "ለማስወገድ የፈለጉትን ሰው <b>ID</b> ይላኩ ወይም ከሰውየው የተላከ መልዕክት <b>Forward</b> ያድርጉልኝ፦")
        bot.register_next_step_handler(msg, process_remove_user)

# --- PROCESSORS ---

def process_add_channel(message):
    if not message.forward_from_chat:
        bot.send_message(ADMIN_ID, "❌ ስህተት! እባክዎ መልዕክቱን ከቻናሉ ፎርዋርድ ያድርጉት።")
        return
    
    ch_id = message.forward_from_chat.id
    ch_name = message.forward_from_chat.title
    
    channels_col.update_one({"id": ch_id}, {"$set": {"name": ch_name, "id": ch_id}}, upsert=True)
    bot.send_message(ADMIN_ID, f"✅ ቻናል <b>{ch_name}</b> በስኬት ወደ Sinte VIP ተጨምሯል!", reply_markup=admin_panel_keyboard())

def process_remove_user(message):
    target_id = None

    if message.forward_from:
        target_id = message.forward_from.id
    elif message.text and message.text.isdigit():
        target_id = int(message.text)
    
    if not target_id:
        bot.send_message(ADMIN_ID, "❌ ስህተት! እባክዎ ትክክለኛ ID ይላኩ ወይም መልዕክት ፎርዋርድ ያድርጉ።")
        return

    users_col.update_one({"user_id": target_id}, {"$set": {"active": False, "expiry": 0}})
    
    channels = list(channels_col.find())
    count = 0

for ch in channels:
        try:
            bot.ban_chat_member(ch["id"], target_id)
            bot.unban_chat_member(ch["id"], target_id)
            count += 1
        except:
            continue
            
    bot.send_message(ADMIN_ID, f"✅ ተጠቃሚ <code>{target_id}</code> ከ {count} የ Sinte VIP ቻናሎች ተወግዷል።", reply_markup=admin_panel_keyboard())

# --- START BOT ---
if name == "main":
    print("Sinte VIP Bot is starting...")
    bot.infinity_polling()
