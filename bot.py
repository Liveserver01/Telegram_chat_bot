# sara_bot_fixed.py
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ChatMemberUpdated
from flask import Flask, request, render_template_string, redirect, session, url_for
import threading
import os
import json
import requests
import re
from fuzzywuzzy import fuzz
from datetime import timedelta

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

# Flask secret key for sessions
FLASK_SECRET_KEY = os.environ.get("FLASK_SECRET_KEY", "1b2e473094dc56a9ba54522c332600b1")

# -------------------------
# Initialize clients
# -------------------------
app = Client("sara_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
flask_app = Flask(__name__)
flask_app.secret_key = FLASK_SECRET_KEY
# Session lifetime: optional, e.g., 8 hours
flask_app.permanent_session_lifetime = timedelta(hours=8)

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
    # Ensure directory exists if needed
    with open(LOCAL_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

# -------------------------
# Admin templates (updated)
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
      // count forms
      const container = document.getElementById('bulk-add-container');
      const forms = container.children;
      const total = forms.length;
      // mark total
      document.getElementById('bulk_count').value = total;
      // nothing else; server will read form fields by index
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
      <!-- initial one form -->
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

# -------------------------
# Flask routes (admin)
# -------------------------
def require_login():
    return session.get("logged", False)

@flask_app.route("/admin", methods=["GET", "POST"])
def admin_login():
    # GET -> show dashboard if logged, else login form
    if request.method == "POST":
        pwd = request.form.get("password")
        if pwd == ADMIN_PASSWORD:
            session.permanent = True
            session["logged"] = True
            # store a short-lived token in session to include in links/forms
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
        # optional: check session pwd_token if you want
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
    # Single delete via link (keeps backward compatibility)
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
    # indices are strings; convert to ints and sort descending to delete safely
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
    # if count is 0, try to detect number of provided title_* keys
    if count <= 0:
        # find keys like title_0, title_1...
        count = 0
        for key in request.form.keys():
            if key.startswith('title_'):
                count += 1
    if count == 0:
        # maybe single default form fields present as title_0 etc (handle minimal case)
        # if still none, just redirect
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
        # duplicate check by file_url
        if any(m.get("file_url") == file_url for m in data):
            continue
        data.append({"title": title.strip(), "filename": filename or "", "file_url": file_url})
        added += 1
    save_movies_local(data)
    return redirect(url_for('admin_login'))

# -------------------------
# Other Flask routes (status)
# -------------------------
@flask_app.route("/")
def home():
    return "✅ Sara is alive via Render & GitHub!"

@flask_app.route("/movies")
def get_movies():
    data = load_movies_from_github()
    return {"count": len(data), "movies": data}

# Run Flask in a separate daemon thread so Pyrogram can run in main thread
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
    ("kya dekh rahe ho", "Main toh sirf movie files dekh rahi ho 😄")
]

# -------------------------
# Auto-save movie from channel
# -----------------------

@app.on_message(filters.channel & filters.photo)
@app.on_message(filters.photo & filters.private)
async def save_movie_poster(client, message):
    try:
        caption = message.caption or ""
        title, download_link = parse_caption(caption)
        if not title or not download_link:
            print("Title or download link missing, skipping")
            return

        movies = load_movies_local()
        # Duplicate check on download link
        if any(m.get("file_url") == download_link for m in movies):
            print("Movie already exists, skipping:", title)
            return

        movies.append({
            "title": title,
            "filename": "",  # optional
            "file_url": download_link
        })
        save_movies_local(movies)
        print(f"✅ Added movie: {title}")

    except Exception as e:
        print("Error saving movie poster:", e)

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



