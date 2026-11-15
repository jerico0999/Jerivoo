# language: Python, file: telegram_bot.py, target: Telegram Bot, Python 3.8+
import os
import random
import time
import sqlite3
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from faker import Faker
import telebot
from telebot import types

# --- CONFIGURATION ---
TOKEN = os.getenv("BOT_TOKEN", "8963457884:AAFeJJl5gxzTAg2JVrVL9PQLTH96h0MDbY4")
ADMIN_USER_ID = int(os.getenv("ADMIN_ID", "8657082712"))

bot = telebot.TeleBot(TOKEN)

# --- DATABASE SETUP ---
def init_db():
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            referred_by INTEGER,
            referral_count INTEGER DEFAULT 0,
            total_generated INTEGER DEFAULT 0,
            balance INTEGER DEFAULT 2,
            is_blocked INTEGER DEFAULT 0
        )
    ''')
    try:
        cursor.execute('ALTER TABLE users ADD COLUMN is_blocked INTEGER DEFAULT 0')
    except:
        pass
    try:
        cursor.execute('ALTER TABLE users ADD COLUMN balance INTEGER DEFAULT 2')
    except:
        pass
    conn.commit()
    conn.close()

init_db()

def get_or_create_user(user_id, username, referrer_id=None):
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    
    if not user:
        ref_by = None
        if referrer_id and referrer_id != user_id:
            cursor.execute("SELECT * FROM users WHERE user_id = ?", (referrer_id,))
            if cursor.fetchone():
                ref_by = referrer_id
                cursor.execute("UPDATE users SET referral_count = referral_count + 1, balance = balance + 1 WHERE user_id = ?", (referrer_id,))
        
        cursor.execute("INSERT INTO users (user_id, username, referred_by, balance, is_blocked) VALUES (?, ?, ?, 2, 0)", (user_id, username or "User", ref_by))
        conn.commit()
    conn.close()

def is_user_blocked(user_id):
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT is_blocked FROM users WHERE user_id = ?", (user_id,))
    res = cursor.fetchone()
    conn.close()
    return res[0] == 1 if res else False

def get_user_balance(user_id):
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    res = cursor.fetchone()
    conn.close()
    return res[0] if res else 0

def deduct_coin(user_id):
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET balance = balance - 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def update_user_stats(user_id, count):
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET total_generated = total_generated + ? WHERE user_id = ?", (count, user_id))
    conn.commit()
    conn.close()

# --- GENERATOR LOGIC ---
API_KEYS = ["fa7ccaa915c34373bb88ac205878253e", "55946caf72414b73bf18337667ccf308"]

def clean_name(name):
    return "".join(c for c in name if c.isalpha())

def fetch_randommer_1(api_key):
    try:
        r = requests.get("https://randommer.io/api/Name", params={"nameType": "firstname", "quantity": 5000}, headers={"accept": "*/*", "X-Api-Key": api_key}, timeout=4)
        return [clean_name(name).capitalize() for name in r.json() if 3 <= len(clean_name(name)) <= 12]
    except:
        return []

def fetch_dummyjson_users():
    try:
        r = requests.get("https://dummyjson.com/users?limit=100", timeout=4)
        return [clean_name(u.get("firstName", "")).capitalize() for u in r.json().get("users", []) if 3 <= len(clean_name(u.get("firstName", ""))) <= 12]
    except:
        return []

def fetch_randomuser():
    try:
        r = requests.get("https://randomuser.me/api/", params={"results": 5000, "nat": "ph"}, timeout=4)
        return [clean_name(u.get("name", {}).get("first", "")).capitalize() for u in r.json().get("results", []) if 3 <= len(clean_name(u.get("name", {}).get("first", ""))) <= 12]
    except:
        return []

def load_names_pool():
    all_names = set()
    endpoints = [
        lambda: fetch_randommer_1(API_KEYS[0]),
        fetch_dummyjson_users,
        fetch_randomuser
    ]
    with ThreadPoolExecutor(max_workers=100) as executor:
        futures = [executor.submit(fn) for fn in endpoints]
        for future in as_completed(futures):
            try:
                names = future.result()
                for n in names:
                    all_names.add(n)
            except:
                pass
    return list(all_names)

def generate_accounts(amount):
    live_names = load_names_pool()
    if not live_names:
        fake = Faker("en_PH")
        live_names = [fake.first_name().strip().capitalize() for _ in range(500)]
    
    records = []
    generated = 0
    attempts = 0
    max_attempts = amount * 20

    while generated < amount and attempts < max_attempts:
        attempts += 1
        name = random.choice(live_names) if live_names else "User"
        number = random.randint(10, 199)
        cred = f"{name}{number}:{name}{number}"
        if cred not in records:
            records.append(cred)
            generated += 1
            
    return records

# --- TELEGRAM BOT HANDLERS ---
user_states = {}

@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name
    
    if is_user_blocked(user_id):
        bot.send_message(message.chat.id, "❌ Na-block ka ng admin at hindi mo maaaring gamitin ang bot na ito.")
        return
    
    args = message.text.split()
    referrer_id = None
    if len(args) > 1 and args[1].startswith("ref_"):
        try:
            referrer_id = int(args[1].replace("ref_", ""))
        except:
            pass
            
    get_or_create_user(user_id, username, referrer_id)
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("⚡ Generate Accounts"), types.KeyboardButton("💰 Balance"))
    markup.add(types.KeyboardButton("🏆 Leaderboard"), types.KeyboardButton("🔗 Referral Link"))
    markup.add(types.KeyboardButton("📊 My Stats"))
    
    bot.send_message(
        message.chat.id,
        f"Mabuhay, *{username}*! 👋\n\n"
        "Maligayang pagdating sa Jerico Upass Generator Bot.\n"
        "🎁 *Mayroon kang 2 Coins Welcome Bonus!* 🎉\n\n"
        "Pumili sa mga opsyon sa ibaba para magsimula:",
        parse_mode="Markdown",
        reply_markup=markup
    )

@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if message.from_user.id != ADMIN_USER_ID:
        bot.send_message(message.chat.id, "❌ Wala kang pahintulot na buksan ang Admin Panel.")
        return
    
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]
    cursor.execute("SELECT SUM(total_generated) FROM users")
    total_gen = cursor.fetchone()[0] or 0
    conn.close()

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("👥 Listahan ng Users (Block/Unblock)", callback_data="admin_users"))
    markup.add(types.InlineKeyboardButton("💰 Magdagdag ng Coins sa User", callback_data="admin_add_coins"))
    markup.add(types.InlineKeyboardButton("📢 Broadcast Message", callback_data="admin_broadcast"))

    bot.send_message(
        message.chat.id,
        f"🛠 *ADMIN CONTROL PANEL* 🛠\n\n"
        f"👥 Total Users: *{total_users}*\n"
        f"⚡ Total Generated Accounts: *{total_gen:,}*\n\n"
        "Piliin ang nais mong gawin:",
        parse_mode="Markdown",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_"))
def admin_callbacks(call):
    if call.from_user.id != ADMIN_USER_ID:
        return
    
    if call.data == "admin_users":
        conn = sqlite3.connect("bot_database.db")
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, username, balance, is_blocked FROM users LIMIT 20")
        users = cursor.fetchall()
        conn.close()
        
        text = "👥 *USER MANAGEMENT (Unang 20)*:\n\n"
        markup = types.InlineKeyboardMarkup()
        for u_id, uname, bal, blocked in users:
            status = "🟢 Active" if blocked == 0 else "🔴 Blocked"
            action_text = f"Block {uname or u_id}" if blocked == 0 else f"Unblock {uname or u_id}"
            cb_data = f"block_{u_id}" if blocked == 0 else f"unblock_{u_id}"
            markup.add(types.InlineKeyboardButton(action_text, callback_data=cb_data))
            text += f"• ID: `{u_id}` | {uname} | Coins: {bal} | {status}\n"
            
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)

    elif call.data.startswith("block_") or call.data.startswith("unblock_"):
        action, u_id = call.data.split("_")
        u_id = int(u_id)
        val = 1 if action == "block" else 0
        
        conn = sqlite3.connect("bot_database.db")
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET is_blocked = ? WHERE user_id = ?", (val, u_id))
        conn.commit()
        conn.close()
        
        bot.answer_callback_query(call.id, f"Tagumpay na na-update ang user {u_id}!")
        admin_panel(call.message)

    elif call.data == "admin_add_coins":
        user_states[ADMIN_USER_ID] = "waiting_coin_input"
        bot.send_message(call.message.chat.id, "I-send ang format na ito: `user_id amount`\nHalimbawa: `8657082712 10`", parse_mode="Markdown")

    elif call.data == "admin_broadcast":
        user_states[ADMIN_USER_ID] = "waiting_broadcast"
        bot.send_message(call.message.chat.id, "I-send ang mensaheng gusto mong i-broadcast sa lahat ng users:")

@bot.message_handler(func=lambda msg: msg.from_user.id == ADMIN_USER_ID and user_states.get(msg.from_user.id) == "waiting_coin_input")
def process_admin_coins(message):
    user_states.pop(ADMIN_USER_ID, None)
    try:
        parts = message.text.strip().split()
        target_id = int(parts[0])
        coins = int(parts[1])
        
        conn = sqlite3.connect("bot_database.db")
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (coins, target_id))
        conn.commit()
        conn.close()
        
        bot.send_message(message.chat.id, f"✅ Matagumpay na nadagdagan ng {coins} coins ang user na may ID: {target_id}")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ May mali sa format. Subukang muli. Error: {e}")

@bot.message_handler(func=lambda msg: msg.from_user.id == ADMIN_USER_ID and user_states.get(msg.from_user.id) == "waiting_broadcast")
def process_broadcast(message):
    user_states.pop(ADMIN_USER_ID, None)
    broadcast_text = message.text
    
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE is_blocked = 0")
    users = cursor.fetchall()
    conn.close()
    
    success = 0
    fail = 0
    for (u_id,) in users:
        try:
            bot.send_message(u_id, f"📢 *ANUNSYO MULA SA ADMIN:*\n\n{broadcast_text}", parse_mode="Markdown")
            success += 1
        except:
            fail += 1
            
    bot.send_message(message.chat.id, f"📢 Broadcast tapos na!\nTagumpay: {success}\nNabigo: {fail}")

# --- USER HANDLERS ---

@bot.message_handler(func=lambda msg: msg.text and ("Balance" in msg.text or msg.text == "/balance"))
def check_balance(message):
    user_id = message.from_user.id
    if is_user_blocked(user_id): return
    get_or_create_user(user_id, message.from_user.username or message.from_user.first_name)
    
    balance = get_user_balance(user_id)
    bot.send_message(
        message.chat.id,
        f"💰 *Iyong Balanse:* `{balance} Coins`\n\n"
        "💡 *Paano madagdagan ang coins?*\n"
        "Mag-invite ng mga kaibigan gamit ang iyong Referral Link para makakuha ng +1 Coin bawat invite!",
        parse_mode="Markdown"
    )

@bot.message_handler(func=lambda msg: msg.text and ("Generate Accounts" in msg.text or msg.text == "/generate"))
def ask_amount(message):
    user_id = message.from_user.id
    if is_user_blocked(user_id): return
    get_or_create_user(user_id, message.from_user.username or message.from_user.first_name)
    
    balance = get_user_balance(user_id)
    if balance < 1:
        bot.send_message(
            message.chat.id,
            "❌ *Wala ka nang sapat na coins para mag-generate!*\n\n"
            "Mag-invite ng mga kaibigan gamit ang iyong 🔗 Referral Link para makakuha ng libreng coins.",
            parse_mode="Markdown"
        )
        return

    user_states[user_id] = "waiting_amount"
    bot.send_message(
        message.chat.id,
        "📥 *Ilan ang gusto mong i-generate?*\n"
        "⚠️ *Limit:* 1,000 hanggang 5,000 accounts lamang bawat generate.\n"
        "💡 *Gastos:* 1 Coin bawat generate.\n\n"
        "Mag-type ng numerong gusto mo (Halimbawa: `1000` o `5000`):",
        parse_mode="Markdown"
    )

@bot.message_handler(func=lambda msg: msg.text and ("Referral Link" in msg.text or msg.text == "/referral"))
def referral_link(message):
    user_id = message.from_user.id
    if is_user_blocked(user_id): return
    get_or_create_user(user_id, message.from_user.username or message.from_user.first_name)
    
    bot_username = bot.get_me().username
    ref_link = f"https://t.me/{bot_username}?start=ref_{user_id}"
    
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT referral_count FROM users WHERE user_id = ?", (user_id,))
    res = cursor.fetchone()
    conn.close()
    ref_count = res[0] if res else 0
    
    bot.send_message(
        message.chat.id,
        f"🔗 *Iyong Referral Link:*\n`{ref_link}`\n\n"
        f"👥 Bilang ng na-refer mo: *{ref_count}*\n"
        "🎁 *Premyo:* Makakatanggap ka ng **1 Coin** sa bawat kaibigang magsisimula sa pamamagitan ng iyong link!",
        parse_mode="Markdown"
    )

@bot.message_handler(func=lambda msg: msg.text and ("Leaderboard" in msg.text or msg.text == "/leaderboard"))
def leaderboard(message):
    user_id = message.from_user.id
    if is_user_blocked(user_id): return
    
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT username, total_generated FROM users WHERE is_blocked = 0 ORDER BY total_generated DESC LIMIT 10")
    top_gen = cursor.fetchall()
    
    cursor.execute("SELECT username, referral_count FROM users WHERE is_blocked = 0 ORDER BY referral_count DESC LIMIT 10")
    top_ref = cursor.fetchall()
    conn.close()
    
    text = "🏆 *LEADERBOARD* 🏆\n\n*⚡ Top Generators:* \n"
    for idx, (uname, total) in enumerate(top_gen, 1):
        text += f"{idx}. {uname or 'User'} — {total:,} accounts\n"
        
    text += "\n*👥 Top Referrers:* \n"
    for idx, (uname, count) in enumerate(top_ref, 1):
        text += f"{idx}. {uname or 'User'} — {count} invites\n"
        
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

@bot.message_handler(func=lambda msg: msg.text and ("My Stats" in msg.text or msg.text == "/stats"))
def my_stats(message):
    user_id = message.from_user.id
    if is_user_blocked(user_id): return
    get_or_create_user(user_id, message.from_user.username or message.from_user.first_name)
    
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT referral_count, total_generated, balance FROM users WHERE user_id = ?", (user_id,))
    res = cursor.fetchone()
    conn.close()
    
    if res:
        ref_count, total_gen, balance = res
        bot.send_message(
            message.chat.id,
            f"📊 *Iyong Estadistika:*\n\n"
            f"💰 Balanse: *{balance} Coins*\n"
            f"⚡ Total Na-generate: *{total_gen:,}*\n"
            f"👥 Total Referrals: *{ref_count}*",
            parse_mode="Markdown"
        )
    else:
        bot.send_message(message.chat.id, "Wala pang rehistro. I-type ang /start.")

@bot.message_handler(func=lambda msg: user_states.get(msg.from_user.id) == "waiting_amount")
def process_generation(message):
    user_id = message.from_user.id
    user_states.pop(user_id, None)
    
    if is_user_blocked(user_id): return

    balance = get_user_balance(user_id)
    if balance < 1:
        bot.send_message(message.chat.id, "❌ Wala ka nang sapat na coins para mag-generate.")
        return
    
    try:
        amount = int(message.text.strip())
        if not (1000 <= amount <= 5000):
            bot.send_message(message.chat.id, "❌ Ang limitasyon sa pag-generate ay nasa pagitan ng *1,000 hanggang 5,000* accounts lamang.", parse_mode="Markdown")
            return
    except ValueError:
        bot.send_message(message.chat.id, "❌ Mangyaring maglagay ng valid na numero sa pagitan ng 1,000 at 5,000.")
        return

    deduct_coin(user_id)

    msg = bot.send_message(message.chat.id, f"⏳ Nag-generate ng {amount:,} accounts... Pakihintay sandali.")
    
    try:
        accounts = generate_accounts(amount)
        update_user_stats(user_id, len(accounts))
        
        filename = f"JERICO_UPASS_{amount}.txt"
        with open(filename, "w", encoding="utf-8") as f:
            f.write("\n".join(accounts) + "\n")
            
        with open(filename, "rb") as f:
            bot.send_document(
                message.chat.id,
                f,
                caption=f"✅ Matagumpay na na-generate ang {len(accounts):,} accounts!\n💰 Nabawasan ng 1 Coin ang iyong balanse."
            )
        os.remove(filename)
        bot.delete_message(message.chat.id, msg.message_id)
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Nagka-error habang nag-a-generate: {str(e)}")

if __name__ == "__main__":
    print("🤖 Telegram Bot with Admin Panel is running...")
    bot.infinity_polling()
