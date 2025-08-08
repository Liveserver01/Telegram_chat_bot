# sara_bot_fixed.py 
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ChatMemberUpdated
from flask import Flask, request, render_template_string, redirect
import threading
import os
import json
import requests
from fuzzywuzzy import fuzz

# -------------------------
# Environment & validation
# -------------------------
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")
if not ADMIN_PASSWORD:
    raise ValueError("❌ ADMIN_PASSWORD not set in environment variables!")

_api_id = os.environ.get("API_ID")
_api_hash = os.environ.get("API_HASH")
_bot_token = os.environ.get("BOT_TOKEN")

if not (_api_id and _api_hash and _bot_token):
    raise ValueError("❌ API_ID, API_HASH or BOT_TOKEN missing in environment variables!")

try:
    API_ID = int(_api_id)
except Exception:
    raise ValueError("❌ API_ID must be an integer")

API_HASH = _api_hash
BOT_TOKEN = _bot_token

# Optional channel config
CHANNEL_ID = int(os.environ.get("CHANNEL_ID", "-1002039183876"))
CHANNEL_INVITE_LINK = os.environ.get("CHANNEL_INVITE_LINK", "")

# GitHub JSON (primary source) and local fallback
GITHUB_JSON_URL = "https://raw.githubusercontent.com/Liveserver01/Telegram_chat_bot/3a8246bc555c65359c1d17a89f3b2705ed1b6350/movie_list.json"
LOCAL_JSON_PATH = "movie_list.json"

# -------------------------
# Initialize clients
# -------------------------
app = Client("sara_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
flask_app = Flask(__name__)

# -------------------------
# Helpers: load/save movies
# -------------------------
def load_movies_from_github():
    try:
        resp = requests.get(GITHUB_JSON_URL, timeout=8)
        if resp.status_code == 200:
            return resp.json()
        print("❌ GitHub JSON fetch failed:", resp.status_code)
    except Exception as e:
        print("❌ Error loading movie_list.json from GitHub:", e)
    # fallback to local file
    try:
        with open(LOCAL_JSON_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def load_movies_local():
    try:
        with open(LOCAL_JSON_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def save_movies_local(data):
    with open(LOCAL_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

# -------------------------
# Flask web routes (admin)
# -------------------------
admin_template = '''<!DOCTYPE html><html><head><title>Login</title></head><body><h2>🔐 Admin Login</h2><form method="POST">Password: <input type="password" name="password" required><input type="submit" value="Login"></form></body></html>'''
dashboard_template = '''<!DOCTYPE html><html><head><title>Dashboard</title></head><body><h2>🎜 Sara Bot Admin Panel</h2><p><b>Total Movies:</b> {{ count }}</p><table border="1" cellpadding="6"><tr><th>#</th><th>Title</th><th>Filename</th><th>URL</th><th>Actions</th></tr>{% for movie in movies %}<tr><td>{{ loop.index0 }}</td><td>{{ movie.title }}</td><td>{{ movie.filename }}</td><td>{{ movie.file_url }}</td><td><a href="/admin/edit/{{ loop.index0 }}?password={{ password }}">✏️ Edit</a> | <a href="/admin/delete/{{ loop.index0 }}?password={{ password }}" onclick="return confirm('Delete this movie?')">🗑 Delete</a></td></tr>{% endfor %}</table><hr><h3>Add New Movie</h3><form method="POST" action="/admin/add"><input type="hidden" name="password" value="{{ password }}">Title: <input name="title" required><br>Filename: <input name="filename"><br>File URL: <input name="file_url"><br><button type="submit">Add Movie</button></form></body></html>'''
edit_template = '''<!DOCTYPE html><html><head><title>Edit Movie</title></head><body><h2>Edit Movie #{{ index }}</h2><form method="POST"><input type="hidden" name="password" value="{{ password }}">Title: <input name="title" value="{{ movie.title }}" required><br>Filename: <input name="filename" value="{{ movie.filename }}"><br>File URL: <input name="file_url" value="{{ movie.file_url }}"><br><button type="submit">Save</button></form></body></html>'''

@flask_app.route("/")
def home():
    return "✅ Sara is alive via Render & GitHub!"

@flask_app.route("/movies")
def get_movies():
    data = load_movies_from_github()
    return {"count": len(data), "movies": data}

@flask_app.route("/admin", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        pwd = request.form.get("password")
        if pwd == ADMIN_PASSWORD:
            data = load_movies_local()
            return render_template_string(dashboard_template, movies=data, count=len(data), password=pwd)
        return "❌ Wrong password!"
    return render_template_string(admin_template)

@flask_app.route("/admin/add", methods=["POST"])
def admin_add_movie():
    pwd = request.form.get("password")
    if pwd != ADMIN_PASSWORD:
        return "❌ Unauthorized"
    data = load_movies_local()
    data.append({
        "title": request.form["title"],
        "filename": request.form.get("filename", ""),
        "file_url": request.form.get("file_url", "")
    })
    save_movies_local(data)
    return redirect(f"/admin?password={pwd}")

@flask_app.route("/admin/edit/<int:index>", methods=["GET", "POST"])
def admin_edit_movie(index):
    pwd = request.values.get("password")
    if pwd != ADMIN_PASSWORD:
        return "❌ Unauthorized"
    data = load_movies_local()
    if index >= len(data) or index < 0:
        return "❌ Invalid index"
    if request.method == "POST":
        data[index] = {
            "title": request.form["title"],
            "filename": request.form.get("filename", ""),
            "file_url": request.form.get("file_url", "")
        }
        save_movies_local(data)
        return redirect(f"/admin?password={pwd}")
    return render_template_string(edit_template, movie=data[index], index=index, password=pwd)

@flask_app.route("/admin/delete/<int:index>")
def admin_delete_movie(index):
    pwd = request.args.get("password")
    if pwd != ADMIN_PASSWORD:
        return "❌ Unauthorized"
    data = load_movies_local()
    if index >= len(data) or index < 0:
        return "❌ Invalid index"
    del data[index]
    save_movies_local(data)
    return redirect(f"/admin?password={pwd}")

# Run Flask in background thread
def run_flask():
    port = int(os.environ.get("PORT", 5000))
    flask_app.run(host="0.0.0.0", port=port)

flask_thread = threading.Thread(target=run_flask, daemon=True)
flask_thread.start()

# -------------------------
# Conversation triggers
# -------------------------
conversation_triggers = [
    ("good night", "Good night ji! Sweet dreams 🛌 ~ Apki Sara"),
    ("good morning", "Good morning! Naya din, nayi movie 🎥"),
    ("thank", "Arey koi baat nahi ji! ❤️"),
    ("love you", "Main bhi aapko movie ke saath saath pyaar karti hoon 😄"),
    ("hello", "Hello ji! Kaise ho aap?"),
    ("hi", "Hi hi! Sara yahan hai aapke liye."),
    ("bored", "Toh ek dhamakedar movie dekhte hain!"),
    ("movie batao", "Aap bas naam likho, main bhejti hoon!"),
    ("acha", "Bilkul sahi! Ab movie ka naam batao."),
    ("ok", "Chaliye fir! Movie ka naam likhiye."),
    ("haan", "Toh movie name likho fir!"),
    ("nahi", "Thik hai fir jab chahiye ho toh zarur batana."),
    ("kya dekh rahe ho", "Main toh sirf movie files dekh rahi hoon 😄")
]

# -------------------------
# Auto-save movie from channel
# -------------------------
@app.on_message(filters.channel & (filters.video | filters.document))
async def save_movie_from_channel(client, message):
    try:
        title = message.caption or (message.video.file_name if message.video else message.document.file_name)
        filename = message.video.file_name if message.video else message.document.file_name
        file_id = message.video.file_id if message.video else message.document.file_id

        if not title:
            print("⚠️ Title missing, skipping...")
            return

        movies = load_movies_local()

        for movie in movies:
            if movie.get("file_url") == file_id:
                print("ℹ️ Movie already in list, skipping:", title)
                return

        movies.append({
            "title": title.strip(),
            "filename": filename or "",
            "file_url": file_id
        })

        save_movies_local(movies)
        print(f"✅ Added movie: {title}")

    except Exception as e:
        print("❌ Error saving movie:", e)

# -------------------------
# Bot Handlers
# -------------------------
@app.on_message(filters.command("start"))
async def start_handler(client, message):
    user = message.from_user.first_name if message.from_user else "Guest"
    channel_button_url = CHANNEL_INVITE_LINK if CHANNEL_INVITE_LINK else f"https://t.me/c/{str(CHANNEL_ID)[4:]}"
    await message.reply_text(
        f"👋 Namaste {user} ji!\nMain *Sara* hoon — aapki movie wali dost 💅‍♀️🎥\nMovie ka naam bhejiye, main bhejti hoon!",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📺 Channel", url=channel_button_url)]])
    )

@app.on_message(filters.text & (filters.private | filters.group | filters.channel))
async def handle_text(client, message):
    if not message.from_user or message.from_user.is_bot:
        return

    text = message.text.lower().strip()
    if text.startswith("/"):
        return

    for key, reply in conversation_triggers:
        if key in text:
            await message.reply_text(reply)
            return

    try:
        data = load_movies_from_github()
        if not data:
            data = load_movies_local()

        best_match = None
        best_score = 0
        for movie in data:
            title = movie.get("title", "").lower()
            score = fuzz.partial_ratio(text, title)
            if score > best_score and score > 70:
                best_score = score
                best_match = movie

        if best_match:
            caption = f"🎬 *{best_match.get('title','Unknown')}*\n📁 Filename: `{best_match.get('filename', 'N/A')}`"
            await message.reply_video(best_match.get("file_url"), caption=caption, quote=True)
            return

        try:
            async for msg in app.search_messages(CHANNEL_ID, query=text, filter="video"):
                await msg.copy(message.chat.id)
                return
        except Exception as e:
            print("Channel search error (ignored):", e)

    except Exception as e:
        print("Error fetching/parsing movie list or searching:", e)

    if message.chat.type == "private":
        await message.reply_text("😔 Sorry ji... ye movie abhi available nahi hai.\nRequest bhej dijiye, main try karungi jaldi se lana 💕")

@app.on_chat_member_updated()
async def welcome(client, update: ChatMemberUpdated):
    try:
        new = getattr(update, "new_chat_member", None)
        if new and not new.user.is_bot:
            name = new.user.first_name
            await client.send_message(
                chat_id=update.chat.id,
                text=f"🎀 Hi {name} ji! Welcome to our group 🎥\nMain *Sara* hoon — yahan ki movie wali dost 💅‍♀️\nMovie chahiye toh bas naam likho!"
            )
    except Exception as e:
        print("Welcome handler error:", e)

# -------------------------
# Start the bot
# -------------------------
if __name__ == "__main__":
    print("Sara bot starting... (Flask running in background thread)")
    app.run()
