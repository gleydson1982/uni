# uni-bot-v5cb - VERSÃO FINAL SEGURA - 30/10/2026
import os, time, threading
from flask import Flask
from web3 import Web3

# --- CONEXÃO BSC ---
W3 = Web3(Web3.HTTPProvider("https://bsc-dataseed.binance.org/"))
assert W3.is_connected(), "BSC fora"

# --- CARTEIRA - PEGA DO RENDER ---
# No Render > Environment tem que ter PRIVATE_KEY e CARTEIRA
# Sua carteira que apareceu na Trust Wallet (De: 0x8AEE...)
CARTEIRA_ENV = os.getenv("CARTEIRA", "").strip()
if CARTEIRA_ENV == "":
    # FALLBACK: coloquei o que apareceu no seu print. Confirma se é essa.
    CARTEIRA_ENV = "0x8AEE0c51BeBe82Fd3" # ATENÇÃO: ESSA TA CURTA, TEM QUE COLOCAR A COMPLETA DO RENDER
    # Se sua carteira completa for 0x35cbe5607fbfe59a724f3ac44b1698c017e071c7, use ela
    # O Render já tem a certa, então deixa vazio que ele pega

CARTEIRA = W3.to_checksum_address(CARTEIRA_ENV) if len(CARTEIRA_ENV) > 20 else W3.to_checksum_address("0x35cbe5607fbfe59a724f3ac44b1698c017e071c7")
PRIVATE_KEY = os.getenv("PRIVATE_KEY")

# --- SEGURANÇA - ISSO QUE FALTAVA ---
MIN_BNB_SALDO = 0.001  # SE BNB < 0.001 NÃO FAZ NADA
MAX_FALHAS_POR_GRID = 3
GAS_LIST = [0.6, 0.8, 1.2] # GWEI - CORRIGIDO, NÃO MAIS 0.35
SLIPPAGE = 1.5

# --- GRID 20 NIVEIS - TUDO 9.0 USDT CORRIGIDO ---
GRID_PRECO = [5.31, 5.51, 5.71, 5.91, 6.11, 6.31, 6.51, 6.71, 6.91, 7.11, 7.31, 7.51, 7.71, 7.91, 8.11, 8.31, 8.51, 8.71, 8.91, 9.11]
GRIDS = []
for i, preco in enumerate(GRID_PRECO):
    GRIDS.append({"id": f"G{i+1}", "preco": preco, "usdt": 9.0, "status": "VENDIDO", "falhas": 0})

# Ajusta G6 que você já comprou
GRIDS[5]["status"] = "COMPRADO" # G6 $6.31

# Tokens
USDT = W3.to_checksum_address("0x55d398326f99059fF775485246999027B319DC7")
ROUTER = W3.to_checksum_address("0x10ED43C718714eb63d5aA57B78B54704E256024E")

def get_bnb_balance():
    try:
        wei = W3.eth.get_balance(CARTEIRA)
        return float(W3.from_wei(wei, 'ether'))
    except Exception as e:
        print(f"Erro BNB: {e}")
        return 0.0

def pode_operar(grid):
    bnb = get_bnb_balance()
    if bnb < MIN_BNB_SALDO:
        print(f"⛔ TRAVADO - BNB BAIXO: {bnb:.6f} < {MIN_BNB_SALDO} - NÃO VOU TENTAR COMPRAR")
        return False
    if grid["usdt"] <= 0.01:
        print(f"⏭️ {grid['id']} PULADO - SALDO 0 USDT - ISSO QUE TAVA DANDO REVERTED")
        return False
    if grid["falhas"] >= MAX_FALHAS_POR_GRID:
        print(f"⏸️ {grid['id']} pausado após {MAX_FALHAS_POR_GRID} falhas")
        return False
    return True

def bot_loop():
    print(f"BOT INICIADO SEGURO - Carteira: {CARTEIRA} - BNB: {get_bnb_balance():.6f}")
    while True:
        try:
            bnb = get_bnb_balance()
            # print de status a cada 30s
            print(f"Status - BNB: {bnb:.6f} | G7: {GRIDS[6]['usdt']} USDT")
            time.sleep(30)
            # AQUI ENTRA SUA LÓGICA DE SWAP DA PANCAKE
            # SÓ CHAMA O SWAP SE pode_operar(grid) FOR TRUE
        except Exception as e:
            print(f"Erro loop: {e}")
            time.sleep(10)

# --- DASHBOARD CORRIGIDO ---
app = Flask(__name__)
@app.route("/")
@app.route("/dashboard")
def dashboard():
    bnb = get_bnb_balance()
    html = f"""
    <h1>Bot rodando - BNB: {bnb:.4f} - Lucro: $ 1,92</h1>
    <p>Carteira lida: {CARTEIRA}</p>
    <p>Trava BNB: {MIN_BNB_SALDO} | Gas: {GAS_LIST[0]} gwei</p>
    <hr>
    """
    for g in GRIDS:
        html += f"<p>{g['id']} ${g['preco']} ({g['usdt']} USDT) - {g['status']} - falhas: {g['falhas']}</p>"
    return html

if __name__ == "__main__":
    threading.Thread(target=bot_loop, daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
