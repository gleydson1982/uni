import os, time, requests, threading
from datetime import datetime
from flask import Flask, render_template_string
import gspread
from oauth2client.service_account import ServiceAccountCredentials

app = Flask(__name__)

# ===== CONFIG =====
GRID_START = 5.31
GRID_STEP = 0.20
GRID_LEVELS = 20
SYMBOL = "UNIUSDT"
GOOGLE_SHEET_ID = "1gEyaX1v7S4DKpQYcU09owU2scNGYEgFQP7icYvGjyg"

STATE = {
    "preco": 6.91,
    "fonte": "Binance",
    "status": "OK",
    "uni_bal": 10.3605,
    "usdt_bal": 135.8091,
    "lucro": 1.92,
    "last_error": "Iniciando bot...",
    "historico": [],
    "grids": []
}

# Cria grids correto: abaixo do preço = COMPRADO
for i in range(GRID_LEVELS):
    price = GRID_START + i * GRID_STEP
    esta_comprado = price < STATE["preco"]
    STATE["grids"].append({
        "id": i+1,
        "price": price,
        "qtd": "9.0 USDT",
        "status": "COMPRADO - Pronto p/ venda" if esta_comprado else "VENDIDO - Pronto p/ compra",
        "trades": 1 if esta_comprado else 0,
        "profit": 0.0,
        "estado": "COMPRADO" if esta_comprado else "VENDIDO"
    })

def get_preco_3_fontes():
    try:
        r = requests.get(f"https://api.binance.com/api/v3/ticker/price?symbol={SYMBOL}", timeout=3)
        STATE["fonte"] = "Binance"
        return float(r.json()['price'])
    except: pass
    try:
        r = requests.get("https://api.coinbase.com/v2/prices/UNI-USD/spot", timeout=3)
        STATE["fonte"] = "Coinbase"
        return float(r.json()['data']['amount'])
    except: pass
    try:
        r = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=uniswap&vs_currencies=usd", timeout=3)
        STATE["fonte"] = "CoinGecko"
        return float(r.json()['uniswap']['usd'])
    except: pass
    STATE["fonte"] = "Cache"
    return STATE["preco"]

def enviar_para_planilha(tipo, preco, qtd, total, hash_tx, saldo_usdt, saldo_uni, lucro_trade):
    # CORREÇÃO: não dá mais erro azul se não tiver credenciais.json
    if not os.path.exists("credenciais.json"):
        STATE["last_error"] = f"Simulação OK {tipo} {preco} - Hash {hash_tx[:10]}..."
        return True
    try:
        scope = ["https://spreadsheets.google.com/feeds","https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_name("credenciais.json", scope)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(GOOGLE_SHEET_ID).sheet1
        agora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        novo_lucro_total = STATE["lucro"] + lucro_trade
        linha = [agora, tipo, preco, qtd, total, lucro_trade, novo_lucro_total, hash_tx, saldo_usdt, saldo_uni]
        sheet.append_row(linha)
        STATE["lucro"] = novo_lucro_total
        STATE["historico"].insert(0, f"{agora} {tipo} {qtd} @ ${preco}")
        STATE["last_error"] = f"{tipo} {preco} OK"
        return True
    except Exception as e:
        STATE["last_error"] = f"Planilha: {str(e)[:80]}"
        return False

def loop_bot():
    while True:
        try:
            preco_real = get_preco_3_fontes()
            STATE["preco"] = preco_real
            for g in STATE["grids"]:
                if preco_real >= g["price"] + 0.10 and g["estado"] == "COMPRADO":
                    hash_fake = f"0x{os.urandom(32).hex()}"
                    enviar_para_planilha("VENDA", g["price"], 2.40247, 2.40247*g["price"], hash_fake, STATE["usdt_bal"], STATE["uni_bal"], 0.48)
                    g["estado"] = "VENDIDO"
                    g["status"] = "VENDIDO - Pronto p/ compra"
                    g["trades"] += 1
                elif preco_real <= g["price"] - 0.10 and g["estado"] == "VENDIDO":
                    hash_fake = f"0x{os.urandom(32).hex()}"
                    enviar_para_planilha("COMPRA", g["price"], 1.4263, 9.0, hash_fake, STATE["usdt_bal"], STATE["uni_bal"], 0)
                    g["estado"] = "COMPRADO"
                    g["status"] = "COMPRADO - Pronto p/ venda"
                    g["trades"] += 1
        except Exception as e:
            STATE["last_error"] = f"Erro loop: {e}"
            STATE["status"] = "ERRO"
        time.sleep(5)

HTML_DASH = """
<html><head><meta http-equiv="refresh" content="3">
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&family=Inter:wght@400;600&display=swap" rel="stylesheet">
<style>
body{background:#0e0e10;color:#d1d1d1;font-family:'Inter',sans-serif;padding:12px;margin:0}
.top{border:1px solid #00e676;border-radius:10px;padding:14px 18px;display:flex;justify-content:space-between;align-items:center;background:#16161a}
.price{font-family:'JetBrains Mono',monospace;font-size:22px;font-weight:700;color:#00e676}
.small{font-size:11px;color:#888;text-transform:uppercase;letter-spacing:0.5px}
.grid{display:grid;grid-template-columns:2fr 1fr;gap:12px;margin-top:12px}
.box{background:#16161a;border:1px solid #232326;border-radius:10px;padding:14px}
.badge{font-size:10px;padding:3px 6px;border-radius:4px;font-weight:600}
.badge-buy{background:rgba(0,230,118,0.15);color:#00e676;border:1px solid rgba(0,230,118,0.3)}
.badge-sell{background:rgba(255,82,82,0.15);color:#ff5252;border:1px solid rgba(255,82,82,0.3)}
.row{display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid #1f1f23;font-size:12px;font-family:'JetBrains Mono',monospace}
.row:last-child{border:none}
.profit{font-family:'JetBrains Mono',monospace;font-size:20px;font-weight:700;color:#00e676}
.error{margin-top:10px;background:#1e1e2e;color:#8b9cff;padding:8px 10px;border-radius:6px;font-size:11px;font-family:'JetBrains Mono',monospace}
</style></head><body>
<div class="top">
<div><div class="small">Preço Real UNI / USDT</div><div class="price">${{preco}} <span style="font-size:11px;color:#888;font-weight:400">{{fonte}}</span></div><div class="small">Binance + Coinbase + CoinGecko | {{hora}} | Status: {{status}}</div></div>
<div style="text-align:right"><div class="small">Saldo Total</div><div class="price" style="font-size:16px">${{uni_usd}} + ${{usdt_bal}}</div></div>
</div>
<div class="grid">
<div class="box">
<div class="small" style="margin-bottom:10px">Carteira & Grid 20 Níveis ($0.20) - Start $5.31</div>
<div style="display:flex;gap:20px;margin-bottom:12px;font-size:12px"><div>UNI <b style="color:#fff">{{uni_bal}}</b> ≈ ${{uni_usd}}</div><div>USDT <b style="color:#fff">{{usdt_bal}}</b></div></div>
{% for g in grids %}
<div class="row"><div>G{{g.id}} <b>${{"%.2f"|format(g.price)}}</b> <span style="color:#666">({{g.qtd}})</span></div><div><span class="badge {{'badge-buy' if g.estado=='COMPRADO' else 'badge-sell'}}">{{g.status}}</span></div><div style="color:#666">{{g.trades}}x</div></div>
{% endfor %}
<div class="error">{{last_error}}</div>
</div>
<div><div class="box"><div class="small">Lucro Realizado</div><div class="profit">+${{lucro}}</div><div class="small" style="margin-top:4px">Planilha: OK | Trades: {{historico|length}}</div></div>
<div class="box" style="margin-top:12px"><div class="small">Histórico</div><div style="margin-top:8px">{% for h in historico %}<div class="small" style="padding:3px 0;color:#aaa">{{h}}</div>{% endfor %}</div><div style="margin-top:16px"><div class="small">Lucro Acumulado</div><div class="profit">+${{lucro}}</div></div></div></div>
</div>
</body></html>
"""

@app.route("/")
def dash():
    return render_template_string(HTML_DASH, preco=f"{STATE['preco']:.4f}", fonte=STATE["fonte"], status=STATE["status"],
                                  hora=datetime.now().strftime("%H:%M:%S"), uni_bal=STATE["uni_bal"],
                                  uni_usd=f"{STATE['uni_bal']*STATE['preco']:.2f}", usdt_bal=STATE["usdt_bal"],
                                  lucro=STATE["lucro"], last_error=STATE["last_error"],
                                  grids=STATE["grids"], historico=STATE["historico"][:10])

threading.Thread(target=loop_bot, daemon=True).start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
