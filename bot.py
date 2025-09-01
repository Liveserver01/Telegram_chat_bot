# sara_bot_fixed_full.py
import os
import re
import json
import time
import logging
import threading
import asyncio
from base64 import b64encode
from datetime import timedelta
from typing import List, Dict, Tuple, Set

import requests
from urllib.parse import quote_plus
from fuzzywuzzy import fuzz
from flask import Flask, request, render_template_string, redirect, session, url_for

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message

# -------------------------
# Config / Env
# -------------------------
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")
if not ADMIN_PASSWORD:
    raise ValueError("ADMIN_PASSWORD required")

_try_api_id = os.environ.get("API_ID")
_try_channel_id = os.environ.get("CHANNEL_ID")
if not _try_api_id or not _try_channel_id:
    raise ValueError("API_ID and CHANNEL_ID required")

API_ID = int(_try_api_id)
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = int(_try_channel_id)  # -100...
FLASK_SECRET_KEY = os.environ.get("FLASK_SECRET_KEY", "change_me_secret")
CHANNEL_INVITE_LINK = os.environ.get("CHANNEL_INVITE_LINK", "https://t.me/+qYUn4HuS7hRiNTNl")

# NEW: OMDb API for legal posters
OMDB_API_KEY = os.environ.get("OMDB_API_KEY", "").strip()

# GitHub (optional) - if not set, uploads skipped
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
GITHUB_REPO = os.environ.get("GITHUB_REPO")  # username/repo
GITHUB_FILE_PATH = os.environ.get("GITHUB_FILE_PATH", "movie_list.json")
GITHUB_BRANCH = os.environ.get("GITHUB_BRANCH", "main")

LOCAL_JSON_PATH = "movie_list.json"
SETTINGS_PATH = "settings.json"
LOG_FILE = "bot.log"

# -------------------------
# Logger बनाओ
# -------------------------
logger = logging.getLogger("sara_bot")
logger.setLevel(logging.INFO)

# 1) File Handler
fh = logging.FileHandler(LOG_FILE, mode="a", encoding="utf-8")
fh.setLevel(logging.INFO)
fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))

# 2) Console Handler
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
ch.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))

# Duplicate handlers से बचने के लिए
if not logger.handlers:
    logger.addHandler(fh)
    logger.addHandler(ch)

# -------------------------
# Test log
# -------------------------
logger.info("Starting Sara bot...")
logger.warning("Warning test message...")
logger.error("Error test message...")

# -------------------------
# Flask app
# -------------------------
flask_app = Flask(__name__)
flask_app.secret_key = FLASK_SECRET_KEY
flask_app.permanent_session_lifetime = timedelta(hours=8)

# -------------------------
# Pyrogram bot
# -------------------------
app = Client("sara_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# -------------------------
# Thread lock
# -------------------------
json_lock = threading.Lock()

# -------------------------
# Helpers: load/save JSON & settings
# -------------------------
def load_movies_local():
    try:
        with open(LOCAL_JSON_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return []
    except Exception:
        logger.exception("load_movies_local error")
        return []

def save_movies_local(data):
    try:
        with open(LOCAL_JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception:
        logger.exception("save_movies_local error")

def load_settings():
    default = {"auto_forward": False}
    try:
        if os.path.exists(SETTINGS_PATH):
            with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                s = json.load(f)
                if "auto_forward" not in s:
                    s["auto_forward"] = False
                return s
        else:
            return default
    except Exception:
        logger.exception("load_settings error")
        return default

def save_settings(settings):
    try:
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=4, ensure_ascii=False)
    except Exception:
        logger.exception("save_settings error")

# -------------------------
# GitHub upload (optional)
# -------------------------
def github_get_file_sha():
    if not (GITHUB_TOKEN and GITHUB_REPO):
        return None
    try:
        url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_FILE_PATH}?ref={GITHUB_BRANCH}"
        headers = {"Authorization": f"token {GITHUB_TOKEN}"}
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            return r.json().get("sha")
        logger.warning("GitHub get SHA failed: %s %s", r.status_code, r.text[:200])
    except Exception:
        logger.exception("github_get_file_sha error")
    return None

def upload_json_to_github(data):
    if not (GITHUB_TOKEN and GITHUB_REPO):
        logger.info("GitHub not configured — skipping upload")
        return False
    try:
        sha = github_get_file_sha()
        content_str = json.dumps(data, indent=4, ensure_ascii=False)
        content_b64 = b64encode(content_str.encode("utf-8")).decode("utf-8")
        url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_FILE_PATH}"
        headers = {"Authorization": f"token {GITHUB_TOKEN}"}
        payload = {"message": "Update movie_list.json via bot", "content": content_b64, "branch": GITHUB_BRANCH}
        if sha:
            payload["sha"] = sha
        r = requests.put(url, json=payload, headers=headers, timeout=15)
        if r.status_code in (200, 201):
            logger.info("Uploaded movie_list.json to GitHub")
            return True
        logger.warning("GitHub upload failed: %s %s", r.status_code, r.text[:300])
    except Exception:
        logger.exception("upload_json_to_github error")
    return False

# -------------------------
# Add movie helper
# -------------------------
def add_movie_to_json(title, msg_id=None, filename=None, file_url=None):
    with json_lock:
        data = load_movies_local()
        title = (title or "Untitled").strip()
        if msg_id and any(int(m.get("msg_id", 0)) == int(msg_id) and m.get("msg_id", 0) != 0 for m in data):
            logger.info("Duplicate msg_id %s, skipping", msg_id)
            return False
        if file_url and any(m.get("file_url") == file_url for m in data if m.get("file_url")):
            logger.info("Duplicate file_url %s, skipping", file_url)
            return False
        entry = {"title": title, "msg_id": int(msg_id) if msg_id else 0, "filename": filename or "", "file_url": file_url or ""}
        data.append(entry)
        save_movies_local(data)
        uploaded = upload_json_to_github(data)
        logger.info("Added movie: %s msg_id=%s file_url=%s github=%s", title, msg_id, file_url, uploaded)
        return True

# -------------------------
# Caption parse util
# -------------------------
def parse_caption(caption_text):
    if not caption_text:
        return None, None
    lines = caption_text.splitlines()
    title = None
    for line in lines:
        s = line.strip()
        if not s:
            continue
        if s.startswith("---") or s.startswith("📌") or s.lower().startswith("feedback") or s.lower().startswith("download"):
            continue
        title = s
        break
    urls = re.findall(r'https?://\S+', caption_text)
    return title, (urls[0] if urls else None)

# -------------------------
# Text Normalization & Matching
# -------------------------
STOPWORDS = {
    "the","and","a","an","of","in","on","at","to","for","by","with","from","part","pt","episode","ep","season","s","disk","disc","cd","movie","film","full","hd","hq","1080p","720p"
}

def normalize_title(s: str) -> str:
    s = (s or "").lower()
    s = re.sub(r"[\[\]\(\)\{\}\|:_\-\.]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def token_words(s: str) -> List[str]:
    s = normalize_title(s)
    words = re.findall(r"[a-z0-9]+", s)
    return [w for w in words if w not in STOPWORDS]

def base_series_title(s: str) -> str:
    s = normalize_title(s)
    s = re.sub(r"\b(part|pt|episode|ep|season|s)\s*\d+\b", "", s)
    s = re.sub(r"\b\d{4}\b", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def is_exact_or_5words_match(query: str, title: str) -> Tuple[bool, int]:
    qn = normalize_title(query)
    tn = normalize_title(title)
    if not qn or not tn:
        return False, 0
    if qn == tn:
        return True, 999
    qset = set(token_words(qn))
    tset = set(token_words(tn))
    overlap = len(qset & tset)
    return (overlap >= 5), overlap

# -------------------------
# OMDb Poster (LEGAL)
# -------------------------
def get_poster_url_omdb(title: str) -> str:
    if not OMDB_API_KEY:
        return ""
    try:
        # try exact title first
        url = f"https://www.omdbapi.com/?apikey={OMDB_API_KEY}&t={quote_plus(title)}"
        r = requests.get(url, timeout=8)
        if r.status_code == 200:
            data = r.json()
            poster = data.get("Poster", "N/A")
            if poster and poster != "N/A":
                return poster
        # fallback: search
        url = f"https://www.omdbapi.com/?apikey={OMDB_API_KEY}&s={quote_plus(title)}"
        r = requests.get(url, timeout=8)
        if r.status_code == 200:
            data = r.json()
            results = data.get("Search", []) or []
            # try to choose best match using fuzzy on Title
            best = None
            best_score = 0
            for it in results:
                t = it.get("Title", "")
                score = fuzz.token_set_ratio(title.lower(), t.lower())
                if score > best_score:
                    best_score = score
                    best = it
            if best:
                p = best.get("Poster", "")
                if p and p != "N/A":
                    return p
    except Exception:
        logger.exception("OMDb poster fetch failed")
    return ""

# -------------------------
# Flask templates
# -------------------------
login_template = """
<!doctype html><title>Admin Login</title>
<h2>Admin Login</h2>
{% if error %}<p style="color:red">{{ error }}</p>{% endif %}
<form method="post">
  <input name="password" type="password" placeholder="Password" required>
  <button type="submit">Login</button>
</form>
"""

dashboard_template = """
<!doctype html><title>Dashboard</title>
<h2>Movie List ({{ count }})</h2>
<p>
  <a href="{{ url_for('admin_logout') }}">Logout</a> |
  Auto-forward: <b>{{ 'ON' if settings.auto_forward else 'OFF' }}</b>
  <form method="post" action="{{ url_for('toggle_forward') }}" style="display:inline">
    <input type="hidden" name="password" value="{{ session.get('pwd_token') }}">
    <button type="submit">{{ 'Disable' if settings.auto_forward else 'Enable' }} Auto-forward</button>
  </form>
</p>

<h3>Bulk Add (one per line: title|file_url|filename(optional))</h3>
<form method="post" action="{{ url_for('admin_bulk_add') }}">
  <input type="hidden" name="password" value="{{ session.get('pwd_token') }}">
  <textarea name="bulk_data" rows="6" cols="80" placeholder="Movie Title | https://link.or.file_id | filename.mkv"></textarea><br>
  <button type="submit">Add Bulk</button>
</form>

<h3>Bulk Delete (indexes)</h3>
<form method="post" action="{{ url_for('admin_bulk_delete') }}">
  <input type="hidden" name="password" value="{{ session.get('pwd_token') }}">
  <input name="bulk_delete_indexes" placeholder="e.g. 0,2,5-7"><button type="submit">Delete</button>
</form>

<table border=1 cellpadding=6>
<tr><th>#</th><th>Title</th><th>Filename</th><th>Msg ID</th><th>File URL</th><th>Actions</th></tr>
{% for movie in movies %}
<tr>
  <td>{{ loop.index0 }}</td>
  <td>{{ movie.title }}</td>
  <td>{{ movie.filename }}</td>
  <td>{{ movie.msg_id }}</td>
  <td style="max-width:300px;word-break:break-all">{{ movie.file_url }}</td>
  <td>
    <a href="{{ url_for('admin_edit_movie', index=loop.index0) }}">Edit</a> |
    <a href="{{ url_for('admin_delete_movie', index=loop.index0) }}?password={{ session.get('pwd_token') }}" onclick="return confirm('Delete?')">Delete</a>
  </td>
</tr>
{% endfor %}
</table>
"""

edit_template = """
<!doctype html><title>Edit Movie</title>
<h2>Edit Movie #{{ index }}</h2>
<form method="post">
  <input type="hidden" name="password" value="{{ session.get('pwd_token') }}">
  Title:<br><input type="text" name="title" value="{{ movie.title }}" required><br>
  Filename:<br><input type="text" name="filename" value="{{ movie.filename }}"><br>
  File URL:<br><input type="text" name="file_url" value="{{ movie.file_url }}"><br>
  <button type="submit">Save</button>
</form>
<a href="{{ url_for('admin_login') }}">Back</a>
"""

# -------------------------
# Flask routes
# -------------------------
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
            movies = load_movies_local()
            settings = load_settings()
            return render_template_string(dashboard_template, movies=movies, count=len(movies), session=session, settings=settings)
        else:
            return render_template_string(login_template, error="Wrong password!")
    else:
        if require_login():
            movies = load_movies_local()
            settings = load_settings()
            return render_template_string(dashboard_template, movies=movies, count=len(movies), session=session, settings=settings)
        return render_template_string(login_template, error=None)

@flask_app.route("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("admin_login"))

@flask_app.route("/admin/edit/<int:index>", methods=["GET", "POST"])
def admin_edit_movie(index):
    if not require_login():
        return redirect(url_for("admin_login"))
    data = load_movies_local()
    if index < 0 or index >= len(data):
        return "Invalid index"
    if request.method == "POST":
        data[index]["title"] = request.form.get("title", data[index].get("title","")).strip()
        data[index]["filename"] = request.form.get("filename", data[index].get("filename",""))
        data[index]["file_url"] = request.form.get("file_url", data[index].get("file_url",""))
        save_movies_local(data)
        upload_json_to_github(data)
        logger.info("Admin edited movie index=%s", index)
        return redirect(url_for("admin_login"))
    return render_template_string(edit_template, movie=data[index], index=index)

@flask_app.route("/admin/delete/<int:index>")
def admin_delete_movie(index):
    pwd = request.args.get("password")
    if pwd != session.get("pwd_token"):
        return redirect(url_for("admin_login"))
    data = load_movies_local()
    if 0 <= index < len(data):
        removed = data.pop(index)
        save_movies_local(data)
        upload_json_to_github(data)
        logger.info("Admin deleted movie index=%s title=%s", index, removed.get("title"))
    return redirect(url_for("admin_login"))

@flask_app.route("/admin/bulk_add", methods=["POST"])
def admin_bulk_add():
    if not require_login():
        return redirect(url_for("admin_login"))
    bulk = request.form.get("bulk_data", "").strip()
    if not bulk:
        return redirect(url_for("admin_login"))
    data = load_movies_local()
    added = 0
    for line in bulk.splitlines():
        parts = [p.strip() for p in line.split("|")]
        if len(parts) >= 2:
            title = parts[0]
            file_url = parts[1]
            filename = parts[2] if len(parts) >= 3 else ""
            if any(m.get("file_url") == file_url for m in data):
                continue
            data.append({"title": title, "filename": filename, "file_url": file_url, "msg_id": 0})
            added += 1
    save_movies_local(data)
    upload_json_to_github(data)
    logger.info("Admin bulk added %d movies", added)
    return redirect(url_for("admin_login"))

def parse_indexes_spec(spec: str):
    rv = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            try:
                a,b = part.split("-",1)
                a=int(a); b=int(b)
                for i in range(a,b+1):
                    rv.add(i)
            except:
                continue
        else:
            try:
                rv.add(int(part))
            except:
                continue
    return sorted(rv)

@flask_app.route("/admin/bulk_delete", methods=["POST"])
def admin_bulk_delete():
    if not require_login():
        return redirect(url_for("admin_login"))
    spec = request.form.get("bulk_delete_indexes","").strip()
    if not spec:
        return redirect(url_for("admin_login"))
    idxs = parse_indexes_spec(spec)
    data = load_movies_local()
    deleted = 0
    for idx in sorted(idxs, reverse=True):
        if 0 <= idx < len(data):
            removed = data.pop(idx)
            deleted += 1
            logger.info("Admin bulk deleted idx=%s title=%s", idx, removed.get("title"))
    save_movies_local(data)
    upload_json_to_github(data)
    return redirect(url_for("admin_login"))

@flask_app.route("/toggle_forward", methods=["POST"])
def toggle_forward():
    if not require_login():
        return redirect(url_for("admin_login"))
    s = load_settings()
    s["auto_forward"] = not bool(s.get("auto_forward", False))
    save_settings(s)
    logger.info("Auto-forward set to %s by admin", s["auto_forward"])
    return redirect(url_for("admin_login"))

@flask_app.route("/")
def home():
    return "✅ Sara bot Flask server running."

@flask_app.route("/movies")
def get_movies():
    data = load_movies_local()
    return {"count": len(data), "movies": data}

# -------------------------
# Bot handlers
# -------------------------
conversation_triggers = [
    ("good night", "Good night ji! Sweet dreams 💤 ~ Apki Sara"),
    ("good morning", "Good morning! Naya din, nayi movie 🎬"),
    ("thank", "Arey koi baat nahi ji! ❤️"),
    ("love you", "Main bhi aapko movie ke saath saath pyaar karti hoon 😄"),
    ("hello", "Hello ji! Kaise ho aap?"),
    ("hi", "Hi hi! Sara yahan hai aapke liye."),
    ("kya kar rahe ho", "Bas aapke liye movies search kar rahi hoon."),
    ("bored", "Toh ek dhamakedar movie deखते हैं!"),
    ("kaisi ho", "Main acchi hoon! Aap sunao?"),
    ("kya haal hai", "Sab badiya! Aapke liye movie ready hai kya?"),
    ("mood off", "Mood thik karte hain ek zabardast movie से!"),
    ("party", "Movie + Popcorn = Best Party!"),
    ("movie batao", "Aap bas naam batao, main bhejti hoon!"),
    ("acha", "Bilkul sahi! Ab movie ka naam batao."),
    ("ok", "Chaliye fir! Movie ka naam likhiye."),
    ("arey", "Kya hua ji? Movie chahiye kya?"),
    ("haan", "Toh movie name likho fir!"),
    ("nahi", "Thik hai fir jab chahiye ho toh zarur batana."),
    ("kahan se ho", "Main Telegram ki duniya se hoon, Sara naam hai mera!"),
    ("khana khaya", "Main bot hoon, movie meri खुराक है 😋"),
    ("kya dekh rahe ho", "Main toh sirf movie files देख रही हूँ 😄"),
    ("kya kar rahi ho", "Bas aapके लिए movies search कर रही हूँ."),
]

user_message_history = {}

@app.on_message(filters.command("start"))
async def start(client, message):
    user = message.from_user.first_name or "User"
    try:
        if CHANNEL_INVITE_LINK:
            channel_button_url = CHANNEL_INVITE_LINK
        else:
            channel_button_url = "https://t.me"
    except Exception as e:
        logger.exception("link generation error")
        channel_button_url = "https://t.me"

    await message.reply_text(
        f"👋 Namaste {user} ji!\n"
        f"Main *Sara* hoon — aapki movie wali dost 💅‍♀️🎥\n"
        f"Movie ka naam bhejiye, main bhejti hoon!\n"
        f"🛠️ Bot created by *VIRENDRA CHAUHAN*\n",
        reply_markup=InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("📺 Channel", url=channel_button_url)]
            ]
        )
    )

@app.on_message((filters.document | filters.video) & filters.private)
async def handle_file(client, message: Message):
    try:
        title = message.caption or "Untitled Movie"
        filename = ""
        file_id = None
        if message.document:
            filename = message.document.file_name
            file_id = message.document.file_id
        elif message.video:
            filename = getattr(message.video, "file_name", "") or ""
            file_id = message.video.file_id
        settings = load_settings()
        msg_id_to_save = 0
        file_url = ""
        if settings.get("auto_forward"):
            try:
                forwarded = await message.forward(CHANNEL_ID)
                msg_id_to_save = forwarded.message_id
                file_url = ""
                logger.info("Forwarded message to channel id=%s msg_id=%s", CHANNEL_ID, msg_id_to_save)
            except Exception:
                logger.exception("Forward to channel failed, will save file_id instead")
                msg_id_to_save = 0
                file_url = file_id
        else:
            msg_id_to_save = 0
            file_url = file_id
        added = add_movie_to_json(title, msg_id=msg_id_to_save, filename=filename, file_url=file_url)
        if added:
            await message.reply_text("✅ Movie saved to movie_list.json")
        else:
            await message.reply_text("⚠️ Movie already exists in list.")
    except Exception:
        logger.exception("handle_file error")
        await message.reply_text("❌ Error while saving movie. Check logs.")

# -------------------------
# SEND HELPERS
# -------------------------
async def send_movie_entry(client: Client, chat_id: int, entry: Dict):
    title = entry.get("title", "Movie")
    sent = False
    if int(entry.get("msg_id", 0)) > 0:
        try:
            await client.forward_messages(chat_id, CHANNEL_ID, entry["msg_id"])
            sent = True
        except Exception:
            logger.exception("forward by msg_id failed")
    if not sent and entry.get("file_url"):
        try:
            await client.send_document(chat_id, entry["file_url"], caption=f"🎬 {title}")
            sent = True
        except Exception:
            logger.exception("send_document failed")
            try:
                await client.send_message(chat_id, f"🎬 {title}\n➡️ {entry['file_url']}")
                sent = True
            except Exception:
                logger.exception("send_message fallback failed")
    return sent

async def send_group_of_movies_with_poster(client: Client, chat_id: int, group: List[Dict], query_title: str):
    if not group:
        return

    poster_url = ""
    try:
        poster_url = get_poster_url_omdb(query_title or group[0].get("title",""))
    except Exception:
        logger.exception("poster fetch failed")

    cap_lines = [f"🎬 Matches for: {query_title}"]
    for i, g in enumerate(group, 1):
        fn = g.get("filename") or g.get("title") or f"Part {i}"
        link = g.get("file_url") or ""
        if link:
            cap_lines.append(f"{i}. {fn} — {link}")
        else:
            cap_lines.append(f"{i}. {fn}")
    caption = "\n".join(cap_lines)

    if poster_url:
        try:
            await client.send_photo(chat_id, poster_url, caption=caption)
        except Exception:
            await client.send_message(chat_id, f"{caption}\n\nPoster: {poster_url}")
    else:
        await client.send_message(chat_id, caption)

    seen: Set[Tuple[int,str]] = set()
    for e in group:
        key = (int(e.get("msg_id",0)), e.get("file_url",""))
        if key in seen:
            continue
        seen.add(key)
        await send_movie_entry(client, chat_id, e)
        await asyncio.sleep(0.4)

# -------------------------
# Text handler
# -------------------------
@app.on_message(filters.text & (filters.private | filters.group))
async def handle_text(client, message: Message):
    if not message.from_user or message.from_user.is_bot:
        return
    text = (message.text or "").strip()
    if not text or text.startswith("/"):
        return

    user_id = message.from_user.id
    chat_id = message.chat.id
    hist = user_message_history.setdefault(user_id, {})
    lt = text.lower()
    hist[lt] = hist.get(lt, 0) + 1
    if hist[lt] > 3:
        return

    if message.chat.type == "private":
        for k, r in conversation_triggers:
            if k in lt:
                await message.reply_text(r)
                return

    try:
        data = load_movies_local()
        if not data:
            await message.reply_text("❌ Movie list empty.")
            return

        matches: List[Dict] = []
        for m in data:
    title = m.get("title","")
    if not title:
        continue

    # ✅ सिर्फ़ तभी match allow करना जब query 3 अक्षर या उससे ज़्यादा हो
    if len(lt) >= 3 and (lt in title.lower() or fuzz.token_set_ratio(lt, title.lower()) >= 70):
        matches.append(m)

        if not matches:
            await message.reply_text("😔 कोई मूवी नहीं मिली।")
            return

        # सभी matches एक group में भेजे जाएंगे
        await send_group_of_movies_with_poster(client, chat_id, matches, text)

    except Exception:
        logger.exception("handle_text search error")
        await message.reply_text("⚠️ Error while searching movies.")
        
# -------------------------
# Run Flask and bot
# -------------------------
def run_flask():
    port = int(os.environ.get("PORT", 8080))
    flask_app.run(host="0.0.0.0", port=port, use_reloader=False)

if __name__ == "__main__":
    if not os.path.exists(SETTINGS_PATH):
        save_settings({"auto_forward": False})
    t = threading.Thread(target=run_flask, daemon=True)
    t.start()
    logger.info("Flask thread started")
    app.run()
