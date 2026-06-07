from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import sqlite3
import re
import random
from rapidfuzz import fuzz
from Sastrawi.Stemmer.StemmerFactory import StemmerFactory

app = Flask(__name__)
app.secret_key = "user123"

factory = StemmerFactory()
stemmer = factory.create_stemmer()

# =========================
# NLP
# =========================
def preprocess(text):
    text = text.lower()
    text = re.sub(r'[^\w\s]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    text = stemmer.stem(text)
    return text

# =========================
# RESPONSE SYSTEM (UPGRADED)
# =========================
def get_response(user_input, user="Teman"):
    conn = sqlite3.connect("chatbot.db")
    cursor = conn.cursor()

    processed_input = preprocess(user_input)

    # =========================
    # RULE BASE (BIAR NATURAL)
    # =========================

    # sapaan
    if any(word in processed_input for word in ["halo", "hai", "hi"]):
        return random.choice([
            f"Hai {user} 👋 Aku Nara!",
            f"Halo {user}! 😊 Ada yang bisa aku bantu?",
            f"Hai juga {user}! Mau belajar apa hari ini? 📚"
        ])

    # panggil nama bot
    if "nara" in processed_input:
        return random.choice([
            "Iya aku di sini 😊",
            f"Ada apa {user}? 👀",
            "Nara siap bantu! 💜"
        ])

    # terima kasih
    if any(word in processed_input for word in ["terima kasih", "makasih"]):
        return random.choice([
            "Sama-sama 😊",
            "Senang bisa bantu!",
            "Kapan-kapan tanya lagi ya ✨"
        ])

    # siapa kamu
    if "siapa kamu" in processed_input:
        return "Aku Nara 🤖 asisten belajarmu!"

    # =========================
    # INTENT MATCHING
    # =========================
    cursor.execute("SELECT pattern, response FROM intents")
    data = cursor.fetchall()

    best_score = 0
    best_response = None

    for pattern, response in data:
        processed_pattern = preprocess(pattern)
        score = fuzz.token_set_ratio(processed_input, processed_pattern)

        if score > best_score:
            best_score = score
            best_response = response

    conn.close()

    # =========================
    # SMART THRESHOLD
    # =========================
    if best_score >= 70:
        return random.choice([
            best_response,
            f"{best_response} 😊",
            f"{best_response} ya {user} 👍"
        ])

    elif best_score >= 50:
        return random.choice([
            f"Maksud kamu tentang ini ya? 🤔\n{best_response}",
            f"Sepertinya kamu menanyakan ini:\n{best_response}"
        ])

    else:
        return random.choice([
            f"Hmm aku belum paham nih {user} 🤔",
            "Coba jelasin lagi ya 😊",
            "Aku belum ngerti maksudnya 😅",
            "Kamu bisa tanya tentang tugas, materi, atau login 📚"
        ])

# =========================
# ROUTES
# =========================

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/chat")
def chat_page():
    user = session.get("user", "Guest")
    return render_template("chat.html", user=user)

# LOGIN
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        session["user"] = username
        return redirect(url_for("chat_page"))
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("home"))

# =========================
# CHAT API
# =========================
@app.route("/chat_api", methods=["POST"])
def chat_api():
    user_input = request.json["message"]
    user = session.get("user", "Teman")

    response = get_response(user_input, user)

    room_id = session.get("room_id")

    conn = sqlite3.connect("chatbot.db")
    cursor = conn.cursor()

    # kalau belum ada room → auto buat
    if room_id is None:
        cursor.execute(
            "INSERT INTO chat_rooms (user_id, title) VALUES (?, ?)",
            (1, "New Chat")
        )
        room_id = cursor.lastrowid
        session["room_id"] = room_id

    # simpan user message
    cursor.execute(
        "INSERT INTO messages (room_id, sender, message) VALUES (?, ?, ?)",
        (room_id, "user", user_input)
    )

    # simpan bot response
    cursor.execute(
        "INSERT INTO messages (room_id, sender, message) VALUES (?, ?, ?)",
        (room_id, "bot", response)
    )

    conn.commit()
    conn.close()

    return jsonify({"response": response})

# =========================
# NEW CHAT
# =========================
@app.route("/new_chat")
def new_chat():
    conn = sqlite3.connect("chatbot.db")
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO chat_rooms (user_id, title) VALUES (?, ?)",
        (1, "New Chat")
    )

    room_id = cursor.lastrowid
    session["room_id"] = room_id

    conn.commit()
    conn.close()

    return redirect(url_for("chat_page"))

# =========================
# LOAD MESSAGES
# =========================
@app.route("/get_messages")
def get_messages():
    room_id = session.get("room_id")

    if room_id is None:
        return jsonify([])

    conn = sqlite3.connect("chatbot.db")
    cursor = conn.cursor()

    cursor.execute(
        "SELECT sender, message FROM messages WHERE room_id=?",
        (room_id,)
    )

    data = cursor.fetchall()
    conn.close()

    return jsonify(data)

# =========================
# LOAD ROOMS
# =========================
@app.route("/get_rooms")
def get_rooms():
    conn = sqlite3.connect("chatbot.db")
    cursor = conn.cursor()

    cursor.execute("SELECT id, title FROM chat_rooms")
    rooms = cursor.fetchall()

    conn.close()
    return jsonify(rooms)

# =========================

if __name__ == "__main__":
    app.run(debug=True)