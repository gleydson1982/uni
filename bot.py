import os, json, time, threading, requests
from flask import Flask
from web3 import Web3

BSC_RPCS = [
    "https://bsc-dataseed1.binance.org",
    "https://bsc-dataseed2.binance.org",
    "https://bsc.meowrpc.com"
]
for rpc in BSC_RPCS:
    try:
        w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={'timeout': 5}))
        if w3.is_connected():
            break
    except:
        continue

PRIVATE_KEY = os.getenv("PRIVATE_KEY", "")
ACCOUNT = w3.eth.account.from_key(PRIVATE_KEY).address if PRIVATE_KEY else ""

USDT = Web3.to_checksum_address("0x55d398326f99059ff775485246999027b319dc7".lower())
UNI = Web3.to_checksum_address("0xbf5140a22578168fd20dcae126e236590a8d6bfa".lower())
ROUTER = Web3.to_checksum_address("0x10ed43c718714eb63d5aa57b78b54704e256024e".lower())

GRID_BASE = 5.51
GRID_STEP = 0.10
GRID_N = 20
VALOR_GRID = 9
MIN_BNB = 0.0005

estado = {"grids": {}, "preco_real": None, "bnb": 0, "ultimo_log": "", "fonte": "INICIANDO"}

def log(m):
    estado["ultimo_log"] = m
    print(m, flush=True)

def pega_preco_agora():
    # SEM CHUTE - SO PESQUISA REAL
    # 1 - Binance
    try:
        r = requests.get("https://api.binance.com/api/v3/ticker/price?symbol=UNIUSDT", timeout=4).json()
        if 'price' in r:
            p = float(r['price'])
            if 3 < p < 20:
                estado["preco_real"] = p
                estado["fonte"] = "Binance"
                return p, "Binance", "OK"
    except Exception as e:
        pass
    # 2 - Coinbase
    try:
        r = requests.get("https://api.exchange.coinbase.com/products/UNI-USD/ticker", timeout=4).json()
        if 'price' in r:
            p = float(r['price'])
            if 3 < p < 20:
                estado["preco_real"] = p
                estado["fonte"] = "Coinbase"
                return p, "Coinbase", "OK"
    except:
        pass
    # 3 - CoinGecko
    try:
        r = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=uniswap&vs_currencies=usd", timeout=5).json()
        p = float(r['uniswap']['usd'])
        if 3 < p < 20:
            estado["preco_real"] = p
            estado["fonte"] = "CoinGecko"
            return p, "CoinGecko", "OK"
    except:
        pass
    # 4 - Se tudo falhar, usa o ULTIMO PRECO PESQUISADO (nao chute)
    if estado.get("preco_real") and 3 < estado["preco_real"] < 20:
        return estado["preco_real"], estado.get("fonte", "ULTIMO") + " (cache)", "CACHE"
    
    # 5 - Se nunca pesquisou nada ainda
    return None, "SEM API", "FALHA"

def get_bals():
    try:
        bnb = float(w3.from_wei(w3.eth.get_balance(ACCOUNT), 'ether')) if ACCOUNT else 0
        abi = [{"constant":True,"inputs":[{"name":"_owner","type":"address"}],"name":"balanceOf","outputs":[{"name":"balance","type":"uint256"}],"type":"function"}]
        usdt_c = w3.eth.contract(address=USDT, abi=abi)
        uni_c = w3.eth.contract(address=UNI, abi=abi)
        usdt = usdt_c.functions.balanceOf(ACCOUNT).call() / 1e18 if ACCOUNT else 0
        uni = uni_c.functions.balanceOf(ACCOUNT).call() / 1e18 if ACCOUNT else 0
        estado["bnb"] = bnb
        return bnb, usdt, uni
    except Exception as e:
        log(f"ERRO BAL {e}")
        return estado.get("bnb",0), 0, 0

def bot_loop():
    while True:
        try:
            preco_data = pega_preco_agora()
            preco = preco_data[0]
            fonte = preco_data[1]
            bnb, usdt, uni = get_bals()
            if preco is None:
                log(f"AGUARDANDO API REAL - Binance/CoinGecko fora - tentando de novo em 15s")
                time.sleep(15)
                continue
            if bnb < MIN_BNB:
                log(f"TRAVADO BNB {bnb:.4f} < {MIN_BNB}")
                time.sleep(60)
                continue
            log(f"PRECO REAL ${preco:.2f} ({fonte}) | BNB:{bnb:.4f}")
        except Exception as e:
            log(f"ERRO LOOP {e}")
        time.sleep(15)

app = Flask(__name__)

@app.route("/")
@app.route("/dashboard")
def dashboard():
    preco, fonte, status = pega_preco_agora()
    bnb = estado.get("bnb",0)
    if preco is None:
        preco_txt = "PESQUISANDO PRECO REAL..."
        grids_html = "<p>Aguardando Binance/CoinGecko responder - sem chute</p>"
    else:
        preco_txt = f"${preco:.2f} ({fonte})"
        grids_html = ""
        for i in range(GRID_N):
            p = GRID_BASE + i*GRID_STEP
            status_grid = "VENDIDO" if preco > p else "COMPRADO"
            cor = "#ff4444" if status_grid=="VENDIDO" else "#44ff44"
            qtd = f"{VALOR_GRID} USDT" if status_grid=="COMPRADO" else "0 USDT"
            grids_html += f"<div style='border:1px solid #333;padding:5px;margin:2px'>G{i} ${p:.2f} ({qtd}) <span style='color:{cor}'>{status_grid}</span></div>"

    return f"<html><body style='background:#111;color:#fff;font-family:monospace;padding:20px'><h2>UNI BOT - PRECO REAL {preco_txt}</h2><p>BNB: {bnb:.4f} | {estado.get('ultimo_log','')}</p><h3>GRID 20 - Base ${GRID_BASE}</h3><div style='display:grid;grid-template-columns:1fr 1fr'>{grids_html}</div></body></html>"

threading.Thread(target=bot_loop, daemon=True).start()
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
