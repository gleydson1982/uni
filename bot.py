from flask import Flask
import requests, time, threading, os
from web3 import Web3

app = Flask(__name__)

RPCS = [
    "https://rpc.ankr.com/bsc",
    "https://bsc.publicnode.com",
    "https://1rpc.io/bnb",
    "https://bsc-dataseed.binance.org/"
]

def get_w3():
    for rpc in RPCS:
        try:
            w = Web3(Web3.HTTPProvider(rpc, request_kwargs={'timeout': 10}))
            if w.is_connected():
                return w, rpc
        except: pass
    return None, "nenhum"

w3, rpc_usado = get_w3()
PRIVATE_KEY = os.getenv("PRIVATE_KEY")
ACCOUNT = Web3().eth.account.from_key(PRIVATE_KEY).address if PRIVATE_KEY else "SEM CHAVE"

UNI_BSC = Web3.to_checksum_address("0xBf5140A22578168FD562DCcF235E5D43A02Ce9B5")
USDT_BSC = Web3.to_checksum_address("0x55d398326f99059fF775485246999027B3197955")
ROUTER_V2 = Web3.to_checksum_address("0x10ED43C718714eb63d5aA57B78B54704E256024E")

ABI_TOKEN = '[{"inputs":[{"internalType":"address","name":"account","type":"address"}],"name":"balanceOf","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"address","name":"owner","type":"address"},{"internalType":"address","name":"spender","type":"address"}],"name":"allowance","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"address","name":"spender","type":"address"},{"internalType":"uint256","name":"amount","type":"uint256"}],"name":"approve","outputs":[{"internalType":"bool","name":"","type":"bool"}],"stateMutability":"nonpayable","type":"function"}]'
ABI_ROUTER = '[{"inputs":[{"internalType":"uint256","name":"amountIn","type":"uint256"},{"internalType":"uint256","name":"amountOutMin","type":"uint256"},{"internalType":"address[]","name":"path","type":"address[]"},{"internalType":"address","name":"to","type":"address"},{"internalType":"uint256","name":"deadline","type":"uint256"}],"name":"swapExactTokensForTokens","outputs":[{"internalType":"uint256[]","name":"amounts","type":"uint256[]"}],"stateMutability":"nonpayable","type":"function"}]'

estado = {"preco": 7.05, "vendidos": 0, "rpc": rpc_usado, "ultimo_erro": f"Iniciando com {rpc_usado}", "grids": []}
for i in range(1, 21):
    estado["grids"].append({"n": i, "venda": round(6.83 + (i*0.20),2), "status": "AGUARDANDO"})

def pega_preco():
    try:
        r = requests.get("https://api.binance.com/api/v3/ticker/price?symbol=UNIUSDT", timeout=5)
        return float(r.json()['price'])
    except: return estado["preco"]

def check_saldos():
    global w3, rpc_usado
    try:
        if not w3: 
            w3, rpc_usado = get_w3()
        if not w3:
            return "Todos RPC falharam"
        bnb = w3.eth.get_balance(Web3.to_checksum_address(ACCOUNT))
        bnb_f = float(w3.from_wei(bnb,'ether'))
        uni_c = w3.eth.contract(address=UNI_BSC, abi=ABI_TOKEN)
        bal = uni_c.functions.balanceOf(Web3.to_checksum_address(ACCOUNT)).call()
        bal_f = float(w3.from_wei(bal, 'ether'))
        estado["rpc"] = rpc_usado
        return f"CONECTADO OK | RPC: {rpc_usado} | BNB: {bnb_f:.5f} | UNI: {bal_f:.4f}"
    except Exception as e:
        return f"ERRO SALDO: {str(e)[:300]}"

def loop_bot():
    while True:
        estado["preco"] = pega_preco()
        estado["ultimo_erro"] = check_saldos()
        time.sleep(15)

threading.Thread(target=loop_bot, daemon=True).start()

@app.route("/dashboard")
def dashboard():
    html = f"<html><head><meta http-equiv='refresh' content='5'></head><body style='background:#111;color:#fff;font-family:Arial;padding:10px;word-break:break-all'>"
    html += f"<h2>VENDA REAL - Conta: {ACCOUNT}</h2><div style='background:#222;padding:10px;border-left:4px solid #0f0'>Preco: ${estado['preco']:.4f} | {estado['ultimo_erro']}</div>"
    for g in estado["grids"]:
        html += f"<div>Grid {g['n']}: Venda ${g['venda']} -> {g['status']}</div>"
    html += "</body></html>"
    return html

@app.route("/")
def home(): return "Rodando"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
