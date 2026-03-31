from flask import Flask, render_template
import threading
import bot  # 🔥 너가 만든 bot.py 불러오기

app = Flask(__name__)

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/start")
def start():
    bot.start()
    return "started"

@app.route("/stop")
def stop():
    bot.stop()
    return "stopped"

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)