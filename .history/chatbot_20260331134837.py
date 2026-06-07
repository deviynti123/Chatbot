import sqlite3
import re
from rapidfuzz import fuzz
from Sastrawi.Stemmer.StemmerFactory import StemmerFactory

# init stemmer
factory = StemmerFactory()
stemmer = factory.create_stemmer()

def preprocess(text):
    text = text.lower()
    text = re.sub(r'[^\w\s]', '', text)
    text = stemmer.stem(text)
    return text

# connect database
conn = sqlite3.connect("chatbot.db")
cursor = conn.cursor()

while True:
    user_input = input("Kamu: ")

    processed_input = preprocess(user_input)

    cursor.execute("SELECT pattern, response FROM intents")
    data = cursor.fetchall()

    best_score = 0
    best_response = None

    for pattern, response in data:
        processed_pattern = preprocess(pattern)

        score = fuzz.ratio(processed_input, processed_pattern)

        if score > best_score:
            best_score = score
            best_response = response

    # threshold
    if best_score >= 70:
        print("Bot:", best_response)
        print("(Score:", best_score, ")")
    else:
        print("Bot: Maaf, saya belum mengerti.")

conn.close()