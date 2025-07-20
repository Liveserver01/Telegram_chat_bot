import os
import json
import requests
from base64 import b64encode

def save_json_to_github(data):
    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPO")
    file_path = os.environ.get("GITHUB_FILE_PATH")
    branch = os.environ.get("GITHUB_BRANCH", "main")

    if not all([token, repo, file_path]):
        print("❌ GitHub config environment variables missing.")
        return

    url = f"https://api.github.com/repos/{repo}/contents/{file_path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json"
    }

    # पहले से मौजूद SHA लेना
    response = requests.get(url, headers=headers)
    sha = response.json().get("sha") if response.status_code == 200 else None

    # JSON को base64 में encode करना
    encoded_content = b64encode(
        json.dumps(data, indent=4, ensure_ascii=False).encode()
    ).decode()

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

    # JSON फ़ाइल पढ़ो (अगर है तो)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                data = []

    # message ID को int में ensure करो
    try:
        msg_id = int(str(msg_id).strip())
    except ValueError:
        print("❌ Invalid message ID")
        return

    # नया मूवी object बनाओ
    movie = {
        "title": title.strip(),
        "msg_id": msg_id
    }

    if filename:
        movie["filename"] = filename.strip()

    data.append(movie)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

    print("✅ लोकल movie_list.json में नया मूवी ऐड हो गया")

    # GitHub पर अपडेट करो
    save_json_to_github(data)
