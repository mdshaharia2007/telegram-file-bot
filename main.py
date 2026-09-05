import asyncio
import os
import threading
from flask import Flask

# Render / Python 3.11+ Event Loop Fix
try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

import sqlite3
from pyrogram import Client, filters, idle
from pyrogram.errors import (
    FloodWait,
    MessageIdInvalid,
    RPCError,
    PeerIdInvalid,
    UserNotParticipant
)
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# --- Render Port Binding Fix (Web Service Free Tier) ---
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "Bot is running successfully!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host="0.0.0.0", port=port)

# ব্যাকগ্রাউন্ডে ওয়েব সার্ভার চালু রাখা যাতে Render পোর্ট এরর না দেয়
threading.Thread(target=run_flask, daemon=True).start()
# -----------------------------------------------------

BOT_TOKEN = "8773057745:AAF9r75CmN6UeDlO5n5f0XUlIEzg-OgmwKM"
API_ID = 15162741
API_HASH = "549c8dc229374dc9f9bf2f3a6bc25daa"

STORAGE_CHANNEL_ID = -1003870581744
FORCE_SUB_CHANNEL = "BlackZone2007"
ADMIN_USERNAME = "backhusts"  # এডমিন ইউজারনেম (@ ছাড়া)

# --- ডাটাবেজ সেটআপ ---
def init_db():
    conn = sqlite3.connect("downloads.db")
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS file_stats (
            file_id INTEGER PRIMARY KEY,
            download_count INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()

# সাধারণ ইউজারের জন্য ডাউনলোড কাউন্ট ১ বৃদ্ধি করার ফাংশন
def update_and_get_downloads(file_id: int) -> int:
    conn = sqlite3.connect("downloads.db")
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO file_stats (file_id, download_count) VALUES (?, 1)
        ON CONFLICT(file_id) DO UPDATE SET download_count = download_count + 1
    ''', (file_id,))
    conn.commit()
    
    cursor.execute('SELECT download_count FROM file_stats WHERE file_id = ?', (file_id,))
    total = cursor.fetchone()[0]
    conn.close()
    return total

# কাউন্ট না বাড়িয়ে শুধু ডাটা দেখার ফাংশন
def get_file_stats(file_id: int) -> int:
    conn = sqlite3.connect("downloads.db")
    cursor = conn.cursor()
    cursor.execute('SELECT download_count FROM file_stats WHERE file_id = ?', (file_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else 0

init_db()

app = Client(
    "file_bot",
    bot_token=BOT_TOKEN,
    api_id=API_ID,
    api_hash=API_HASH
)

@app.on_message(filters.command("start") & filters.private)
async def start_handler(client, message):
    # ১. ফোর্স সাবস্ক্রিপশন চেক
    try:
        user = await client.get_chat_member(FORCE_SUB_CHANNEL, message.from_user.id)
        if user.status.value == "banned":
            return await message.reply("❌ আপনি এই চ্যানেলে ব্যানড রয়েছেন।")
    except UserNotParticipant:
        start_param = message.command[1] if len(message.command) > 1 else ""
        bot_username = (await client.get_me()).username
        retry_link = f"https://t.me/{bot_username}?start={start_param}" if start_param else f"https://t.me/{bot_username}"
        
        join_buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 চ্যানেলে জয়েন করুন", url=f"https://t.me/{FORCE_SUB_CHANNEL}")],
            [InlineKeyboardButton("🔄 পুনরায় চেষ্টা করুন", url=retry_link)]
        ])
        return await message.reply(
            "⚠️ **ফাইলটি পেতে আপনাকে অবশ্যই আমাদের চ্যানেলে জয়েন করতে হবে!**",
            reply_markup=join_buttons
        )
    except Exception as e:
        print(f"Force Sub Error: {e}")

    # ২. ফাইল ডেলিভারি প্রসেস
    if len(message.command) < 2:
        return await message.reply("ফাইল পেতে সঠিক লিংক ব্যবহার করুন।")

    payload = message.command[1]
    if not payload.isdigit():
        return await message.reply("❌ অকার্যকর ফাইল আইডি (Invalid File ID)।")

    file_id = int(payload)

    try:
        await client.get_chat(STORAGE_CHANNEL_ID)

        await client.copy_message(
            chat_id=message.chat.id,
            from_chat_id=STORAGE_CHANNEL_ID,
            message_id=file_id
        )

        # ইউজার এডমিন কিনা চেক করা হচ্ছে
        is_admin = bool(
            message.from_user.username and 
            message.from_user.username.lower() == ADMIN_USERNAME.lower()
        )

        if is_admin:
            # এডমিন হলে কাউন্ট না বাড়িয়ে বর্তমান কাউন্ট দেখানো হবে
            total_downloads = get_file_stats(file_id)
            await message.reply(f"📊 **এডমিন নোট:**\nএই ফাইলটি ইউজাররা মোট `{total_downloads}` বার ডাউনলোড করেছে। (আপনার ভিউ গণনা করা হয়নি)")
        else:
            # সাধারণ ইউজার হলে কাউন্ট ১ বাড়বে
            update_and_get_downloads(file_id)

    except PeerIdInvalid:
        await message.reply("⚠️ বট চ্যানেলটিকে চিনতে পারছে না। Admin পারমিশন চেক করুন।")
    except MessageIdInvalid:
        await message.reply(f"⚠️ {file_id} নম্বর ফাইলটি পাওয়া যায়নি বা মুছে ফেলা হয়েছে।")
    except FloodWait as e:
        await asyncio.sleep(e.value)
        await client.copy_message(
            chat_id=message.chat.id,
            from_chat_id=STORAGE_CHANNEL_ID,
            message_id=file_id
        )
        
        is_admin = bool(
            message.from_user.username and 
            message.from_user.username.lower() == ADMIN_USERNAME.lower()
        )
        if is_admin:
            total_downloads = get_file_stats(file_id)
            await message.reply(f"📊 **এডমিন নোট:**\nএই ফাইলটি ইউজাররা মোট `{total_downloads}` বার ডাউনলোড করেছে। (আপনার ভিউ গণনা করা হয়নি)")
        else:
            update_and_get_downloads(file_id)

    except RPCError as e:
        await message.reply("⚠️ ফাইলটি পাঠাতে সমস্যা হয়েছে।")
        print(f"RPC Error: {e}")
    except Exception as e:
        print(f"Unexpected Error: {e}")

# এডমিনদের জন্য ফাইল স্ট্যাটাস চেক করার আলাদা কমান্ড
@app.on_message(filters.command("stats") & filters.private)
async def stats_handler(client, message):
    if not message.from_user.username or message.from_user.username.lower() != ADMIN_USERNAME.lower():
        return

    if len(message.command) < 2:
        return await message.reply("ব্যবহার পদ্ধতি: `/stats <file_id>`\nউদাহরণ: `/stats 19`")

    file_id = message.command[1]
    if not file_id.isdigit():
        return await message.reply("❌ অকার্যকর ফাইল আইডি।")

    total = get_file_stats(int(file_id))
    await message.reply(f"📊 **ফাইল আইডি `{file_id}` এর তথ্য:**\nইউজারদের মোট ডাউনলোড: `{total}` বার।")

# --- বট স্টার্ট প্রসেস ---
async def main():
    await app.start()
    print("Bot Started Successfully!")
    await idle()
    await app.stop()

if __name__ == "__main__":
    asyncio.run(main())
