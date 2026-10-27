from flask import Flask
import requests, time, threading, os
from web3 import Web3

app = Flask(__name__)

RPCS = [
    "https://bsc-dataseed.binance.org/",
    "https://rpc.ankr.com/bsc",
    "https://bsc.publicnode.com",
    "https://1rpc.io/bnb"
]

def get_w3():
    for rpc in RPCS:
        try:
            w = Web3(Web3.HTTPProvider(rpc, request_kwargs={'timeout': 5}))
            if w.is_connected():
                return w, rpc
        except:
            continue
    return None, "nenhum"

w3, rpc_usado = get_w3()

PRIVATE_KEY = os.getenv("PRIVATE_KEY")
ACCOUNT = ""
try:
    if PRIVATE_KEY:
        ACCOUNT = Web3().eth.account.from_key(PRIVATE_KEY).address
    else:
        ACCOUNT = "SEM CHAVE"
except:
    ACCOUNT = "ERRO NA PRIVATE_KEY"

UNI_BSC = Web3.to_checksum_address("0xBf5140A22578168FD562DCcF235E5D43A02Ce9B5")
USDT_BSC = Web3.to_checksum_address("0x55d398326f99059fF775485246999027B3197955")
ROUTER_V2 = Web3.to_checksum_address("0x10ED43C718714eb63d5aA57B78B54704E256024E")

ABI_TOKEN = '[{"inputs":[{"internalType":"address","name":"account","type":"address"}],"name":"balanceOf","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"address","name":"owner","type":"address"},{"internalType":"address","name":"spender","type":"address"}],"name":"allowance","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"address","name":"spender","type":"address"},{"internalType":"uint256","name":"amount","type":"uint256"}],"name":"approve","outputs":[{"internalType":"bool","name":"","type":"bool"}],"stateMutability":"nonpayable","type":"function"}]'
ABI_ROUTER = '[{"inputs":[{"internalType":"uint256","name":"amountIn","type":"uint256"},{"internalType":"uint256","name":"amountOutMin","type":"uint256"},{"internalType":"address[]","name":"path","type":"address[]"},{"internalType":"address","name":"to","type":"address"},{"internalType":"uint256","name":"deadline","type":"uint256"}],"name":"swapExactTokensForTokens","outputs":[{"internalType":"uint256[]","name":"amounts","type":"uint256[]"}],"stateMutability":"nonpayable","type":"function"}]'

estado = {"preco": 7.05, "vendidos": 0, "rpc": rpc_usado, "ultimo_erro": f"Iniciando... RPC: {rpc_usado}", "grids": []}
for i in range(1, 21):
    estado["grids"].append({"n": i, "venda": round(6.83 + (i*0.20),2), "status": "AGUARDANDO"})

def pega_preco():
    try:
        r = requests.get("https://api.binance.com/api/v3/ticker/price?symbol=UNIUSDT", timeout=5)
        return float(r.json()['price'])
    except: return estado["preco"]

def vender_real(qtd):
    global w3, rpc_usado
    try:
        if not w3:
            w3, rpc_usado = get_w3()
            if not w3:
                estado["ultimo_erro"] = "Todos RPCs falharam - Render bloqueando?"
                return False

        bnb = w3.eth.get_balance(Web3.to_checksum_address(ACCOUNT))
        bnb_f = float(w3.from_wei(bnb,'ether'))

        uni = w3.eth.contract(address=UNI_BSC, abi=ABI_TOKEN)
        balance = uni.functions.balanceOf(Web3.to_checksum_address(ACCOUNT)).call()
        balance_f = float(w3.from_wei(balance, 'ether'))

        estado["ultimo_erro"] = f"CONECTADO em {rpc_usado} | BNB={bnb_f:.4f} UNI={balance_f:.3f}"

        router = w3.eth.contract(address=ROUTER_V2, abi=ABI_ROUTER)
        amt = w3.to_wei(qtd, 'ether')
        if balance < amt: amt = balance

        allowance = uni.functions.allowance(Web3.to_checksum_address(ACCOUNT), ROUTER_V2).call()
        if allowance < amt:
            tx = uni.functions.approve(ROUTER_V2, 2**256-1).build_transaction({
                'from': Web3.to_checksum_address(ACCOUNT), 'gas': 100000, 'gasPrice': w3.to_wei('3', 'gwei'),
                'nonce': w3.eth.get_transaction_count(Web3.to_checksum_address(ACCOUNT)), 'chainId': 56
            })
            s = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
            h = w3.eth.send_raw_transaction(s.raw_transaction)
            estado["ultimo_erro"] = f"APROVANDO UNI... {h.hex()}"
            time.sleep(15)
            return True

        path = [UNI_BSC, USDT_BSC]
        tx2 = router.functions.swapExactTokensForTokens(amt, 0, path, Web3.to_checksum_address(ACCOUNT), int(time.time())+600).build_transaction({
            'from': Web3.to_checksum_address(ACCOUNT), 'gas': 350000, 'gasPrice': w3.to_wei('3', 'gwei'),
            'nonce': w3.eth.get_transaction_count(Web3.to_checksum_address(ACCOUNT)), 'chainId': 56
        })
        s2 = w3.eth.account.sign_transaction(tx2, PRIVATE_KEY)
        h2 = w3.eth.send_raw_transaction(s2.raw_transaction)
        estado["ultimo_erro"] = f"VENDA REAL ENVIADA: {h2.hex()}"
        return True
    except Exception as e:
        estado["ultimo_erro"] = f"ERRO: {str(e)[:500]}"
        w3, rpc_usado = get_w3()
        return False

def loop_bot():
    while True:
        preco = pega_preco()
        estado["preco"] = preco
        estado["rpc"] = rpc_usado
        for g in estado["grids"]:
            if preco >= g["venda"] and g["status"] == "AGUARDANDO":
                vender_real(0.1)
                if "VENDA REAL ENVIADA" in estado["ultimo_erro"]:
                    g["status"] = "VENDIDO REAL"
                    estado["vendidos"] += 1
                break
        time.sleep(15)

threading.Thread(target=loop_bot, daemon=True).start()

@app.route("/dashboard")
def dashboard():
    html = f"<html><head><meta http-equiv='refresh' content='5'></head><body style='background:#111;color:#fff;font-family:Arial;padding:10px;word-break:break-all'>"
    html += f"<h2>VENDA REAL - Conta: {ACCOUNT}</h2><div style='background:#222;padding:10px;border-left:4px solid #0f0'>Preco: ${estado['preco']:.4f} | RPC: {estado['rpc']}</div>"
    html += f"<div style='background:#331111;padding:10px;margin:10px 0;border-left:4px solid #f00'>{estado['ultimo_erro']}</div>"
    for g in estado["grids"]:
        html += f"<div>Grid {g['n']}: Venda ${g['venda']} -> {g['status']}</div>"
    html += "</body></html>"
    return html

@app.route("/")
def home(): return f"Rodando - {rpc_usado}"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
