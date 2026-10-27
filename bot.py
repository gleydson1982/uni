from flask import Flask
import requests, time, threading, os
from web3 import Web3
app = Flask(__name__)

RPCS = [
    "https://bsc-mainnet.nodereal.io/v1/64a9df0874fb4a93d87595a3524a732",
    "https://bsc-dataseed1.binance.org",
    "https://bsc-dataseed2.binance.org",
    "https://bsc-dataseed3.binance.org",
    "https://1rpc.io/bnb",
    "https://bsc.publicnode.com",
    "https://rpc.ankr.com/bsc"
]

PRIVATE_KEY = os.getenv("PRIVATE_KEY")
ACCOUNT = Web3().eth.account.from_key(PRIVATE_KEY).address if PRIVATE_KEY else "SEM CHAVE"
UNI_BSC = Web3.to_checksum_address("0xBf5140A22578168FD562DCcF235E5D43A02Ce9B5")

ABI = '[{"inputs":[{"internalType":"address","name":"account","type":"address"}],"name":"balanceOf","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"}]'

estado = {"preco": 7.05, "msg": "Iniciando...", "grids": []}
for i in range(1,21):
    estado["grids"].append({"n":i,"venda":round(6.83+i*0.20,2),"status":"AGUARDANDO"})

def get_saldo_tentando_todos():
    for rpc in RPCS:
        try:
            w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={'timeout':8}))
            if not w3.is_connected(): continue
            bnb = float(w3.from_wei(w3.eth.get_balance(Web3.to_checksum_address(ACCOUNT)),'ether'))
            c = w3.eth.contract(address=UNI_BSC, abi=ABI)
            bal = c.functions.balanceOf(Web3.to_checksum_address(ACCOUNT)).call()
            uni = float(w3.from_wei(bal,'ether'))
            return f"CONECTADO OK | RPC: {rpc} | BNB: {bnb:.5f} | UNI: {uni:.4f} | Conta: {ACCOUNT}"
        except Exception as e:
            last = f"RPC {rpc} falhou: {str(e)[:150]}"
            continue
    return f"ERRO EM TODOS RPCs - Ultimo: {last}"

def pega_preco():
    try:
        r = requests.get("https://api.binance.com/api/v3/ticker/price?symbol=UNIUSDT", timeout=5)
        return float(r.json()['price'])
    except: return estado["preco"]

def loop():
    while True:
        estado["preco"] = pega_preco()
        estado["msg"] = get_saldo_tentando_todos()
        time.sleep(15)

threading.Thread(target=loop, daemon=True).start()

@app.route("/dashboard")
def dash():
    h=f"<html><head><meta http-equiv='refresh' content='5'></head><body style='background:#111;color:#fff;font-family:Arial;padding:10px;word-break:break-all'>"
    h+=f"<h2>VENDA REAL - {ACCOUNT}</h2><div style='background:#222;padding:12px;border-left:4px solid #0f0'>Preco: ${estado['preco']:.4f}<br>{estado['msg']}</div><br>"
    for g in estado["grids"]:
        h+=f"<div>Grid {g['n']}: ${g['venda']} -> {g['status']}</div>"
    h+="</body></html>"
    return h

@app.route("/")
def home(): return "Rodando"

if __name__=="__main__":
    app.run(host="0.0.0.0", port=10000)
