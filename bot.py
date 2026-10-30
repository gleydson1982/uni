import os, time, threading, requests
from flask import Flask
from web3 import Web3

# --- CONFIG BSC ---
RPC = "https://bsc-dataseed1.binance.org"
w3 = Web3(Web3.HTTPProvider(RPC))

# ENDERECOS 100% CORRETOS DA SUA TRANSACAO QUE FUNCIONOU
# USDT que aparece na sua BscScan como Binance-Peg BSC-USD
USDT = "0x55d398326f99059fF775485246999027B3197955"
# UNI Binance-Peg UNI
UNI = "0xbf5140a22578168fd20dcae126e236590a8d6bfa"
# Pancake Router v2 que fez sua transacao
PANCAKE_ROUTER = "0x10ED43C718714eb63d5aA57B78B54704E256024E"
WBNB = "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c"

# --- CARTEIRA ---
PRIVATE_KEY = os.getenv("PRIVATE_KEY", "").strip()
ACCOUNT = None
try:
    if PRIVATE_KEY and len(PRIVATE_KEY) > 10:
        ACCOUNT = w3.eth.account.from_key(PRIVATE_KEY).address
except Exception as e:
    ACCOUNT = None

# --- ESTADO DO DASHBOARD ---
estado = {
    "preco_real": None,
    "fonte": "INICIANDO",
    "bnb": 0.0,
    "log": "Iniciando bot - pesquisando preco REAL"
}

def pega_preco_real():
    """SEM CHUTE - SO PESQUISA REAL BINANCE / COINGECKO"""
    try:
        r = requests.get("https://api.binance.com/api/v3/ticker/price?symbol=UNIUSDT", timeout=5).json()
        if 'price' in r:
            p = float(r['price'])
            estado["preco_real"] = p
            estado["fonte"] = "Binance"
            return p, "Binance"
    except:
        pass
    try:
        r = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=uniswap&vs_currencies=usd", timeout=5).json()
        p = float(r['uniswap']['usd'])
        estado["preco_real"] = p
        estado["fonte"] = "CoinGecko"
        return p, "CoinGecko"
    except:
        pass
    if estado["preco_real"]:
        return estado["preco_real"], estado["fonte"] + " (cache)"
    return None, "SEM API"

# --- FLASK DASHBOARD ---
app = Flask(__name__)

@app.route("/")
def dashboard():
    preco, fonte = pega_preco_real()
    
    if preco is None:
        titulo = "PESQUISANDO PRECO REAL... (Binance/CoinGecko)"
        grid_html = "<p style='color:yellow'>Aguardando API real - sem chute de $6.47 / $7.37</p>"
    else:
        titulo = f"${preco:.2f} - PESQUISA REAL ({fonte})"
        grid_html = ""
        for i in range(20):
            preco_grid = 5.51 + (i * 0.10) # Grids de 5.51 ate 7.41
            status = "VENDIDO" if preco > preco_grid else "COMPRADO"
            cor = "#ff4444" if status == "VENDIDO" else "#44ff44"
            grid_html += f"<div style='border:1px solid #333;padding:6px;margin:3px;background:#222'>Grid {i}: ${preco_grid:.2f} <b style='color:{cor}'>{status}</b></div>"

    bnb_txt = f"{estado['bnb']:.6f}" if estado['bnb'] else "0.000000"
    conta_txt = ACCOUNT if ACCOUNT else "PRIVATE_KEY nao configurada"

    return f"""
    <html><head><meta http-equiv="refresh" content="10"></head>
    <body style="background:#111;color:#fff;font-family:monospace;padding:20px">
        <h2>UNI BOT V5 - {titulo}</h2>
        <p>Conta: {conta_txt} | BNB: {bnb_txt}</p>
        <p>Log: {estado['log']}</p>
        <p>Transacao referencia que funcionou: 0x6dd6ab70b4858dd5a176abb1550a17417951dab5e4dafcf6cccef506477a3fb1</p>
        <p>Router: {PANCAKE_ROUTER}</p>
        <hr>
        <div style="display:grid;grid-template-columns:1fr 1fr 1fr">{grid_html}</div>
    </body></html>
    """

# --- LOOP DO BOT ---
def bot_loop():
    while True:
        try:
            preco, fonte = pega_preco_real()
            estado["fonte"] = fonte
            if preco:
                estado["log"] = f"Preco REAL pesquisado: ${preco:.4f} ({fonte}) - Rota USDT->WBNB->UNI igual da Trust Wallet"
            else:
                estado["log"] = "Sem API ainda, tentando de novo..."
            
            if ACCOUNT:
                try:
                    bal = w3.eth.get_balance(ACCOUNT)
                    estado["bnb"] = float(w3.from_wei(bal, 'ether'))
                except:
                    pass
        except Exception as e:
            estado["log"] = f"Erro loop: {str(e)[:100]}"
        time.sleep(15)

threading.Thread(target=bot_loop, daemon=True).start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
