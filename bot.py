import os
import telebot
import logging
from telebot import types
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from pymongo import MongoClient

# --- CONFIGURATION ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
MONGO_URI = os.getenv("MONGO_URI")

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

# --- DATABASE SETUP ---
client = MongoClient(MONGO_URI)
db = client["gett_vip_ultimate_db"]
channels_col = db["channels"]
users_col = db["users"]

# --- ADMIN KEYBOARD ---
def admin_panel_keyboard():
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("➕ ቻናል ለመጨመር", callback_data="adm_add_ch"),
        InlineKeyboardButton("➖ ቻናል ለመቀነስ", callback_data="adm_rem_ch"),
        InlineKeyboardButton("👤 ተጠቃሚ ለማስወገድ (በ ID)", callback_data="adm_manual_remove")
    )
    return markup

# --- COMMANDS ---
@bot.message_handler(commands=['start'])
def handle_start(message):
    if message.chat.id == ADMIN_ID:
        bot.send_message(ADMIN_ID, "<b>🛠 የGett VIP አድሚን ፓነል</b>\n\nከታች ያሉትን አማራጮች ይጠቀሙ፦", 
                         reply_markup=admin_panel_keyboard())
    else:
        bot.send_message(message.chat.id, "ይህ ቦት ለአድሚን ብቻ የሚያገለግል ነው።")

# --- CALLBACK HANDLERS ---
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    if call.from_user.id != ADMIN_ID: return

    if call.data == "adm_add_ch":
        msg = bot.send_message(ADMIN_ID, "እባክዎ መጨመር ከሚፈልጉት ቻናል አንድ መልዕክት <b>Forward</b> ያድርጉልኝ፦")
        bot.register_next_step_handler(msg, process_add_channel)

    elif call.data == "adm_rem_ch":
        markup = InlineKeyboardMarkup()
        for ch in list(channels_col.find()):
            markup.add(InlineKeyboardButton(f"❌ {ch['name']}", callback_data=f"del_ch_{ch['id']}"))
        bot.edit_message_text("መሰረዝ የሚፈልጉትን ቻናል ይምረጡ፦", ADMIN_ID, call.message.message_id, reply_markup=markup)

    elif call.data.startswith("del_ch_"):
        ch_id = int(call.data.split("_")[2])
        channels_col.delete_one({"id": ch_id})
        bot.answer_callback_query(call.id, "ቻናሉ ተሰርዟል!")
        bot.send_message(ADMIN_ID, "✅ ቻናሉ በስኬት ተሰርዟል።", reply_markup=admin_panel_keyboard())

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
    bot.send_message(ADMIN_ID, f"✅ ቻናል <b>{ch_name}</b> በስኬት ተጨምሯል!", reply_markup=admin_panel_keyboard())

def process_remove_user(message):
    target_id = None

    # በፎርዋርድ ሜሴጅ ከሆነ
    if message.forward_from:
        target_id = message.forward_from.id
    # በጽሁፍ (ID) ከሆነ
    elif message.text and message.text.isdigit():
        target_id = int(message.text)
    
    if not target_id:
        bot.send_message(ADMIN_ID, "❌ ስህተት! እባክዎ ትክክለኛ ID ይላኩ ወይም መልዕክት ፎርዋርድ ያድርጉ።")
        return

    # ከአገልግሎት ማገድ (Database)
    users_col.update_one({"user_id": target_id}, {"$set": {"active": False, "expiry": 0}})
    
    # ከሁሉም ቻናሎች ማስወገድ
    channels = list(channels_col.find())
    count = 0
    for ch in channels:
        try:
            bot.ban_chat_member(ch["id"], target_id)
            bot.unban_chat_member(ch["id"], target_id)
            count += 1
        except:
            continue
            
    bot.send_message(ADMIN_ID, f"✅ ተጠቃሚ <code>{target_id}</code> ከ {count} ቻናሎች ተወግዷል።", reply_markup=admin_panel_keyboard())

if name == "main":
    bot.polling(none_stop=True)        for p in raw_plans:
            t, pr = p.strip().split(':')
            plans_dict[t] = pr
        
        channels_col.update_one({"channel_id": ch_id}, {"$set": {"name": ch_name, "plans": plans_dict, "admin_id": ADMIN_ID}}, upsert=True)
        bot_username = bot.get_me().username
        bot.send_message(ADMIN_ID, f"✅ Setup Successful!\n\nInvite Link for users:\n`https://t.me/{bot_username}?start={ch_id}`", parse_mode="Markdown")
    except:
        bot.send_message(ADMIN_ID, "❌ Invalid format. Please use `Min:Price, Min:Price`. Use /add to retry.")

# --- USER: PAYMENT FLOW ---

@bot.callback_query_handler(func=lambda call: call.data.startswith('select_'))
def user_pays(call):
    _, ch_id, mins = call.data.split('_')
    ch_data = channels_col.find_one({"channel_id": int(ch_id)})
    price = ch_data['plans'][mins]
    
    qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data=upi://pay?pa={UPI_ID}%26am={price}%26cu=INR"
    
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("✅ I Have Paid", callback_data=f"paid_{ch_id}_{mins}"))
    markup.add(InlineKeyboardButton("📞 Contact Admin", url=f"https://t.me/{CONTACT_USERNAME}"))
    
    bot.send_photo(call.message.chat.id, qr_url, 
                   caption=f"Plan: {mins} Minutes\nPrice: ₹{price}\nUPI ID: `{UPI_ID}`\n\nPlease complete the payment and click 'I Have Paid'.", 
                   reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith('paid_'))
def admin_notify(call):
    _, ch_id, mins = call.data.split('_')
    user = call.from_user
    ch_data = channels_col.find_one({"channel_id": int(ch_id)})
    price = ch_data['plans'][mins]
    
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("✅ Approve", callback_data=f"app_{user.id}_{ch_id}_{mins}"))
    markup.add(InlineKeyboardButton("❌ Reject", callback_data=f"rej_{user.id}"))
    
    bot.send_message(ADMIN_ID, f"🔔 *Payment Verification Required!*\n\nUser: {user.first_name}\nChannel: {ch_data['name']}\nPlan: {mins} Mins\nPrice: ₹{price}", 
                     reply_markup=markup, parse_mode="Markdown")
    
    u_markup = InlineKeyboardMarkup().add(InlineKeyboardButton("📞 Contact Admin", url=f"https://t.me/{CONTACT_USERNAME}"))
    bot.send_message(call.message.chat.id, "✅ Your payment request has been sent. Please wait for Admin approval.", reply_markup=u_markup)

# --- APPROVAL & EXPIRY ---

@bot.callback_query_handler(func=lambda call: call.data.startswith('app_'))
def approve_now(call):
    _, u_id, ch_id, mins = call.data.split('_')
    u_id, ch_id, mins = int(u_id), int(ch_id), int(mins)
    
    try:
        expiry_datetime = datetime.now() + timedelta(minutes=mins)
        expiry_ts = int(expiry_datetime.timestamp())

        # Link expires when sub ends
        link = bot.create_chat_invite_link(ch_id, member_limit=1, expire_date=expiry_ts)
        
        users_col.update_one({"user_id": u_id, "channel_id": ch_id}, {"$set": {"expiry": expiry_datetime.timestamp()}}, upsert=True)
        
        bot.send_message(u_id, f"🥳 *Payment Approved!*\n\nSubscription: {mins} Minutes\n\nJoin Link: {link.invite_link}\n\n⚠️ Note: This link and your access will expire in {mins} minutes.", parse_mode="Markdown")
        bot.edit_message_text(f"✅ Approved user {u_id} for {mins} mins.", call.message.chat.id, call.message.message_id)
        
    except Exception as e:
        bot.send_message(ADMIN_ID, f"❌ Error: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith('manage_'))
def manage_ch(call):
    ch_id = int(call.data.split('_')[1])
    ch_data = channels_col.find_one({"channel_id": ch_id})
    bot_username = bot.get_me().username
    link = f"https://t.me/{bot_username}?start={ch_id}"
    
    bot.edit_message_text(f"Settings for: *{ch_data['name']}*\n\nYour Link: `{link}`\n\nTo edit prices, use /add and forward a message from this channel again.", 
                          call.message.chat.id, call.message.message_id, parse_mode="Markdown")

# Automate Kicking
def kick_expired_users():
    now = datetime.now().timestamp()
    expired_users = users_col.find({"expiry": {"$lte": now}})
    bot_username = bot.get_me().username

    for user in expired_users:
        try:
            bot.ban_chat_member(user['channel_id'], user['user_id'])
            bot.unban_chat_member(user['channel_id'], user['user_id'])
            
            rejoin_url = f"https://t.me/{bot_username}?start={user['channel_id']}"
            markup = InlineKeyboardMarkup().add(InlineKeyboardButton("🔄 Re-join / Renew", url=rejoin_url))
            
            bot.send_message(user['user_id'], "⚠️ Your subscription has expired.\n\nTo join again or renew, please click the button below:", reply_markup=markup)
            users_col.delete_one({"_id": user['_id']})
        except: pass

# --- STARTUP ---
if __name__ == '__main__':
    keep_alive()
    scheduler = BackgroundScheduler()
    scheduler.add_job(kick_expired_users, 'interval', minutes=1)
    scheduler.start()
    bot.remove_webhook()
    print("Bot is running...")
    bot.infinity_polling(timeout=20, long_polling_timeout=10)
