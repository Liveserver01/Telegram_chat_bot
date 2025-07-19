import os
import json
import requests
from base64 import b64encode

def save_json_to_github(data):
    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPO")
    file_path = os.environ.get("GITHUB_FILE_PATH")
    branch = os.environ.get("GITHUB_BRANCH", "main")

    url = f"https://api.github.com/repos/{repo}/contents/{file_path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json"
    }

    # GitHub file की SHA लेना जरूरी है update के लिए
    response = requests.get(url, headers=headers)
    sha = response.json().get("sha") if response.status_code == 200 else None

    # JSON को base64 में encode करना पड़ेगा GitHub API के लिए
    encoded_content = b64encode(json.dumps(data, indent=4, ensure_ascii=False).encode()).decode()

    payload = {
        "message": "Update movie_list.json",
        "content": encoded_content,
        "branch": branch
    }

    if sha:
        payload["sha"] = sha

    res = requests.put(url, headers=headers, json=payload)

    if res.status_code in [200, 201]:
        print("✅ JSON GitHub पर save हो गया!")
    else:
        print("❌ GitHub save error:", res.text)


def add_movie_to_json(title, msg_id, filename=None):
    path = "movie_list.json"
    data = []

    # अगर पहले से JSON मौजूद है तो उसे लोड करो
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                data = []

    # नया मूवी object बनाओ
    movie = {
        "title": title.strip().lower(),
        "msg_id": msg_id
    }

    if filename:
        movie["filename"] = filename.strip()

    # Append करो और save करो
    data.append(movie)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    # GitHub पर भी push करो
    save_json_to_github(data)
