# 🎬 Telegram Movie Bot – Admin Panel, Bulk Management & Auto-Save  

A high-performance Telegram bot built with **Pyrogram + Flask**, designed for managing and sharing movies easily.  
Perfect for personal collections, streaming channels, or private movie-sharing groups.  

---

## 🚀 Features  

- 📥 **Instant Movie Save**  
  Forward movies or posters from your channel and auto-save to `movie_list.json` & GitHub repository.  

- 🛠 **Secure Admin Panel**  
  Password-protected admin interface to manage your movie list without touching the code.  

- 📌 **Bulk Add & Bulk Delete**  
  Add or remove multiple movies in one go, with an easy “Add More” button.  

- 🔄 **GitHub Sync**  
  Real-time update of movie list to your GitHub repo for permanent storage.  

- 📤 **Bulk Send with Delay**  
  Send or forward multiple movies with a built-in delay to avoid Telegram spam limits.  

- ⚙ **Custom Settings**  
  Change bot behavior (auto-forward ON/OFF, delay time, etc.) directly from the panel.  

- 📝 **Activity Logs**  
  All admin actions are recorded in `bot.log` for transparency and troubleshooting.  

---

## 📂 File Structure  

📁 project-root
├── app.py # Flask Admin Panel & API
├── bot.py # Telegram Bot main script
├── updater.py # GitHub sync functions
├── settings.json # Bot settings
├── movie_list.json # Saved movie data
├── bot.log # Action logs
└── requirements.txt # Dependencies


---

## ⚙ Environment Variables  

| Variable Name         | Description |
|-----------------------|-------------|
| `BOT_TOKEN`           | Your Telegram Bot API Token |
| `ADMIN_PASSWORD`      | Admin Panel password |
| `CHANNEL_ID`          | Your Telegram channel ID |
| `CHANNEL_INVITE`      | Permanent invite link of your channel |
| `FLASK_SECRET_KEY`    | Flask session secret key |
| `GITHUB_TOKEN`        | GitHub personal access token |
| `GITHUB_REPO`         | GitHub repo name (e.g. `username/repo`) |
| `GITHUB_FILE_PATH`    | Path to `movie_list.json` in repo |
| `GITHUB_BRANCH`       | Branch name (default: `main`) |

---

## 🌐 Connect with Me

<p align="left">
  <a href="https://facebook.com/virendrachauhan012" target="_blank">
    <img src="https://img.shields.io/badge/Facebook-1877F2?style=for-the-badge&logo=facebook&logoColor=white" />
  </a>
  <a href="https://youtube.com/@Technical-hack-guide" target="_blank">
    <img src="https://img.shields.io/badge/YouTube-FF0000?style=for-the-badge&logo=youtube&logoColor=white" />
  </a>
  <a href="https://youtube.com/@yeraazkyahai" target="_blank">
    <img src="https://img.shields.io/badge/YouTube-FF0000?style=for-the-badge&logo=youtube&logoColor=white" />
  </a>
  <a href="https://www.threads.net/@virendra_chauhan_1" target="_blank">
    <img src="https://img.shields.io/badge/Threads-000000?style=for-the-badge&logo=threads&logoColor=white" />
  </a>
  <a href="https://instagram.com/virendra_chauhan_1" target="_blank">
    <img src="https://img.shields.io/badge/Instagram-E4405F?style=for-the-badge&logo=instagram&logoColor=white" />
  </a>
</p>


## 📜 License  

MIT License © 2025 VIRENDRA CHAUHAN 

---

💡 *Easily manage, share, and store your movie collection without hassle!*  
