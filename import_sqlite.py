import pandas as pd
import sqlite3

# Baca SEMUA sheet sekaligus
df = pd.read_excel("dataset_chatbot_nara.xlsx", sheet_name=None)

# Gabungkan semua sheet jadi satu
df_all = pd.concat(df.values(), ignore_index=True)

conn = sqlite3.connect("chatbot.db")
df_all.to_sql("intents", conn, if_exists="replace", index=False)
conn.close()

print("Dataset berhasil dimasukkan ke SQLite!")