from updater import add_movie_to_json   
from pyrogram import Client, filters
from pyrogram.types import ChatMemberUpdated, InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask, request, render_template_string, redirect
import threading
import os
import json
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

# 🤖 Bot init
app = Client("sara_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
flask_app = Flask(__name__)

# 🌐 Flask keep-alive
@flask_app.route("/")
def home():
    return "✅ Sara Ab Apna Kaam Karne Ke Liye Taiyar Hai!"

@flask_app.route("/movies")
def get_movies():
    try:
        with open("movie_list.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        return {"count": len(data), "movies": data}
    except:
        return {"error": "movie_list.json not found"}

# 🔐 Admin Panel Templates
admin_template = '''
<!DOCTYPE html><html><head><title>Sara Admin Login</title></head>
<body><h2>🔐 Admin Login</h2><form method="POST">
Password: <input type="password" name="password" required>
<input type="submit" value="Login"></form></body></html>
'''

dashboard_template = '''
<!DOCTYPE html><html><head><title>Admin Dashboard</title></head><body>
<h2>🎜 Sara Bot Admin Panel</h2><p><b>Total Movies:</b> {{ count }}</p>
<table border="1" cellpadding="6">
<tr><th>#</th><th>Title</th><th>Msg ID</th><th>Filename</th><th>Actions</th></tr>
{% for movie in movies %}<tr>
<td>{{ loop.index0 }}</td><td>{{ movie.title }}</td><td>{{ movie.msg_id }}</td><td>{{ movie.filename }}</td>
<td>
    <a href="/admin/edit/{{ loop.index0 }}?password={{ password }}">✏️ Edit</a> |
    <a href="/admin/delete/{{ loop.index0 }}?password={{ password }}" onclick="return confirm('Delete this movie?')">🗑 Delete</a>
</td>
</tr>{% endfor %}</table><hr>
<h3>Add New Movie</h3>
<form method="POST" action="/admin/add">
<input type="hidden" name="password" value="{{ password }}">
Title: <input name="title" required><br>
Msg ID: <input name="msg_id" required><br>
Filename: <input name="filename"><br>
<button type="submit">Add Movie</button>
</form></body></html>
'''

edit_template = '''
<!DOCTYPE html><html><head><title>Edit Movie</title></head><body>
<h2>✏️ Edit Movie #{{ index }}</h2>
<form method="POST">
<input type="hidden" name="password" value="{{ password }}">
Title: <input name="title" value="{{ movie.title }}" required><br>
Msg ID: <input name="msg_id" value="{{ movie.msg_id }}" required><br>
Filename: <input name="filename" value="{{ movie.filename }}"><br>
<button type="submit">Save Changes</button>
</form></body></html>
'''

@flask_app.route("/admin", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        pwd = request.form.get("password")
        if pwd == ADMIN_PASSWORD:
            try:
                with open("movie_list.json", "r", encoding="utf-8") as f:
                    data = json.load(f)
            except:
                data = []
            return render_template_string(dashboard_template, movies=data, count=len(data), password=pwd)
        return "❌ Wrong password!"
    return render_template_string(admin_template)

@flask_app.route("/admin/add", methods=["POST"])
def admin_add_movie():
    pwd = request.form.get("password")
    if pwd != ADMIN_PASSWORD:
        return "❌ Unauthorized"
    title = request.form["title"]
    msg_id = int(request.form["msg_id"])
    filename = request.form.get("filename") or None
    add_movie_to_json(title, msg_id, filename)
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
            "msg_id": int(request.form["msg_id"]),
            "filename": request.form.get("filename") or ""
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

# 🔁 Flask Background Thread
threading.Thread(target=lambda: flask_app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))).start()

# 🌟 Repeat tracking
user_message_history = {}

# 💬 Hinglish Conversation Triggers
conversation_triggers = [
    ("good night", "Good night ji! Sweet dreams 💤 ~ Apki Sara"),
    ("good morning", "Good morning! Naya din, nayi movie 🎬"),
    ("thank", "Arey koi baat nahi ji! ❤️"),
    ("love you", "Main bhi aapko movie ke saath saath pyaar karti hoon 😄"),
    ("hello", "Hello ji! Kaise ho aap?"),
    ("hi", "Hi hi! Sara yahan hai aapke liye."),
    ("kya kar rahe ho", "Bas aapke liye movies search kar rahi hoon."),
    ("bored", "Toh ek dhamakedar movie dekhte hain!"),
    ("kaisi ho", "Main acchi hoon! Aap sunao?"),
    ("kya haal hai", "Sab badiya! Aapke liye movie ready hai kya?"),
    ("mood off", "Mood thik karte hain ek zabardast movie se!"),
    ("party", "Movie + Popcorn = Best Party!"),
    ("movie batao", "Aap bas naam batao, main bhejti hoon!"),
    ("acha", "Bilkul sahi! Ab movie ka naam batao."),
    ("ok", "Chaliye fir! Movie ka naam likhiye."),
    ("arey", "Kya hua ji? Movie chahiye kya?"),
    ("haan", "Toh movie name likho fir!"),
    ("nahi", "Thik hai fir jab chahiye ho toh zarur batana."),
    ("kahan se ho", "Main Telegram ki duniya se hoon, Sara naam hai mera!"),
    ("khana khaya", "Main bot hoon, movie meri khuraak hai 😋"),
    ("kya dekh rahe ho", "Main toh sirf movie files dekh rahi hoon 😄"),
    ("kya kar rahi ho", "Bas aapke liye movies search kar rahi hoon."),
]

@app.on_message(filters.command("start"))
async def start(client, message):
    user = message.from_user.first_name
    await message.reply_text(
        f"👋 Namaste {user} ji!\nMain *Sara* hoon — aapki movie wali dost 💁‍♀️🎥\nBas movie ka naam bhejiye... main dhoond kar de doongi!\n\n📺 Hamara channel: https://t.me/{CHANNEL_USERNAME}",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📺 Channel kholen", url=f"https://t.me/{CHANNEL_USERNAME}")]
        ])
    )

@app.on_message((filters.document | filters.video) & filters.private)
async def handle_file(client, message):
    title = message.caption or message.text or "Untitled"
    filename = message.document.file_name if message.document else message.video.file_name
    add_movie_to_json(title, message.message_id, filename)
    await message.reply_text("✅ Movie JSON में save हो गई 📁")

@app.on_message(filters.text & (filters.private | filters.group))
async def handle_text(client, message):
    if not message.from_user or message.from_user.is_bot:
        return
    text = message.text.lower().strip()
    if text.startswith("/"):
        return
    user_id = message.from_user.id
    chat_id = message.chat.id
    if user_id not in user_message_history:
        user_message_history[user_id] = {}
    user_msgs = user_message_history[user_id]
    user_msgs[text] = user_msgs.get(text, 0) + 1
    if user_msgs[text] > 3 or user_msgs[text] > 1:
        return
    if message.chat.type == "private":
        for keyword, reply in conversation_triggers:
            if keyword in text:
                await message.reply_text(reply)
                return
    try:
        stop_words = {"facebook", "instagram", "youtube", "tiktok", "whatsapp", "google", "telegram", "game", "gaming", "terabox", "feedback", "dubbed", "emoji", "streaming", "link", "romance", "romantic", "status", "application", "install", "android", "click", "language", "platform", "channel", "online", "comedy", "movies", "movie", "bhai", "bhejo", "bro", "hindi", "english", "south"}
        if any(w in text for w in stop_words):
            return
        with open("movie_list.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        best_match = None
        best_score = 0
        for movie in data:
            score = fuzz.partial_ratio(text, movie["title"].lower())
            if score > best_score and score > 70:
                best_score = score
                best_match = movie
        if best_match:
            await client.forward_messages(chat_id, CHANNEL_USERNAME, best_match["msg_id"])
            return
    except Exception as e:
        print("Search Error in JSON:", e)
    try:
        async for msg in app.get_chat_history(CHANNEL_USERNAME, limit=1000):
            if msg.caption and fuzz.partial_ratio(text, msg.caption.lower()) > 75:
                await msg.forward(chat_id)
                return
    except Exception as e:
        print("Search Error in Channel:", e)
    if message.chat.type == "private":
        if any(w in text for w in ["upload", "movie chahiye", "please", "req"]):
            await message.reply_text("🍿 Ok ji! Aapki request note kar li gayi hai, jald hi upload karungi 🥰")
        else:
            await message.reply_text("😔 Sorry ji... wo movie abhi upload nahi hui hai.\nRequest bhej dijiye, main koshish karungi jald lane ki 💕")

@app.on_chat_member_updated()
async def welcome(client, update: ChatMemberUpdated):
    if update.new_chat_member and not update.new_chat_member.user.is_bot:
        name = update.new_chat_member.user.first_name
        await client.send_message(
            chat_id=update.chat.id,
            text=f"🎀 Hi {name} ji! Welcome to our group 🎥\nMain *Sara* hoon — yahan ki movie wali dost 💁‍♀️\nKoi movie chahiye toh bas naam boliye ❤️"
        )

app.run()
