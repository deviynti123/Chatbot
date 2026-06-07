import sqlite3

conn = sqlite3.connect("chatbot.db")
cursor = conn.cursor()

cursor.execute("SELECT * FROM intents LIMIT 5")
rows = cursor.fetchall()

for row in rows:
    print(row)

conn.close()