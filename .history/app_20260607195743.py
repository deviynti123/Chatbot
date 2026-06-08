from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
import sqlite3
import re
import random
import requests
from rapidfuzz import fuzz
from Sastrawi.Stemmer.StemmerFactory import StemmerFactory
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "user123"

factory = StemmerFactory()
stemmer = factory.create_stemmer()

# =========================
# KONFIGURASI AI FALLBACK
# Ganti dengan API key kamu
# =========================
GEMINI_API_KEY = "ISI_API_KEY_GEMINI_KAMU_DI_SINI"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"

# =========================
# SINONIM / NORMALISASI KATA
# =========================
SINONIM = {
    # Typo & singkatan umum
    "gabisa": "tidak bisa",
    "gbs": "tidak bisa",
    "ga bisa": "tidak bisa",
    "gak bisa": "tidak bisa",
    "ngak bisa": "tidak bisa",
    "tdk bisa": "tidak bisa",
    "ga": "tidak",
    "gak": "tidak",
    "ngak": "tidak",
    "nggak": "tidak",
    "enggak": "tidak",
    "udah": "sudah",
    "udh": "sudah",
    "blm": "belum",
    "blum": "belum",
    "gimana": "bagaimana",
    "gmn": "bagaimana",
    "gmana": "bagaimana",
    "kenapa": "mengapa",
    "knp": "mengapa",
    "krn": "karena",
    "karna": "karena",
    "buat": "untuk",
    "utk": "untuk",
    "trus": "lalu",
    "terus": "lalu",
    "abis": "setelah",
    "habis": "setelah",
    "mau": "ingin",
    "pengen": "ingin",
    "pgn": "ingin",
    "coba": "mencoba",
    "nyoba": "mencoba",
    "lupa": "tidak ingat",
    "error": "masalah",
    "eror": "masalah",
    "lemot": "lambat",
    "loading": "memuat",
    "login": "masuk",
    "log in": "masuk",
    "logout": "keluar",
    "upload": "unggah",
    "uplod": "unggah",
    "download": "unduh",
    "password": "sandi",
    "pass": "sandi",
    "pw": "sandi",
    "akun": "akun",
    "acc": "akun",
    "classroom": "google classroom",
    "gc": "google classroom",
    "gclassroom": "google classroom",
    "quiziz": "quizizz",
    "kuis": "quizizz",
    "moodl": "moodle",
    "cara": "bagaimana",
    "steps": "langkah",
    "step": "langkah",
    "panduan": "petunjuk",
    "tutorial": "petunjuk",
    "tolong": "bantu",
    "help": "bantu",
    "bisa bantu": "bantu",
    "susah": "sulit",
    "ribet": "sulit",
    "ngga muncul": "tidak muncul",
    "ga muncul": "tidak muncul",
    "hilang": "tidak muncul",
}

def normalize(text):
    text = text.lower().strip()
    # Ganti sinonim kata per kata
    words = text.split()
    result = []
    i = 0
    while i < len(words):
        # Coba dua kata dulu (bigram)
        if i + 1 < len(words):
            bigram = words[i] + " " + words[i+1]
            if bigram in SINONIM:
                result.append(SINONIM[bigram])
                i += 2
                continue
        # Satu kata
        word = words[i]
        result.append(SINONIM.get(word, word))
        i += 1
    return " ".join(result)

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
# NLP PREPROCESS
# =========================
def preprocess(text):
    text = normalize(text)           # normalisasi sinonim dulu
    text = re.sub(r'[^\w\s]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    text = stemmer.stem(text)
    return text

# =========================
# DETEKSI PLATFORM
# =========================
def detect_platform(text):
    text = normalize(text.lower())
    if any(k in text for k in ["google classroom", "classroom", "gc"]):
        return "google_classroom"
    elif any(k in text for k in ["quizizz", "quiz", "kuis"]):
        return "quizizz"
    elif "moodle" in text:
        return "moodle"
    return None

# =========================
# FALLBACK KE GEMINI AI
# =========================
def ask_gemini(user_input, user="Teman"):
    try:
        system_context = """Kamu adalah Nara, asisten digital yang membantu guru SD 
        dalam menggunakan platform pembelajaran seperti Google Classroom, Quizizz, dan Moodle.
        Jawab dengan ramah, singkat, dan dalam bahasa Indonesia. 
        Jika pertanyaan di luar topik platform pembelajaran, tetap bantu semampu kamu tapi 
        arahkan kembali ke topik platform pembelajaran SD.
        Panggil user dengan nama mereka jika disebutkan."""

        payload = {
            "contents": [{
                "parts": [{
                    "text": f"{system_context}\n\nUser ({user}): {user_input}"
                }]
            }]
        }
        res = requests.post(GEMINI_URL, json=payload, timeout=8)
        data = res.json()
        answer = data["candidates"][0]["content"]["parts"][0]["text"]
        return answer.strip()
    except Exception:
        return None

# =========================
# CHATBOT RESPONSE SYSTEM
# =========================
def get_response(user_input, user="Teman"):
    conn = sqlite3.connect("chatbot.db")
    cursor = conn.cursor()

    processed_input = preprocess(user_input)

    # Rule-based natural responses
    if any(word in processed_input for word in ["halo", "hai", "hi", "hello"]):
        conn.close()
        return random.choice([
            f"Hai {user} 👋 Aku Nara!",
            f"Halo {user}! 😊 Ada yang bisa aku bantu?",
            f"Hai juga {user}! Mau belajar apa hari ini? 📚"
        ])

    if "nara" in processed_input and len(processed_input.split()) <= 3:
        conn.close()
        return random.choice([
            "Iya aku di sini 😊",
            f"Ada apa {user}? 👀",
            "Nara siap bantu! 💜"
        ])

    if any(word in processed_input for word in ["terima kasih", "makasih", "thanks"]):
        conn.close()
        return random.choice([
            "Sama-sama 😊",
            "Senang bisa bantu!",
            "Kapan-kapan tanya lagi ya ✨"
        ])

    if any(p in processed_input for p in ["siapa kamu", "siapa nara", "kamu siapa"]):
        conn.close()
        return "Aku Nara 🤖 asisten digital yang siap bantu kamu menggunakan platform pembelajaran seperti Google Classroom, Quizizz, dan Moodle!"

    # Intent matching
    platform = detect_platform(user_input)
    cursor.execute("SELECT pattern, response, tag FROM intents")
    data = cursor.fetchall()

    best_score = 0
    best_response = None

    platform_penalty = {
        "google_classroom": ["quizizz", "moodle"],
        "quizizz": ["google_classroom", "moodle"],
        "moodle": ["google_classroom", "quizizz"],
    }

    for pattern, response, tag in data:
        processed_pattern = preprocess(pattern)

        # Gabungkan beberapa scoring untuk fleksibilitas
        score_token  = fuzz.token_set_ratio(processed_input, processed_pattern)
        score_partial = fuzz.partial_ratio(processed_input, processed_pattern)
        score_sort   = fuzz.token_sort_ratio(processed_input, processed_pattern)
        score = max(score_token, score_partial, score_sort)

        if platform:
            tag_lower = tag.lower()
            if platform in tag_lower:
                score += 20
            else:
                for wrong_platform in platform_penalty.get(platform, []):
                    if wrong_platform in tag_lower:
                        score -= 30
                        break

        if score > best_score:
            best_score = score
            best_response = response

    conn.close()

    # Threshold diturunkan: 60 (sebelumnya 70) dan 40 (sebelumnya 50)
    if best_score >= 60:
        return random.choice([
            best_response,
            f"{best_response} 😊",
            f"{best_response} ya {user} 👍"
        ])

    elif best_score >= 40:
        return random.choice([
            f"Maksud kamu tentang ini ya? 🤔\n{best_response}",
            f"Sepertinya kamu menanyakan ini:\n{best_response}"
        ])

    else:
        # ── FALLBACK CERDAS: coba Gemini dulu ──
        ai_response = ask_gemini(user_input, user)
        if ai_response:
            return ai_response

        # ── Fallback akhir: tanya balik user ──
        return random.choice([
            f"Hmm, aku kurang paham nih {user} 🤔 Bisa dijelaskan lebih detail?",
            f"Maksud kamu gimana ya {user}? Coba ceritain lebih lengkap 😊",
            f"Aku belum nangkep maksudnya nih 😅 Kamu lagi pakai platform apa? (Google Classroom, Quizizz, atau Moodle?)",
            f"Bisa diperjelas lagi {user}? Misalnya: 'Cara upload tugas di Google Classroom' 📚",
        ])

# =========================
# HOME
# =========================
@app.route("/")
def home():
    return render_template("index.html")

# =========================
# CHAT PAGE
# =========================
@app.route("/chat")
def chat_page():
    user = session.get("user", "Guest")
    return render_template("chat.html", user=user)

# =========================
# LOGIN
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
            cursor.execute("SELECT id FROM chat_rooms WHERE user_id=? ORDER BY created_at DESC LIMIT 1", (user[0],))
            last_room = cursor.fetchone()
            conn.close()
            if last_room:
                session["room_id"] = last_room[0]
            else:
                session.pop("room_id", None)
            return redirect(url_for("chat_page"))
        else:
            flash("Username atau password salah!", "error")
            return redirect(url_for("login"))
    return render_template("login.html")

# =========================
# SIGNUP
# =========================
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
            cursor.execute("INSERT INTO users (fullname, username, password) VALUES (?, ?, ?)", (fullname, username, hashed))
            conn.commit()
            conn.close()
            flash("Akun berhasil dibuat! Silakan login.", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("Username sudah dipakai!", "error")
            return redirect(url_for("signup"))
    return render_template("signup.html")

# =========================
# LOGOUT
# =========================
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
    user    = session.get("user", "Teman")
    user_id = session.get("user_id", 0)
    response = get_response(user_input, user)
    room_id  = session.get("room_id")
    conn = sqlite3.connect("chatbot.db")
    cursor = conn.cursor()
    if room_id is None:
        cursor.execute("INSERT INTO chat_rooms (user_id, title) VALUES (?, ?)", (user_id, "New Chat"))
        room_id = cursor.lastrowid
        session["room_id"] = room_id
    cursor.execute("INSERT INTO messages (room_id, sender, message) VALUES (?, ?, ?)", (room_id, "user", user_input))
    cursor.execute("INSERT INTO messages (room_id, sender, message) VALUES (?, ?, ?)", (room_id, "bot", response))
    cursor.execute("SELECT COUNT(*) FROM messages WHERE room_id=?", (room_id,))
    count = cursor.fetchone()[0]
    if count <= 2:
        title = user_input[:30] + ("..." if len(user_input) > 30 else "")
        cursor.execute("UPDATE chat_rooms SET title=? WHERE id=?", (title, room_id))
    conn.commit()
    conn.close()
    return jsonify({"response": response})

# =========================
# NEW CHAT
# =========================
@app.route("/new_chat")
def new_chat():
    user_id = session.get("user_id", 0)
    conn = sqlite3.connect("chatbot.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO chat_rooms (user_id, title) VALUES (?, ?)", (user_id, "New Chat"))
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
    cursor.execute("SELECT sender, message FROM messages WHERE room_id=? ORDER BY id ASC", (room_id,))
    data = cursor.fetchall()
    conn.close()
    return jsonify(data)

# =========================
# LOAD ROOMS
# =========================
@app.route("/get_rooms")
def get_rooms():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify([])
    conn = sqlite3.connect("chatbot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, title FROM chat_rooms WHERE user_id=? ORDER BY created_at DESC LIMIT 20", (user_id,))
    rooms = cursor.fetchall()
    conn.close()
    return jsonify(rooms)

# =========================
# LOAD ROOM
# =========================
@app.route("/load_room/<int:room_id>")
def load_room(room_id):
    session["room_id"] = room_id
    conn = sqlite3.connect("chatbot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT sender, message FROM messages WHERE room_id=? ORDER BY id ASC", (room_id,))
    data = cursor.fetchall()
    conn.close()
    return jsonify(data)

# =========================
# DELETE ROOM
# =========================
@app.route("/delete_room/<int:room_id>", methods=["DELETE"])
def delete_room(room_id):
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"status": "error", "message": "Unauthorized"}), 401
    conn = sqlite3.connect("chatbot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM chat_rooms WHERE id=? AND user_id=?", (room_id, user_id))
    room = cursor.fetchone()
    if not room:
        conn.close()
        return jsonify({"status": "error", "message": "Room tidak ditemukan"}), 404
    cursor.execute("DELETE FROM messages WHERE room_id=?", (room_id,))
    cursor.execute("DELETE FROM chat_rooms WHERE id=?", (room_id,))
    conn.commit()
    conn.close()
    if session.get("room_id") == room_id:
        session.pop("room_id", None)
    return jsonify({"status": "ok"})

# =========================
# FORGOT PASSWORD
# =========================
@app.route("/forgot_password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        username     = request.form["username"]
        new_password = generate_password_hash(request.form["password"])
        conn = sqlite3.connect("chatbot.db")
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET password=? WHERE username=?", (new_password, username))
        conn.commit()
        conn.close()
        return redirect(url_for("login"))
    return render_template("forgot_password.html")

# =========================
# RUN APP
# =========================
if __name__ == "__main__":
    init_db()
    app.run(debug=True)