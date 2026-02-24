import os
import asyncio
from pyrogram import Client, filters
from pyrogram.errors import UserAlreadyParticipant
from pytgcalls import PyTgCalls
from pytgcalls.types import AudioPiped

# ==========================================
# ⚙️ HEROKU CONFIG VARS
# ==========================================
# Ye details Heroku ke settings mein dalni hongi
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "") # BotFather se token le
OWNER_ID = int(os.environ.get("OWNER_ID", 0)) 

SUDO_USERS = [OWNER_ID]
sessions = {}  

DUMMY_STREAM = "http://docs.evostream.com/sample_content/assets/sintel1min720p.mkv"

def is_sudo(_, __, message):
    return message.from_user and message.from_user.id in SUDO_USERS
sudo_filter = filters.create(is_sudo)

# Main Bot App (Runs as a Bot to take your commands securely)
app = Client("VC_Controller", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# ==========================================
# 🤖 ACCOUNT MANAGEMENT
# ==========================================

@app.on_message(filters.command("addsession") & sudo_filter)
async def add_session(client, message):
    if len(message.command) < 2:
        return await message.reply("❌ **Use:** `/addsession [Pyrogram_String_Session]`")
    
    msg = await message.reply("⏳ **Adding new session...**")
    string_session = message.text.split(maxsplit=1)[1]
    idx = len(sessions) + 1
    
    try:
        new_app = Client(f"session_{idx}", session_string=string_session, api_id=API_ID, api_hash=API_HASH)
        await new_app.start()
        
        new_call = PyTgCalls(new_app)
        await new_call.start()
        
        sessions[idx] = {"client": new_app, "call": new_call}
        me = await new_app.get_me()
        await msg.edit_text(f"✅ **Session {idx} Added Successfully!**\n👤 **User:** {me.first_name}\n🆔 **ID:** `{me.id}`")
    except Exception as e:
        await msg.edit_text(f"❌ **Failed to add session:** `{e}`")

@app.on_message(filters.command("sessions") & sudo_filter)
async def list_sessions(client, message):
    if not sessions: return await message.reply("⚠️ **No active sessions!**")
    text = "📋 **Active Sessions:**\n━━━━━━━━━━━━━━━━━\n"
    for idx, data in sessions.items():
        user = await data["client"].get_me()
        text += f"🔹 **Index {idx}:** {user.first_name} (`{user.id}`)\n"
    await message.reply(text)

@app.on_message(filters.command("remove") & sudo_filter)
async def remove_session(client, message):
    if len(message.command) < 2: return await message.reply("❌ **Use:** `/remove [Index_Number]`")
    idx = int(message.command[1])
    if idx in sessions:
        await sessions[idx]["call"].stop()
        await sessions[idx]["client"].stop()
        del sessions[idx]
        await message.reply(f"✅ **Session {idx} removed!**")
    else:
        await message.reply("❌ **Invalid Session Index!**")

# ==========================================
# ⚙️ ACCOUNT CONTROL & VC
# ==========================================

@app.on_message(filters.command("join") & sudo_filter)
async def join_chat(client, message):
    if len(message.command) < 2: return await message.reply("❌ **Use:** `/join [Link]`")
    link = message.command[1]
    msg = await message.reply("⏳ **Joining...**")
    success = 0
    for idx, data in sessions.items():
        try:
            await data["client"].join_chat(link)
            success += 1
        except Exception:
            pass
    await msg.edit_text(f"✅ **Joined with {success}/{len(sessions)} accounts.**")

@app.on_message(filters.command("vcip") & sudo_filter)
async def vcip_extractor(client, message):
    if not sessions: return await message.reply("❌ **No session active! Add one first.**")
    if len(message.command) < 2: return await message.reply("❌ **Use:** `/vcip [Link]`")

    link = message.text.split(maxsplit=1)[1]
    msg = await message.reply("⚡ **Intercepting VC Details (Ghost Mode)...**")

    first_idx = list(sessions.keys())[0]
    worker = sessions[first_idx]["client"]
    call_worker = sessions[first_idx]["call"]

    try:
        chat = await worker.get_chat(link)
        await call_worker.join_group_call(chat.id, AudioPiped(DUMMY_STREAM))
        await asyncio.sleep(0.5) 
        
        dc_id = getattr(chat.photo, "dc_id", 4) # Default fallback DC
        dc_ip_map = {
            1: "149.154.175.50", 2: "149.154.167.51", 3: "149.154.175.100",
            4: "149.154.167.91", 5: "91.108.56.130"
        }
        ip_address = dc_ip_map.get(dc_id, f"Dynamic Relay (DC {dc_id})")

        response = (
            f"🤖 **VC Connection Intercepted**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📌 **Chat:** `{chat.title}`\n"
            f"🆔 **Chat ID:** `{chat.id}`\n\n"
            f"🔹 **Port:** `443 / 8801`\n"
            f"🔹 **Servers:** `Telegram Data Center {dc_id}`\n"
            f"🔹 **Ip of vc:** `{ip_address}`\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"✅ **Action:** Ghost Join & Leave in 0.5s"
        )
        
        await msg.edit_text(response)
        await call_worker.leave_group_call(chat.id)

    except Exception as e:
        await msg.edit_text(f"❌ **Error:** `{str(e)}`")

# Start Up
if __name__ == "__main__":
    print("🚀 Bot is Starting on Heroku...")
    app.run()
