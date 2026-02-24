import os
import asyncio
import json
import sqlite3
import time
from telethon import TelegramClient, events, functions, types
from telethon.sessions import StringSession

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
bot = TelegramClient("bot_session", API_ID, API_HASH).start(bot_token=BOT_TOKEN)
user_clients = {}

async def start_userbots():
    sessions = get_sessions()
    for s in sessions:
        try:
            client = TelegramClient(StringSession(s[2]), API_ID, API_HASH)
            await client.connect()
            if await client.is_user_authorized():
                user_clients[s[0]] = client
                print(f"Userbot {s[1]} started.")
        except Exception as e:
            print(f"Failed to start userbot {s[1]}: {e}")

@bot.on(events.NewMessage(pattern="/start"))
async def start_cmd(event):
    if event.sender_id != OWNER_ID: return
    await event.reply("🤖 **Userbot Controller Active.**\nUse /help for commands.")

@bot.on(events.NewMessage(pattern="/help"))
async def help_cmd(event):
    if event.sender_id != OWNER_ID: return
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
    await event.reply(help_text)

@bot.on(events.NewMessage(pattern="/addsession"))
async def add_session_cmd(event):
    if event.sender_id != OWNER_ID: return
    try:
        session_str = event.text.split(" ", 1)[1]
        client = TelegramClient(StringSession(session_str), API_ID, API_HASH)
        await client.connect()
        me = await client.get_me()
        add_session(me.phone, session_str, me.id, me.username)
        await event.reply(f"✅ Added account: {me.first_name} (@{me.username})")
        await start_userbots()
    except Exception as e:
        await event.reply(f"❌ Error: {e}")

@bot.on(events.NewMessage(pattern="/sessions"))
async def list_sessions_cmd(event):
    if event.sender_id != OWNER_ID: return
    sessions = get_sessions()
    if not sessions: return await event.reply("No sessions found.")
    resp = "**Active Sessions:**\n"
    for s in sessions:
        resp += f"ID: `{s[0]}` | {s[1]} (@{s[4]})\n"
    await event.reply(resp)

@bot.on(events.NewMessage(pattern="/remove"))
async def remove_session_cmd(event):
    if event.sender_id != OWNER_ID: return
    args = event.text.split()
    if len(args) < 2: return await event.reply("Usage: `/remove {id}`")
    session_id = int(args[1])
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
    conn.commit()
    conn.close()
    user_clients.pop(session_id, None)
    await event.reply(f"✅ Session {session_id} removed.")

@bot.on(events.NewMessage(pattern="/vcip"))
async def vcip_cmd(event):
    if event.sender_id != OWNER_ID: return
    args = event.text.split()
    if len(args) < 2: return await event.reply("Usage: `/vcip {link}`")
    link = args[1]
    
    sessions = get_sessions()
    if not sessions: return await event.reply("No userbots available.")
    
    client = user_clients.get(sessions[0][0])
    if not client: return await event.reply("Primary userbot not connected.")

    start_time = time.time()
    try:
        peer = await client.get_entity(link)
        full = await client(functions.channels.GetFullChannelRequest(channel=peer))
        call = full.full_chat.call
        if not call: return await event.reply("❌ No active voice chat found.")

        connection = await client(functions.phone.JoinGroupCallRequest(
            call=call,
            join_as=await client.get_me(),
            muted=True,
            params=types.DataJSON(data=json.dumps({
                "setup": {},
                "connection": {"transport": "udp", "ip": "0.0.0.0", "port": 0}
            }))
        ))

        params = json.loads(connection.params.data)
        udp = params.get("transport", {}).get("udp", {})
        duration = round(time.time() - start_time, 2)

        resp = f"""
✅ **VC IP Extracted** ({duration}s)
━━━━━━━━━━━━━━━━━━━━
📍 **IP:** `{udp.get('ip', 'Unknown')}`
🔌 **Port:** `{udp.get('port', 'Unknown')}`
🛠 **Protocol:** `{udp.get('protocol', 'UDP')}`
━━━━━━━━━━━━━━━━━━━━
Chat: {link}
        """
        await event.reply(resp)
        await client(functions.phone.LeaveGroupCallRequest(call=call, source=0))
    except Exception as e:
        await event.reply(f"❌ **Error:** {e}")

async def main():
    await start_userbots()
    await bot.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
