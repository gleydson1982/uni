from flask import Flask
import requests
import time
import threading

app = Flask(__name__)

# SEU ESTADO - Já com seus valores novos
estado = {
    "preco": 6.83,
    "base": 6.83,
    "uni": 16.173,
    "usdt": 150.36,
    "comprados": 0,
    "vendidos": 0,
    "lucro": 0,
    "status": "rodando",
    "inicio": time.time(),
    "grids": []
}

# Cria os 20 níveis igual você tinha
for i in range(1, 21):
    compra = round(6.83 - (i * 0.20), 2)
    venda = round(6.83 + (i * 0.20), 2)
    estado["grids"].append({"n": i, "compra": compra, "venda": venda, "status": "AGUARDANDO"})

def pega_preco_real():
    try:
        r = requests.get("https://api.binance.com/api/v3/ticker/price?symbol=UNIUSDT", timeout=5)
        return float(r.json()['price'])
    except:
        try:
            r = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=uniswap&vs_currencies=usd", timeout=5)
            return float(r.json()['uniswap']['usd'])
        except:
            return estado["preco"]  # mantém último se falhar

def loop_bot():
    while True:
        try:
            preco_real = pega_preco_real()
            estado["preco"] = preco_real
            
            # VERIFICA VENDA - Se subiu e tem UNI, vende!
            for g in estado["grids"]:
                if preco_real >= g["venda"] and g["status"] == "AGUARDANDO" and estado["uni"] > 0.5:
                    print(f"VENDENDO Grid {g['n']} a ${preco_real}")
                    estado["uni"] -= 0.5
                    estado["usdt"] += 0.5 * preco_real
                    estado["vendidos"] += 1
                    estado["lucro"] += 0.20
                    g["status"] = "VENDIDO"
                    break
            
            time.sleep(10)
        except Exception as e:
            print(f"Erro loop: {e}")
            time.sleep(10)

threading.Thread(target=loop_bot, daemon=True).start()

@app.route("/")
def home():
    return "Bot rodando! Veja /dashboard"

@app.route("/dashboard")
def dashboard():
    uptime = int(time.time() - estado["inicio"])
    h = uptime // 3600
    m = (uptime % 3600) // 60
    s = uptime % 60
    uptime_str = f"{h:02d}:{m:02d}:{s:02d}"
    
    html = f"""
    <html><head><meta http-equiv='refresh' content='5'><style>
    body{{background:#111;color:#fff;font-family:Arial;padding:10px}}
    .box{{background:#222;padding:15px;border-radius:10px;margin-bottom:10px}}
    table{{width:100%;border-collapse:collapse}} th,td{{padding:8px;text-align:left;border-bottom:1px solid #333}}
    </style></head><body>
    <h2>UNI/USDT GRID - BNB</h2>
    <div class='box'>
    <b>Preco: ${estado['preco']:.2f}</b> (REAL AO VIVO - antes travava em 6.83)<br>
    <b>Base:</b> ${estado['base']}<br>
    <b>UNI:</b> {estado['uni']:.3f} <b>USDT:</b> ${estado['usdt']:.2f}<br>
    </div>
    <div class='box'>
    <b>Comprados:</b> {estado['comprados']}/20 <b>Vendidos:</b> {estado['vendidos']}/20<br>
    <b>Lucro:</b> ${estado['lucro']:.2f}<br>
    <b>Status:</b> {estado['status']} {uptime_str}
    </div>
    <div class='box'><b>P&L por Grid</b></div>
    <div class='box'><b>Grid Levels</b>
    <table><tr><th>N</th><th>Compra</th><th>Venda</th><th>Status</th></tr>
    """
    for g in estado["grids"]:
        html += f"<tr><td>{g['n']}</td><td>${g['compra']}</td><td>${g['venda']}</td><td>{g['status']}</td></tr>"
    html += "</table></div></body></html>"
    return html

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
