import os, time, threading
from flask import Flask

PRIVATE_KEY = os.getenv("PRIVATE_KEY")

def rodar_bot():
    while True:
        try:
            print("BOT UNI RODANDO...")
            time.sleep(60)
        except Exception as e:
            print(f"Erro: {e}")
            time.sleep(10)

app = Flask(__name__)
@app.route('/')
def home():
    return "Bot UNI online 24/7 - OK!"

if __name__ == "__main__":
    t = threading.Thread(target=rodar_bot, daemon=True)
    t.start()
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
