from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask, request, render_template_string, redirect, session, url_for
import threading
import os
import json
from fuzzywuzzy import fuzz
import requests
from datetime import timedelta
from base64 import b64encode

# ------------ Environment Variables ------------
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")
API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = int(os.environ.get("CHANNEL_ID"))  # Ex: -1001234567890
FLASK_SECRET_KEY = os.environ.get("FLASK_SECRET_KEY", "defaultsecret")
CHANNEL_INVITE_LINK = os.environ.get("CHANNEL_INVITE_LINK", "")

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
GITHUB_REPO = os.environ.get("GITHUB_REPO")  # username/reponame
GITHUB_FILE_PATH = os.environ.get("GITHUB_FILE_PATH", "movie_list.json")
GITHUB_BRANCH = os.environ.get("GITHUB_BRANCH", "main")

LOCAL_JSON_PATH = "movie_list.json"

# ------------ Flask Setup ------------
flask_app = Flask(__name__)
flask_app.secret_key = FLASK_SECRET_KEY
flask_app.permanent_session_lifetime = timedelta(hours=8)

# ------------ Pyrogram Setup ------------
app = Client("sara_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# ------------ Thread Lock ------------
json_lock = threading.Lock()

# ------------ JSON Helpers ------------

def load_movies_local():
    try:
        with open(LOCAL_JSON_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def save_movies_local(data):
    with open(LOCAL_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

# ------------ GitHub Integration ------------

def github_get_file_sha():
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_FILE_PATH}?ref={GITHUB_BRANCH}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        return r.json()['sha']
    else:
        print("GitHub get SHA failed:", r.text)
        return None

def upload_json_to_github(data):
    if not (GITHUB_TOKEN and GITHUB_REPO):
        print("GitHub credentials missing; skipping upload.")
        return False
    sha = github_get_file_sha()
    if sha is None:
        print("No SHA found, cannot update GitHub file.")
        return False
    content_str = json.dumps(data, indent=4, ensure_ascii=False)
    content_b64 = b64encode(content_str.encode('utf-8')).decode('utf-8')
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_FILE_PATH}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    payload = {
        "message": "Update movie_list.json via bot",
        "content": content_b64,
        "branch": GITHUB_BRANCH,
        "sha": sha
    }
    r = requests.put(url, json=payload, headers=headers)
    if r.status_code in [200, 201]:
        print("movie_list.json updated on GitHub successfully.")
        return True
    else:
        print("GitHub upload failed:", r.text)
        return False

# ------------ Add Movie ------------

def add_movie_to_json(title, msg_id=None, filename=None, file_url=None):
    with json_lock:
        data = load_movies_local()
        # Duplicate check
        if msg_id and any(m.get("msg_id") == msg_id for m in data):
            print(f"Duplicate msg_id {msg_id}, skipping.")
            return False
        if file_url and any(m.get("file_url") == file_url for m in data):
            print(f"Duplicate file_url {file_url}, skipping.")
            return False

        movie = {
            "title": title.strip(),
            "msg_id": msg_id or 0,
            "filename": filename or "",
            "file_url": file_url or ""
        }
        data.append(movie)
        save_movies_local(data)
        upload_json_to_github(data)
        print(f"Added movie: {title}")
        return True

# ------------ Flask Templates (simple versions) ------------

login_template = '''
<!doctype html><title>Admin Login</title>
<h2>Admin Login</h2>
{% if error %}<p style="color:red;">{{ error }}</p>{% endif %}
<form method="post">
  <input name="password" type="password" placeholder="Password" required>
  <button type="submit">Login</button>
</form>
'''

dashboard_template = '''
<!doctype html><title>Dashboard</title>
<h2>Movie List ({{ count }})</h2>
<a href="{{ url_for('admin_logout') }}">Logout</a>
<table border=1>
<tr><th>Index</th><th>Title</th><th>Filename</th><th>Msg ID</th><th>Actions</th></tr>
{% for i,movie in enumerate(movies) %}
<tr>
  <td>{{ i }}</td>
  <td>{{ movie.title }}</td>
  <td>{{ movie.filename }}</td>
  <td>{{ movie.msg_id }}</td>
  <td>
    <a href="{{ url_for('admin_edit_movie', index=i) }}">Edit</a> | 
    <a href="{{ url_for('admin_delete_movie', index=i) }}" onclick="return confirm('Delete?')">Delete</a>
  </td>
</tr>
{% endfor %}
</table>
'''

edit_template = '''
<!doctype html><title>Edit Movie</title>
<h2>Edit Movie #{{ index }}</h2>
<form method="post">
  Title:<br><input type="text" name="title" value="{{ movie.title }}" required><br>
  Filename:<br><input type="text" name="filename" value="{{ movie.filename }}"><br>
  File URL:<br><input type="text" name="file_url" value="{{ movie.file_url }}"><br>
  <button type="submit">Save</button>
</form>
<a href="{{ url_for('admin_login') }}">Back</a>
'''

# ------------ Flask Routes ------------

def require_login():
    return session.get("logged", False)

@flask_app.route("/admin", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        if request.form.get("password") == ADMIN_PASSWORD:
            session.permanent = True
            session["logged"] = True
            data = load_movies_local()
            return render_template_string(dashboard_template, movies=data, count=len(data))
        else:
            return render_template_string(login_template, error="गलत पासवर्ड!")
    else:
        if require_login():
            data = load_movies_local()
            return render_template_string(dashboard_template, movies=data, count=len(data))
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
    if index < 0 or index >= len(data):
        return "Invalid index"
    if request.method == "POST":
        data[index]["title"] = request.form["title"].strip()
        data[index]["filename"] = request.form.get("filename", "")
        data[index]["file_url"] = request.form.get("file_url", "")
        save_movies_local(data)
        upload_json_to_github(data)
        return redirect(url_for('admin_login'))
    return render_template_string(edit_template, movie=data[index], index=index)

@flask_app.route("/admin/delete/<int:index>")
def admin_delete_movie(index):
    if not require_login():
        return redirect(url_for('admin_login'))
    data = load_movies_local()
    if 0 <= index < len(data):
        data.pop(index)
        save_movies_local(data)
        upload_json_to_github(data)
    return redirect(url_for('admin_login'))

@flask_app.route("/")
def home():
    return "✅ Sara bot Flask server running."

@flask_app.route("/movies")
def get_movies():
    data = load_movies_local()
    return {"count": len(data), "movies": data}

# ------------ Bot Conversation triggers ------------

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

# ------------ User message history ------------

user_message_history = {}

# ------------ Bot Handlers ------------

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
    title = message.caption or "Untitled Movie"
    filename = ""
    if message.document:
        filename = message.document.file_name
    elif message.video:
        filename = message.video.file_name or ""
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

    # Spam prevent
    user_msgs = user_message_history.setdefault(user_id, {})
    user_msgs[text] = user_msgs.get(text, 0) + 1
    if user_msgs[text] > 3:
        return

    if message.chat.type == "private":
        for keyword, reply in conversation_triggers:
            if keyword in text:
                await message.reply_text(reply)
                return

    # Search in local JSON
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
            if best_match.get("msg_id", 0) > 0:
                await client.forward_messages(chat_id, CHANNEL_ID, best_match["msg_id"])
            elif best_match.get("file_url"):
                await client.send_message(chat_id, f"यहाँ आपकी movie है: {best_match['file_url']}")
            else:
                await client.send_message(chat_id, "माफ़ कीजिये, movie नहीं मिली।")
            return
    except Exception as e:
        print("Search Error in JSON:", e)

    # Search in channel recent messages
    try:
        async for msg in app.get_chat_history(CHANNEL_ID, limit=1000):
            if msg.caption and fuzz.partial_ratio(text, msg.caption.lower()) > 75:
                await msg.forward(chat_id)
                return
    except Exception as e:
        print("Search Error in Channel:", e)

    # Default reply for private chat
    if message.chat.type == "private":
        if any(w in text for w in ["upload", "movie chahiye", "please", "req"]):
            await message.reply_text("🍿 Ok ji! Aapki request note kar li, jaldi movie bhejti hoon.")
            return
        await message.reply_text("क्षमा करें, मुझे आपकी movie समझ नहीं आई। कृपया सही नाम भेजिए।")

# ------------ Run Flask and Pyrogram ------------

def run_flask():
    flask_app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

if __name__ == "__main__":
    import threading
    threading.Thread(target=run_flask).start()
    app.run()
