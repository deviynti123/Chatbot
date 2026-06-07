import pandas as pd
import sqlite3

df = pd.read_excel("dataset_.xlsx")

conn = sqlite3.connect("chatbot.db")

df.to_sql("intents", conn, if_exists="replace", index=False)

conn.close()

print("Dataset berhasil dimasukkan ke SQLite!")