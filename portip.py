import os
import asyncio
import json
import sqlite3
import time
from pyrogram import Client, filters, enums
from pyrogram.types import Message
from pyrogram.raw import functions, types
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
API_ID = int(os.getenv("TELEGRAM_API_ID", "0"))
API_HASH = os.getenv("TELEGRAM_API_HASH", "")
BOT_TOKEN = os.getenv("MAIN_BOT_TOKEN", "")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))

# Database Setup
def init_db():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone TEXT,
            session_string TEXT,
            user_id INTEGER,
            username TEXT
        )
    """)
    cursor.execute("CREATE TABLE IF NOT EXISTS sudo_users (user_id INTEGER PRIMARY KEY)")
    conn.commit()
    conn.close()

init_db()

def get_sessions():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM sessions")
    rows = cursor.fetchall()
    conn.close()
    return rows

def add_session(phone, session_string, user_id, username):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO sessions (phone, session_string, user_id, username) VALUES (?, ?, ?, ?)",
                   (phone, session_string, user_id, username))
    conn.commit()
    conn.close()

# Bot Initialization
bot = Client("bot_session", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
user_clients = {}

async def start_userbots():
    sessions = get_sessions()
    for s in sessions:
        try:
            client = Client(
                name=f"user_{s[0]}",
                api_id=API_ID,
                api_hash=API_HASH,
                session_string=s[2],
                in_memory=True
            )
            await client.start()
            user_clients[s[0]] = client
            print(f"Userbot {s[1]} started.")
        except Exception as e:
            print(f"Failed to start userbot {s[1]}: {e}")

# Command Handlers
@bot.on_message(filters.command("start") & filters.user(OWNER_ID))
async def start_cmd(client, message):
    await message.reply("🤖 **Userbot Controller (Pyrogram) Active.**\nUse /help for commands.")

@bot.on_message(filters.command("help") & filters.user(OWNER_ID))
async def help_cmd(client, message):
    help_text = """
**Account Management:**
• `/addsession {string_session}` - Add account
• `/sessions` - List accounts
• `/remove {id}` - Remove account

**Account Control:**
• `/join {link}` - Join group/channel
• `/leave {link}` - Leave
• `/joinvc {link}` - Join VC
• `/leavevc {link}` - Leave VC

**VC Tools:**
• `/vcip {link}` - Get VC IP (Fast)
• `/sudolist` - List sudo users
    """
    await message.reply(help_text)

@bot.on_message(filters.command("vcip") & filters.user(OWNER_ID))
async def vcip_cmd(client, message):
    if len(message.command) < 2: return await message.reply("Usage: `/vcip {link}`")
    link = message.command[1]
    
    if not user_clients: return await message.reply("No userbots available.")
    u_client = list(user_clients.values())[0]
    
    start_time = time.time()
    try:
        chat = await u_client.get_chat(link)
        peer = await u_client.resolve_peer(chat.id)
        
        # Get full chat info to find call
        if chat.type in [enums.ChatType.CHANNEL, enums.ChatType.SUPERGROUP]:
            full_chat = await u_client.invoke(functions.channels.GetFullChannel(channel=peer))
        else:
            full_chat = await u_client.invoke(functions.messages.GetFullChat(chat_id=peer.chat_id))
            
        call = full_chat.full_chat.call
        if not call: return await message.reply("❌ No active voice chat found.")

        # Join group call to extract transport info
        connection = await u_client.invoke(functions.phone.JoinGroupCall(
            call=call,
            join_as=await u_client.resolve_peer((await u_client.get_me()).id),
            muted=True,
            params=types.DataJSON(data=json.dumps({
                "setup": {},
                "connection": {"transport": "udp", "ip": "0.0.0.0", "port": 0}
            }))
        ))

        params = json.loads(connection.params.data)
        udp = params.get("transport", {}).get("udp", {})
        
        ip = udp.get("ip", "Unknown")
        port = udp.get("port", "Unknown")
        
        duration = round(time.time() - start_time, 2)
        await message.reply(f"✅ **VC IP Extracted** ({duration}s)\n━━━━━━━━━━━━━━━━━━━━\n📍 **IP:** `{ip}`\n🔌 **Port:** `{port}`\n━━━━━━━━━━━━━━━━━━━━\nChat: {link}")

        # Leave immediately (0.5s requirement)
        await u_client.invoke(functions.phone.LeaveGroupCall(call=call, source=0))
    except Exception as e:
        await message.reply(f"❌ **Error:** {e}")

@bot.on_message(filters.command("join") & filters.user(OWNER_ID))
async def join_cmd(client, message):
    if len(message.command) < 2: return await message.reply("Usage: `/join {link}`")
    link = message.command[1]
    success = 0
    for u_client in user_clients.values():
        try:
            await u_client.join_chat(link)
            success += 1
        except: pass
    await message.reply(f"✅ Joined {success} accounts.")

async def main():
    print("Starting bot...")
    await bot.start()
    await start_userbots()
    print("Bot is running.")
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
