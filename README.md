# 🎬 YouTube Livestream Redirector Dashboard

A lightweight Flask-based dashboard that caches YouTube livestream URLs (M3U8) and serves them via redirect links. Built for simplicity, speed, and self-hosting — ideal for embedding or sharing stable stream links.

[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/M4M31NTEGN)

---

## 🚀 Features

- 🔁 **Redirector**: Serve cached M3U8 links via `/stream?name=...`
- 🧠 **Smart Caching**: Uses `yt-dlp` to extract and refresh livestream URLs
- 🗂️ **Dashboard**: View, add, delete, and refresh streams
- 📊 **Access Logs**: Track IP-based access counts and timestamps per stream
- 🕒 **Auto Scheduler**: Refreshes streams every 6 hours (configurable)
- 🐳 **Dockerized**: Easy deployment with Docker & Portainer

---

## 📦 Requirements

- Python 3.8+
- `yt-dlp`, `Flask`, `TinyDB`, `APScheduler`, `gunicorn`, `python-dotenv` (see `requirements.txt`)

---

## 🛠️ Setup

### 1. Clone the Repo

```bash
git clone https://github.com/yourusername/youtube-redirector.git
cd youtube-redirector


2. Add Your Channels
App initially reads the entries in channels.txt. So make sure you enter the channels you like to channels.txt in a comma separated value format. Eg. ChannelHandleOfYourChoice,https://www.youtube.com/watch?v=VIDEO_ID (also supports https://www.youtube.com/@channelname/live format) See included channels.txt for more examples.
 
ChannelHandleOfYourChoice will be name of the stream, the part you will use after https://yourdomain.com:6095/stream?name=the_name_you_have_chosen_while_adding_the_stream
 
After first launch the channels.txt will be updated automatically if you delete/add channels using the dashboard UI. You can also download the up-to-date channels.txt using the download button. 

3. Build & Run with Docker
docker-compose up --build -d

The app will be available at: http://localhost:6095/dashboard

🖥️ Dashboard

•  🔄 Refresh Now: Manually refresh all stream links
•  ➕ Add New Stream: Append a new YouTube livestream
•  📊 View Access Logs: See IP-based access counts and timestamps
•  🗑️ Delete: Remove a stream from the cache

🔁 Redirect Usage

To get the latest M3U8 link for a stream:
https://yourdomain.com:6095/stream?name=channelname
http://localhost:6095/stream?name=the_name_you_have_chosen_while_adding_the_stream

⚙️ Configuration (Optional)

Edit config.py:

UPDATE_INTERVAL_HOURS = 6  # How often to refresh links

📊 Access Logging

Each time a stream is accessed via /stream, the following is logged:

•  IP address
•  Timestamp
•  Stream name

View logs at /dashboard/logs.

🧼 Logging

Minimal but informative logs are printed to stdout:
[CACHE] stream_name updated
[SERVE] stream_name served to 203.0.113.10
[ADD] stream_name added
[DELETE] stream_name removed
[REFRESH] Manual refresh triggered


🧪 Development

To run locally:
pip install -r requirements.txt
python app.py

📄 License

MIT License — free to use, modify, and distribute.


🙌 Credits

Built with ❤️ using:

•  Flask
•  yt-dlp
•  TinyDB
•  APScheduler
