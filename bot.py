# ✅ Full Updated bot.py
# - GitHub-based JSON fetch
# - Admin Panel (Add/Edit/Delete)
# - file_url support
# - Hinglish conversation replies
# - fallback fuzzy movie match

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ChatMemberUpdated
from flask import Flask, request, render_template_string, redirect
import threading
import os
import json
import requests
from fuzzywuzzy import fuzz

# 🔐 Secure Password
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")
if not ADMIN_PASSWORD:
    raise ValueError("❌ ADMIN_PASSWORD not set in environment variables!")


# 🌐 Env Vars
API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_USERNAME = os.environ.get("CHANNEL_USERNAME", "youtuner02alltypemovies")

# 🧠 GitHub movie_list.json URL
GITHUB_JSON_URL = "https://raw.githubusercontent.com/Liveserver01/Telegram_chat_bot/3a8246bc555c65359c1d17a89f3b2705ed1b6350/movie_list.json
"

# 🤖 Bot init
app = Client("sara_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
flask_app = Flask(__name__)

# ✅ GitHub JSON Fetch
def load_movies_from_github():
    try:
        response = requests.get(GITHUB_JSON_URL)
        if response.status_code == 200:
            return response.json()
        print("❌ GitHub JSON fetch failed:", response.status_code)
        return []
    except Exception as e:
        print("❌ Error loading movie_list.json:", e)
        return []

# 🌐 Flask routes
@flask_app.route("/")
def home():
    return "✅ Sara is alive via Render & GitHub!"

@flask_app.route("/movies")
def get_movies():
    data = load_movies_from_github()
    return {"count": len(data), "movies": data}

# 🔐 Admin Panel Templates
admin_template = '''<!DOCTYPE html><html><head><title>Login</title></head><body><h2>🔐 Admin Login</h2><form method="POST">Password: <input type="password" name="password" required><input type="submit" value="Login"></form></body></html>'''

dashboard_template = '''<!DOCTYPE html><html><head><title>Dashboard</title></head><body><h2>🎜 Sara Bot Admin Panel</h2><p><b>Total Movies:</b> {{ count }}</p><table border="1" cellpadding="6"><tr><th>#</th><th>Title</th><th>Filename</th><th>URL</th><th>Actions</th></tr>{% for movie in movies %}<tr><td>{{ loop.index0 }}</td><td>{{ movie.title }}</td><td>{{ movie.filename }}</td><td>{{ movie.file_url }}</td><td><a href="/admin/edit/{{ loop.index0 }}?password={{ password }}">✏️ Edit</a> | <a href="/admin/delete/{{ loop.index0 }}?password={{ password }}" onclick="return confirm('Delete this movie?')">🗑 Delete</a></td></tr>{% endfor %}</table><hr><h3>Add New Movie</h3><form method="POST" action="/admin/add"><input type="hidden" name="password" value="{{ password }}">Title: <input name="title" required><br>Filename: <input name="filename"><br>File URL: <input name="file_url"><br><button type="submit">Add Movie</button></form></body></html>'''

edit_template = '''<!DOCTYPE html><html><head><title>Edit Movie</title></head><body><h2>Edit Movie #{{ index }}</h2><form method="POST"><input type="hidden" name="password" value="{{ password }}">Title: <input name="title" value="{{ movie.title }}" required><br>Filename: <input name="filename" value="{{ movie.filename }}"><br>File URL: <input name="file_url" value="{{ movie.file_url }}"><br><button type="submit">Save</button></form></body></html>'''

@flask_app.route("/admin", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        pwd = request.form.get("password")
        if pwd == ADMIN_PASSWORD:
            data = load_movies_from_github()
            return render_template_string(dashboard_template, movies=data, count=len(data), password=pwd)
        return "❌ Wrong password!"
    return render_template_string(admin_template)

@flask_app.route("/admin/add", methods=["POST"])
def admin_add_movie():
    pwd = request.form.get("password")
    if pwd != ADMIN_PASSWORD:
        return "❌ Unauthorized"
    try:
        with open("movie_list.json", "r", encoding="utf-8") as f:
            data = json.load(f)
    except:
        data = []
    data.append({
        "title": request.form["title"],
        "filename": request.form.get("filename", ""),
        "file_url": request.form.get("file_url", "")
    })
    with open("movie_list.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    return redirect(f"/admin?password={pwd}")

@flask_app.route("/admin/edit/<int:index>", methods=["GET", "POST"])
def admin_edit_movie(index):
    pwd = request.values.get("password")
    if pwd != ADMIN_PASSWORD:
        return "❌ Unauthorized"
    try:
        with open("movie_list.json", "r", encoding="utf-8") as f:
            data = json.load(f)
    except:
        return "❌ movie_list.json not found"
    if index >= len(data):
        return "❌ Invalid index"
    if request.method == "POST":
        data[index] = {
            "title": request.form["title"],
            "filename": request.form.get("filename", ""),
            "file_url": request.form.get("file_url", "")
        }
        with open("movie_list.json", "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        return redirect(f"/admin?password={pwd}")
    return render_template_string(edit_template, movie=data[index], index=index, password=pwd)

@flask_app.route("/admin/delete/<int:index>")
def admin_delete_movie(index):
    pwd = request.args.get("password")
    if pwd != ADMIN_PASSWORD:
        return "❌ Unauthorized"
    try:
        with open("movie_list.json", "r", encoding="utf-8") as f:
            data = json.load(f)
    except:
        return "❌ movie_list.json not found"
    if index >= len(data):
        return "❌ Invalid index"
    del data[index]
    with open("movie_list.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    return redirect(f"/admin?password={pwd}")

# 🔁 Run Flask app in background
threading.Thread(target=lambda: flask_app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))).start()

# ✨ Hinglish Triggers
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

@app.on_message(filters.command("start"))
async def start(client, message):
    user = message.from_user.first_name
    await message.reply_text(
        f"👋 Namaste {user} ji!\nMain *Sara* hoon — aapki movie wali dost 💅‍♀️🎥\nMovie ka naam bhejiye, main bhejti hoon!",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📺 Channel", url=f"https://t.me/{CHANNEL_USERNAME}")]
        ])
    )

@app.on_message(filters.text & (filters.private | filters.group))
async def handle_text(client, message):
    if not message.from_user or message.from_user.is_bot:
        return
    text = message.text.lower().strip()
    if text.startswith("/"):
        return
    for keyword, reply in conversation_triggers:
        if keyword in text:
            await message.reply_text(reply)
            return
    try:
        data = load_movies_from_github()
        best_match = None
        best_score = 0
        for movie in data:
            score = fuzz.partial_ratio(text, movie["title"].lower())
            if score > best_score and score > 70:
                best_score = score
                best_match = movie
        if best_match and best_match.get("file_url"):
            await message.reply_document(best_match["file_url"], caption=best_match["title"])
            return
    except Exception as e:
        print("❌ Search Error:", e)
    await message.reply_text("😔 Sorry ji... wo movie abhi nahi hai.\nRequest bhej dijiye, main jald laungi 💕")

@app.on_chat_member_updated()
async def welcome(client, update: ChatMemberUpdated):
    if update.new_chat_member and not update.new_chat_member.user.is_bot:
        name = update.new_chat_member.user.first_name
        await client.send_message(
            chat_id=update.chat.id,
            text=f"🎀 Hi {name} ji! Welcome to our group 🎥\nMain *Sara* hoon — yahan ki movie wali dost 💅‍♀️\nMovie chahiye toh bas naam likho!"
        )

app.run()


