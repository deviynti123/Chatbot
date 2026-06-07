from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
import sqlite3
import re
import random
from rapidfuzz import fuzz
from Sastrawi.Stemmer.StemmerFactory import StemmerFactory
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "user123"

factory = StemmerFactory()
stemmer = factory.create_stemmer()

# =========================
# DATABASE INIT
# =========================
def init_db():
    conn = sqlite3.connect("chatbot.db")
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fullname TEXT NOT NULL,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_rooms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            title TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_id INTEGER,
            sender TEXT,
            message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()

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
# RESPONSE SYSTEM
# =========================
def get_response(user_input, user="Teman"):
    conn = sqlite3.connect("chatbot.db")
    cursor = conn.cursor()

    processed_input = preprocess(user_input)

    # RULE BASE
    if any(word in processed_input for word in ["halo", "hai", "hi"]):
        return random.choice([
            f"Hai {user} 👋 Aku Nara!",
            f"Halo {user}! 😊 Ada yang bisa aku bantu?",
            f"Hai juga {user}! Mau belajar apa hari ini? 📚"
        ])

    if "nara" in processed_input:
        return random.choice([
            "Iya aku di sini 😊",
            f"Ada apa {user}? 👀",
            "Nara siap bantu! 💜"
        ])

    if any(word in processed_input for word in ["terima kasih", "makasih"]):
        return random.choice([
            "Sama-sama 😊",
            "Senang bisa bantu!",
            "Kapan-kapan tanya lagi ya ✨"
        ])

    if "siapa kamu" in processed_input:
        return "Aku Nara 🤖 asisten belajarmu!"

    # INTENT MATCHING
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

    # SMART THRESHOLD
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
# ROUTES – HALAMAN UTAMA
# =========================

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/chat")
def chat_page():
    user = session.get("user", "Guest")
    return render_template("chat.html", user=user)

# =========================
# ROUTES – AUTH
# =========================

@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user"):
        return redirect(url_for("chat_page"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or not password:
            flash("Username dan password wajib diisi!", "error")
            return redirect(url_for("login"))

        conn = sqlite3.connect("chatbot.db")
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, password FROM users WHERE username=?", (username,))
        user = cursor.fetchone()
        conn.close()

       if user and check_password_hash(user[2], password):
    session["user_id"] = user[0]
    session["user"] = user[1]

    conn = sqlite3.connect("chatbot.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id FROM chat_rooms
        WHERE user_id=?
        ORDER BY created_at DESC
        LIMIT 1
    """, (user[0],))

    last_room = cursor.fetchone()
    conn.close()

    if last_room:
        session["room_id"] = last_room[0]
    else:
        session.pop("room_id", None)

    return redirect(url_for("chat_page"))

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if session.get("user"):
        return redirect(url_for("chat_page"))

    if request.method == "POST":
        fullname = request.form.get("fullname", "").strip()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm  = request.form.get("confirm_password", "")

        if not fullname or not username or not password:
            flash("Semua field wajib diisi!", "error")
            return redirect(url_for("signup"))

        if len(password) < 6:
            flash("Password minimal 6 karakter!", "error")
            return redirect(url_for("signup"))

        if password != confirm:
            flash("Password dan konfirmasi tidak cocok!", "error")
            return redirect(url_for("signup"))

        hashed = generate_password_hash(password)

        try:
            conn = sqlite3.connect("chatbot.db")
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO users (fullname, username, password) VALUES (?, ?, ?)",
                (fullname, username, hashed)
            )
            conn.commit()
            conn.close()
            flash("Akun berhasil dibuat! Silakan login.", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("Username sudah dipakai, coba yang lain!", "error")
            return redirect(url_for("signup"))

    return render_template("signup.html")


@app.route("/logout")
def logout():
    session.clear()
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
    user_id = session.get("user_id", 1)

    conn = sqlite3.connect("chatbot.db")
    cursor = conn.cursor()

    if room_id is None:
        cursor.execute(
            "INSERT INTO chat_rooms (user_id, title) VALUES (?, ?)",
            (user_id, "New Chat")
        )
        room_id = cursor.lastrowid
        session["room_id"] = room_id

    cursor.execute(
        "INSERT INTO messages (room_id, sender, message) VALUES (?, ?, ?)",
        (room_id, "user", user_input)
    )
    cursor.execute(
        "INSERT INTO messages (room_id, sender, message) VALUES (?, ?, ?)",
        (room_id, "bot", response)
    )

    # update judul room dari pesan pertama
    cursor.execute("SELECT COUNT(*) FROM messages WHERE room_id=?", (room_id,))
    count = cursor.fetchone()[0]
    if count <= 2:
        short = user_input[:30] + ("..." if len(user_input) > 30 else "")
        cursor.execute("UPDATE chat_rooms SET title=? WHERE id=?", (short, room_id))

    conn.commit()
    conn.close()

    return jsonify({"response": response})

# =========================
# NEW CHAT
# =========================

@app.route("/new_chat")
def new_chat():
    user_id = session.get("user_id", 1)

    conn = sqlite3.connect("chatbot.db")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO chat_rooms (user_id, title) VALUES (?, ?)",
        (user_id, "New Chat")
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
        "SELECT sender, message FROM messages WHERE room_id=? ORDER BY id ASC",
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
    user_id = session.get("user_id")

    conn = sqlite3.connect("chatbot.db")
    cursor = conn.cursor()

    if user_id:
        cursor.execute(
            "SELECT id, title FROM chat_rooms WHERE user_id=? ORDER BY created_at DESC LIMIT 20",
            (user_id,)
        )
    else:
        cursor.execute("SELECT id, title FROM chat_rooms ORDER BY created_at DESC LIMIT 20")

    rooms = cursor.fetchall()
    conn.close()
    return jsonify(rooms)

# =========================

if __name__ == "__main__":
    init_db()
    app.run(debug=True)