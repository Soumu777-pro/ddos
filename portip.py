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
STRING_SESSION = os.getenv("STRING_SESSION", "")

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

# Authorized Users Filter
async def is_authorized(_, __, message: Message):
    if not message.from_user: return False
    user_id = message.from_user.id
    if user_id == OWNER_ID: return True
    
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM sudo_users WHERE user_id = ?", (user_id,))
    res = cursor.fetchone()
    conn.close()
    return bool(res)

authorized = filters.create(is_authorized)

# Bot Initialization
bot = Client("bot_session", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, in_memory=True)
user_clients = {}

async def start_userbots():
    # Start session from environment variable if exists
    if STRING_SESSION:
        try:
            client = Client(
                name="env_user",
                api_id=API_ID,
                api_hash=API_HASH,
                session_string=STRING_SESSION,
                in_memory=True
            )
            await client.start()
            me = await client.get_me()
            user_clients[0] = client
            print(f"✅ Userbot (from Env) {me.first_name} (@{me.username}) started.")
        except Exception as e:
            print(f"❌ Failed to start environment userbot: {e}")

    # Start sessions from database
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
            print(f"✅ Userbot {s[1]} (@{s[4]}) started.")
        except Exception as e:
            print(f"❌ Failed to start userbot {s[1]}: {e}")

# Command Handlers
@bot.on_message(filters.command("start"))
async def start_cmd(client, message):
    user_id = message.from_user.id
    if await is_authorized(None, None, message):
        await message.reply("🤖 **Userbot Controller (Pyrogram) Active.**\n\nI am ready to manage your assistant accounts and extract VC IPs.\nUse /help to see all available commands.")
    else:
        await message.reply(f"❌ **Unauthorized.**\nYour ID: `{user_id}`\n\nPlease set this ID in your Heroku `OWNER_ID` config var.")

@bot.on_message(filters.command("help") & authorized)
async def help_cmd(client, message):
    help_text = """
**📱 Account Management:**
• `/addsession {string}` - Add a new assistant account
• `/sessions` - List all connected accounts
• `/remove {id}` - Remove an account by ID

**🎮 Account Control:**
• `/join {link}` - All accounts join a chat
• `/leave {link}` - All accounts leave a chat
• `/joinvc {link}` - All accounts join a Voice Chat
• `/leavevc {link}` - All accounts leave a Voice Chat

**🔍 VC Tools:**
• `/vcip {link}` - **Instant VC IP Extraction**
• `/ping` - Check bot latency

**👑 Admin Tools:**
• `/sudolist` - List all authorized users
• `/addsudo {id}` - Add a new sudo user (Owner only)
• `/removesudo {id}` - Remove a sudo user (Owner only)
    """
    await message.reply(help_text)

@bot.on_message(filters.command("vcip") & authorized)
async def vcip_cmd(client, message):
    if len(message.command) < 2: return await message.reply("Usage: `/vcip {link}`")
    link = message.command[1]
    
    if not user_clients: return await message.reply("❌ No userbots available. Add one using /addsession or STRING_SESSION.")
    
    u_client = list(user_clients.values())[0]
    u_me = await u_client.get_me()
    
    status_msg = await message.reply("⚡️ **Getting VC IP...**")
    
    start_time = time.time()
    try:
        chat = await u_client.get_chat(link)
        peer = await u_client.resolve_peer(chat.id)
        
        if chat.type in [enums.ChatType.CHANNEL, enums.ChatType.SUPERGROUP]:
            full_chat = await u_client.invoke(functions.channels.GetFullChannel(channel=peer))
        else:
            full_chat = await u_client.invoke(functions.messages.GetFullChat(chat_id=peer.chat_id))
            
        call = full_chat.full_chat.call
        if not call: return await status_msg.edit("❌ No active voice chat found.")

        connection = await u_client.invoke(functions.phone.JoinGroupCall(
            call=call,
            join_as=await u_client.resolve_peer(u_me.id),
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
        duration_ms = round((time.time() - start_time) * 1000, 2)

        resp = f"✅ **VC IP Extracted!**\n\n**Account:** {u_me.first_name}\n**Chat Name:** {chat.title}\n**Chat ID:** `{chat.id}`\n**IP:** `{ip}`\n**Port:** `{port}`\n**Time:** `{duration_ms}ms`\n\n⚠️ **Left VC immediately**"
        await status_msg.edit(resp)
        await u_client.invoke(functions.phone.LeaveGroupCall(call=call, source=0))
    except Exception as e:
        await status_msg.edit(f"❌ **Error:** {e}")

async def main():
    print("🚀 Starting Userbot Controller...")
    await bot.start()
    await start_userbots()
    print("✨ Bot is fully operational.")
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
