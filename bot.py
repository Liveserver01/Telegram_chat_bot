from pyrogram import Client, filters
from pyrogram.types import ChatMemberUpdated, InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask, request, render_template_string, redirect, session, url_for
import threading
import os
import json
import requests
import re
from fuzzywuzzy import fuzz
from base64 import b64encode
from datetime import timedelta

# -------------------------
# Environment Variables Setup
# -------------------------
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")
if not ADMIN_PASSWORD:
    raise ValueError("❌ ADMIN_PASSWORD not set in environment variables!")

_api_id = os.environ.get("API_ID")
_api_hash = os.environ.get("API_HASH")
_bot_token = os.environ.get("BOT_TOKEN")
_channel_id = os.environ.get("CHANNEL_ID")
_flask_secret_key = os.environ.get("FLASK_SECRET_KEY", "default_secret_key")
_channel_invite_link = os.environ.get("CHANNEL_INVITE_LINK", "")

if not (_api_id and _api_hash and _bot_token and _channel_id):
    raise ValueError("❌ API_ID, API_HASH, BOT_TOKEN or CHANNEL_ID missing in environment variables!")

try:
    API_ID = int(_api_id)
    CHANNEL_ID = int(_channel_id)
except Exception:
    raise ValueError("❌ API_ID and CHANNEL_ID must be integers")

API_HASH = _api_hash
BOT_TOKEN = _bot_token
FLASK_SECRET_KEY = _flask_secret_key
CHANNEL_INVITE_LINK = _channel_invite_link

LOCAL_JSON_PATH = "movie_list.json"

# -------------------------
# Flask App Setup
# -------------------------
flask_app = Flask(__name__)
flask_app.secret_key = FLASK_SECRET_KEY
flask_app.permanent_session_lifetime = timedelta(hours=8)

# -------------------------
# Pyrogram Bot Setup
# -------------------------
app = Client("sara_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# -------------------------
# Thread Lock for JSON access
# -------------------------
json_lock = threading.Lock()

# -------------------------
# Movie List Helpers
# -------------------------
def load_movies_local():
    try:
        with open(LOCAL_JSON_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def save_movies_local(data):
    with open(LOCAL_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def add_movie_to_json(title, msg_id, filename=None, file_url=None):
    with json_lock:
        try:
            data = load_movies_local()
        except:
            data = []

        # Avoid duplicate msg_id or file_url
        if msg_id and any(m.get("msg_id") == msg_id for m in data):
            print(f"Duplicate msg_id {msg_id}, skipping add.")
            return False
        if file_url and any(m.get("file_url") == file_url for m in data):
            print(f"Duplicate file_url {file_url}, skipping add.")
            return False

        movie_entry = {
            "title": title.strip(),
            "msg_id": msg_id or 0,
            "filename": filename or "",
            "file_url": file_url or ""
        }
        data.append(movie_entry)
        save_movies_local(data)
        print(f"Added movie: {title} msg_id:{msg_id} file_url:{file_url}")
        return True

# -------------------------
# Caption parsing function
# -------------------------
def parse_caption(caption_text):
    lines = caption_text.split('\n')
    title = None
    for line in lines:
        line_strip = line.strip()
        if line_strip != "" and not line_strip.startswith(("----","📌","Feedback","Download")):
            title = line_strip
            break
    urls = re.findall(r'https?://\S+', caption_text)
    download_link = urls[0] if urls else None
    return title, download_link

# -------------------------
# Flask Routes - Admin Panel
# -------------------------
login_template = '''
<!doctype html>
<html>
<head><title>Admin Login</title></head>
<body>
  <h2>🔐 Admin Login</h2>
  {% if error %}<p style="color:red">{{ error }}</p>{% endif %}
  <form method="POST" action="{{ url_for('admin_login') }}">
    Password: <input type="password" name="password" required>
    <button type="submit">Login</button>
  </form>
</body>
</html>
'''

dashboard_template = '''
<!doctype html>
<html>
<head>
  <title>Sara Bot - Admin</title>
  <style>
    table { border-collapse: collapse; width: 100%; }
    th, td { border: 1px solid #ccc; padding: 6px; text-align: left; }
    .controls { margin: 10px 0; }
    .movie-form { margin-bottom: 10px; padding:8px; border:1px solid #ddd; }
    .small { font-size: 0.9em; color:#666; }
  </style>
  <script>
    function addMore() {
      const container = document.getElementById('bulk-add-container');
      const idx = container.children.length;
      const div = document.createElement('div');
      div.className = 'movie-form';
      div.innerHTML = `
        <label>Title: <input name="title_${idx}" required></label><br>
        <label>Filename: <input name="filename_${idx}"></label><br>
        <label>File URL / ID: <input name="file_url_${idx}" required></label><br>
        <button type="button" onclick="this.parentNode.remove()">Remove</button>
      `;
      container.appendChild(div);
    }
    function prepareBulkAdd() {
      const container = document.getElementById('bulk-add-container');
      const forms = container.children;
      const total = forms.length;
      document.getElementById('bulk_count').value = total;
      return true;
    }
    function toggleAll(source) {
      const checks = document.getElementsByName('selected[]');
      for (let i=0;i<checks.length;i++) checks[i].checked = source.checked;
    }
  </script>
</head>
<body>
  <h2>🎜 Sara Bot Admin Panel</h2>
  <p class="small">Logged in as admin. <a href="{{ url_for('admin_logout') }}">Logout</a></p>

  <h3>Movies (Total: {{ count }})</h3>
  <form method="POST" action="{{ url_for('admin_bulk_delete') }}">
    <div class="controls">
      <button type="submit" onclick="return confirm('Delete selected movies?')">Delete Selected</button>
      <label><input type="checkbox" onclick="toggleAll(this)"> Select All</label>
    </div>
    <table>
      <tr><th></th><th>#</th><th>Title</th><th>Filename</th><th>URL / ID</th><th>Actions</th></tr>
      {% for movie in movies %}
      <tr>
        <td><input type="checkbox" name="selected[]" value="{{ loop.index0 }}"></td>
        <td>{{ loop.index0 }}</td>
        <td>{{ movie.title }}</td>
        <td>{{ movie.filename }}</td>
        <td style="max-width:400px; word-break:break-all">{{ movie.file_url }}</td>
        <td>
          <a href="{{ url_for('admin_edit_movie', index=loop.index0) }}">Edit</a> |
          <a href="{{ url_for('admin_delete_movie', index=loop.index0) }}?password={{ session.get('pwd_token') }}">Delete</a>
        </td>
      </tr>
      {% endfor %}
    </table>
  </form>

  <hr>
  <h3>Bulk Add Movies</h3>
  <form method="POST" action="{{ url_for('admin_bulk_add') }}" onsubmit="return prepareBulkAdd();">
    <input type="hidden" name="password" value="{{ session.get('pwd_token') }}">
    <input type="hidden" id="bulk_count" name="bulk_count" value="0">
    <div id="bulk-add-container">
      <div class="movie-form">
        <label>Title: <input name="title_0" required></label><br>
        <label>Filename: <input name="filename_0"></label><br>
        <label>File URL / ID: <input name="file_url_0" required></label><br>
      </div>
    </div>
    <button type="button" onclick="addMore()">Add More</button>
    <button type="submit">Add All</button>
  </form>

  <hr>
  <p class="small">Tip: File URL can be Telegram file_id or direct download link. New entries will be appended to <code>movie_list.json</code>.</p>
</body>
</html>
'''

edit_template = '''
<!doctype html>
<html>
<head><title>Edit Movie</title></head>
<body>
  <h2>Edit Movie #{{ index }}</h2>
  <form method="POST">
    <input type="hidden" name="password" value="{{ session.get('pwd_token') }}">
    Title: <input name="title" value="{{ movie.title }}" required><br>
    Filename: <input name="filename" value="{{ movie.filename }}"><br>
    File URL: <input name="file_url" value="{{ movie.file_url }}"><br>
    <button type="submit">Save</button>
  </form>
  <p><a href="{{ url_for('admin_login') }}">Back to dashboard</a></p>
</body>
</html>
'''

def require_login():
    return session.get("logged", False)

@flask_app.route("/admin", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        pwd = request.form.get("password")
        if pwd == ADMIN_PASSWORD:
            session.permanent = True
            session["logged"] = True
            session["pwd_token"] = pwd
            data = load_movies_local()
            return render_template_string(dashboard_template, movies=data, count=len(data), session=session)
        return render_template_string(login_template, error="Wrong password!")
    else:
        if require_login():
            data = load_movies_local()
            return render_template_string(dashboard_template, movies=data, count=len(data), session=session)
        return render_template_string(login_template, error=None)

@flask_app.route("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for('admin_login'))

@flask_app.route("/admin/edit/<int:index>", methods=["GET", "POST"])
def admin_edit_movie(index):
    if not require_login():
        return redirect(url_for('admin_login'))
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
        return redirect(url_for('admin_login'))
    return render_template_string(edit_template, movie=data[index], index=index, session=session)

@flask_app.route("/admin/delete/<int:index>")
def admin_delete_movie(index):
    if not require_login():
        return redirect(url_for('admin_login'))
    data = load_movies_local()
    if index >= len(data) or index < 0:
        return "❌ Invalid index"
    del data[index]
    save_movies_local(data)
    return redirect(url_for('admin_login'))

@flask_app.route("/admin/bulk_delete", methods=["POST"])
def admin_bulk_delete():
    if not require_login():
        return redirect(url_for('admin_login'))
    selected = request.form.getlist('selected[]')
    if not selected:
        return redirect(url_for('admin_login'))
    idxs = sorted([int(x) for x in selected], reverse=True)
    data = load_movies_local()
    for idx in idxs:
        if 0 <= idx < len(data):
            del data[idx]
    save_movies_local(data)
    return redirect(url_for('admin_login'))

@flask_app.route("/admin/bulk_add", methods=["POST"])
def admin_bulk_add():
    if not require_login():
        return redirect(url_for('admin_login'))
    try:
        count = int(request.form.get('bulk_count', '0'))
    except:
        count = 0
    if count <= 0:
        count = 0
        for key in request.form.keys():
            if key.startswith('title_'):
                count += 1
    if count == 0:
        return redirect(url_for('admin_login'))
    data = load_movies_local()
    added = 0
    for i in range(count):
        title_key = f"title_{i}"
        file_key = f"file_url_{i}"
        fname_key = f"filename_{i}"
        title = request.form.get(title_key)
        file_url = request.form.get(file_key)
        filename = request.form.get(fname_key, "")
        if not title or not file_url:
            continue
        if any(m.get("file_url") == file_url for m in data):
            continue
        data.append({"title": title.strip(), "filename": filename or "", "file_url": file_url})
        added += 1
    save_movies_local(data)
    return redirect(url_for('admin_login'))

# -------------------------
# Flask Routes - Misc
# -------------------------
@flask_app.route("/")
def home():
    return "✅ Sara bot is alive! (Flask running)"

@flask_app.route("/movies")
def get_movies():
    data = load_movies_local()
    return {"count": len(data), "movies": data}

# -------------------------
# Bot Conversation Triggers
# -------------------------
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

# -------------------------
# User message history to prevent spam replies
# -------------------------
user_message_history = {}

# -------------------------
# Bot Handlers
# -------------------------
@app.on_message(filters.command("start"))
async def start(client, message):
    user = message.from_user.first_name if message.from_user else "Friend"
    await message.reply_text(
        f"👋 Namaste {user} ji!\nMain *Sara* hoon — aapki movie wali dost 💁‍♀️🎥\nBas movie ka naam bhejiye... main dhoond kar de doongi!\n\n📺 Hamara channel invite link: {CHANNEL_INVITE_LINK}",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("📺 Channel Join Karein", url=CHANNEL_INVITE_LINK)]]
        ),
        parse_mode="markdown"
    )

@app.on_message((filters.document | filters.video) & filters.private)
async def handle_file(client, message):
    # Use the caption or text as title
    title = message.caption or message.text or "Untitled"
    filename = message.document.file_name if message.document else message.video.file_name if message.video else ""
    # Save movie using local json add function
    added = add_movie_to_json(title, message.id, filename=filename)
    if added:
        await message.reply_text("✅ Movie JSON में save हो गई 📁")
    else:
        await message.reply_text("⚠️ Movie पहले से मौजूद है।")

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
    # Simple spam filter - max 3 times per text
    if user_msgs[text] > 3:
        return

    # Check conversation triggers only in private chat
    if message.chat.type == "private":
        for keyword, reply in conversation_triggers:
            if keyword in text:
                await message.reply_text(reply)
                return

    # Avoid common spam/search terms
    stop_words = {
        "facebook", "instagram", "youtube", "tiktok", "whatsapp", "google", "telegram",
        "game", "gaming", "terabox", "feedback", "dubbed", "emoji", "streaming", "link",
        "romance", "romantic", "status", "application", "install", "android", "click",
        "language", "platform", "channel", "online", "comedy", "movies", "movie", "bhai",
        "bhejo", "bro", "hindi", "english", "south"
    }
    if any(w in text for w in stop_words):
        return

    try:
        data = load_movies_local()
        best_match = None
        best_score = 0
        for movie in data:
            score = fuzz.partial_ratio(text, movie["title"].lower())
            if score > best_score and score > 70:
                best_score = score
                best_match = movie

        if best_match:
            # Forward message by msg_id or send file_url
            if best_match.get("msg_id", 0) > 0:
                await client.forward_messages(chat_id, CHANNEL_ID, best_match["msg_id"])
            elif best_match.get("file_url"):
                await client.send_message(chat_id, f"यहाँ आपकी movie है: {best_match['file_url']}")
            else:
                await client.send_message(chat_id, "माफ़ कीजिये, movie नहीं मिली।")
            return
    except Exception as e:
        print("Search Error in JSON:", e)

    try:
        async for msg in app.get_chat_history(CHANNEL_ID, limit=1000):
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
            text=f"🎀 Hi {name} ji! Welcome to our group 🎥\nMain *Sara* hoon — yahan ki movie wali dost 💁‍♀️\nKoi movie chahiye toh bas naam boliye ❤️",
            parse_mode="markdown"
        )

# -------------------------
# Flask app background thread
# -------------------------
def run_flask():
    flask_app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)

threading.Thread(target=run_flask).start()

# -------------------------
# Start Bot
# -------------------------
if __name__ == "__main__":
    app.run()
