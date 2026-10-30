import os
import time
import threading
import requests
from flask import Flask, jsonify, render_template_string
from web3 import Web3
from eth_account import Account

app = Flask(__name__)

# ===== CONFIG DA RENDER (Pega do Environment) =====
PRIVATE_KEY = os.getenv("PRIVATE_KEY", "").strip()
GOOGLE_SHEET_URL = os.getenv("GOOGLE_SHEET_URL", "").strip()

if PRIVATE_KEY and not PRIVATE_KEY.startswith("0x"):
    PRIVATE_KEY = "0x" + PRIVATE_KEY

WALLET_ADDRESS = None
if PRIVATE_KEY:
    try:
        WALLET_ADDRESS = Account.from_key(PRIVATE_KEY).address
    except:
        WALLET_ADDRESS = None

BSC_RPC = "https://bsc-dataseed.binance.org/"
w3 = Web3(Web3.HTTPProvider(BSC_RPC))

GRID_START = 5.31
GRID_END = 9.11
GRID_LEVELS = 20
GRID_STEP = (GRID_END - GRID_START) / (GRID_LEVELS - 1)

STATE = {
    "preco": 6.92,
    "usdt_bal": 125.898,
    "uni_bal": 18.3085,
    "lucro": 0.0,
    "trades": 0,
    "status": "Iniciando...",
    "wallet": WALLET_ADDRESS or "Carregando...",
    "grids": [],
    "last_error": "",
    "logs": []
}

# Cria grids com SUA lógica correta
# Abaixo do preço = VENDIDO (segura USDT p/ comprar)
# Acima do preço = COMPRADO (segura UNI p/ vender)
def init_grids(preco_ref=6.92):
    STATE["grids"] = []
    for i in range(GRID_LEVELS):
        price = round(GRID_START + i * GRID_STEP, 2)
        # Lógica CORRETA que você falou
        esta_comprado = price > preco_ref
        STATE["grids"].append({
            "id": i+1,
            "price": price,
            "qtd": "9.0 USDT",
            "estado": "COMPRADO" if esta_comprado else "VENDIDO",
            "status": "COMPRADO - Pronto p/ venda" if esta_comprado else "VENDIDO - Pronto p/ compra",
            "trades": 0,
            "profit": 0.0
        })

init_grids(STATE["preco"])

def log(msg):
    print(msg)
    STATE["logs"].insert(0, f"{time.strftime('%H:%M:%S')} {msg}")
    STATE["logs"] = STATE["logs"][:20]

def get_preco_real():
    try:
        r = requests.get("https://api.binance.com/api/v3/ticker/price?symbol=UNIUSDT", timeout=5)
        p = float(r.json()["price"])
        STATE["preco"] = p
        return p
    except Exception as e:
        STATE["last_error"] = f"Preco: {e}"
        return STATE["preco"]

def get_saldo_real():
    if not WALLET_ADDRESS:
        return False
    try:
        abi = '[{"constant":true,"inputs":[{"name":"_owner","type":"address"}],"name":"balanceOf","outputs":[{"name":"balance","type":"uint256"}],"type":"function"}]'
        usdt_c = w3.eth.contract(address=Web3.to_checksum_address("0x55d398326f99059fF775485246999027B3197955"), abi=abi)
        uni_c = w3.eth.contract(address=Web3.to_checksum_address("0xBF5142A225b4a1cfAEC59F842A46b36269De8bDaF"), abi=abi)
        bal_usdt = usdt_c.functions.balanceOf(Web3.to_checksum_address(WALLET_ADDRESS)).call() / 10**18
        bal_uni = uni_c.functions.balanceOf(Web3.to_checksum_address(WALLET_ADDRESS)).call() / 10**18
        STATE["usdt_bal"] = round(bal_usdt, 4)
        STATE["uni_bal"] = round(bal_uni, 4)
        STATE["wallet"] = WALLET_ADDRESS
        STATE["status"] = "Trust Wallet Conectada"
        return True
    except Exception as e:
        STATE["last_error"] = f"Saldo: {str(e)[:90]}"
        return False

def enviar_para_planilha(tipo, preco_grid, preco_atual, qtd):
    if not GOOGLE_SHEET_URL:
        return
    try:
        payload = {
            "tipo": tipo,
            "grid": preco_grid,
            "preco_atual": preco_atual,
            "qtd": qtd,
            "usdt_bal": STATE["usdt_bal"],
            "uni_bal": STATE["uni_bal"],
            "wallet": WALLET_ADDRESS,
            "timestamp": time.strftime('%Y-%m-%d %H:%M:%S')
        }
        requests.post(GOOGLE_SHEET_URL, json=payload, timeout=10)
        log(f"Planilha OK {tipo} {preco_grid}")
    except Exception as e:
        log(f"Planilha ERRO {e}")

def loop_bot():
    init_grids(get_preco_real())
    while True:
        try:
            preco = get_preco_real()
            get_saldo_real()
            
            for g in STATE["grids"]:
                # VENDA: preço subiu acima do grid que estava COMPRADO
                if preco >= g["price"] + 0.05 and g["estado"] == "COMPRADO":
                    g["estado"] = "VENDIDO"
                    g["status"] = "VENDIDO - Pronto p/ compra"
                    g["trades"] += 1
                    STATE["trades"] += 1
                    STATE["lucro"] += 0.15
                    log(f"VENDA {g['price']} - preco {preco}")
                    enviar_para_planilha("VENDA", g["price"], preco, g["qtd"])
                
                # COMPRA: preço caiu abaixo do grid que estava VENDIDO
                elif preco <= g["price"] - 0.05 and g["estado"] == "VENDIDO":
                    g["estado"] = "COMPRADO"
                    g["status"] = "COMPRADO - Pronto p/ venda"
                    g["trades"] += 1
                    STATE["trades"] += 1
                    log(f"COMPRA {g['price']} - preco {preco}")
                    enviar_para_planilha("COMPRA", g["price"], preco, g["qtd"])
            
            time.sleep(5)
        except Exception as e:
            STATE["last_error"] = str(e)[:100]
            time.sleep(5)

HTML = """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>UNI Bot</title>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
<style>
body{background:#0f1115;color:#e6e6e6;font-family:'JetBrains Mono',monospace;font-size:12px;margin:0;padding:12px}
.header{display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #222;padding-bottom:8px;margin-bottom:10px}
.price{font-size:18px;font-weight:600}
.bal{display:flex;gap:16px;margin:10px 0}
.bal div{background:#1a1d24;padding:8px 12px;border-radius:6px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:6px}
.card{background:#1a1d24;border-radius:6px;padding:8px;border-left:3px solid #333}
.card.COMPRADO{border-left-color:#22c55e}
.card.VENDIDO{border-left-color:#ef4444}
.badge{font-size:10px;padding:2px 6px;border-radius:10px;color:#fff}
.badge.COMPRADO{background:#22c55e}
.badge.VENDIDO{background:#ef4444}
.log{margin-top:12px;background:#1a1d24;padding:8px;border-radius:6px;max-height:150px;overflow:auto;font-size:11px}
.small{font-size:10px;color:#888}
</style>
</head>
<body>
<div class="header">
<div><b>UNI-BOT v5</b> <span class="small" id="wallet"></span></div>
<div class="price">$<span id="preco">-</span> <span class="small" id="status"></span></div>
</div>
<div class="bal">
<div>UNI: <b id="uni">-</b></div>
<div>USDT: <b id="usdt">-</b></div>
<div>Trades: <b id="trades">-</b> | Lucro: $<b id="lucro">-</b></div>
</div>
<div class="small" id="error" style="color:#f87171;margin-bottom:8px"></div>
<div class="grid" id="grid"></div>
<div class="log" id="logs"></div>
<script>
function load(){
 fetch('/api/state').then(r=>r.json()).then(s=>{
  document.getElementById('preco').innerText=s.preco.toFixed(2);
  document.getElementById('uni').innerText=s.uni_bal;
  document.getElementById('usdt').innerText=s.usdt_bal;
  document.getElementById('trades').innerText=s.trades;
  document.getElementById('lucro').innerText=s.lucro.toFixed(2);
  document.getElementById('status').innerText=s.status;
  document.getElementById('wallet').innerText=(s.wallet||'').slice(0,12)+'...';
  document.getElementById('error').innerText=s.last_error||'';
  let h='';
  s.grids.forEach(g=>{
    h+=`<div class="card ${g.estado}"><div style="display:flex;justify-content:space-between"><b>G${g.id} $${g.price.toFixed(2)}</b><span class="badge ${g.estado}">${g.estado}</span></div><div class="small">${g.qtd} | trades ${g.trades}</div><div class="small">${g.status}</div></div>`;
  });
  document.getElementById('grid').innerHTML=h;
  document.getElementById('logs').innerHTML=s.logs.join('<br>');
 });
}
setInterval(load,3000);load();
</script>
</body>
</html>
"""

@app.route("/")
def home():
    return render_template_string(HTML)

@app.route("/api/state")
def state():
    return jsonify(STATE)

threading.Thread(target=loop_bot, daemon=True).start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
