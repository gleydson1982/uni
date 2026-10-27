from flask import Flask
import requests, time, threading, os, traceback
from web3 import Web3

app = Flask(__name__)
# RPC NOVO - LlamaRPC, muito mais estável que da Binance
BSC_RPC = "https://binance.llamarpc.com"
w3 = Web3(Web3.HTTPProvider(BSC_RPC))

PRIVATE_KEY = os.getenv("PRIVATE_KEY")
ACCOUNT = w3.eth.account.from_key(PRIVATE_KEY).address if PRIVATE_KEY else "SEM CHAVE"

UNI_BSC = Web3.to_checksum_address("0xBf5140A22578168FD562DCcF235E5D43A02Ce9B5")
USDT_BSC = Web3.to_checksum_address("0x55d398326f99059fF775485246999027B3197955")
ROUTER_V2 = Web3.to_checksum_address("0x10ED43C718714eb63d5aA57B78B54704E256024E")

ABI_TOKEN = '[{"inputs":[{"internalType":"address","name":"account","type":"address"}],"name":"balanceOf","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"address","name":"owner","type":"address"},{"internalType":"address","name":"spender","type":"address"}],"name":"allowance","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"address","name":"spender","type":"address"},{"internalType":"uint256","name":"amount","type":"uint256"}],"name":"approve","outputs":[{"internalType":"bool","name":"","type":"bool"}],"stateMutability":"nonpayable","type":"function"}]'
ABI_ROUTER = '[{"inputs":[{"internalType":"uint256","name":"amountIn","type":"uint256"},{"internalType":"uint256","name":"amountOutMin","type":"uint256"},{"internalType":"address[]","name":"path","type":"address[]"},{"internalType":"address","name":"to","type":"address"},{"internalType":"uint256","name":"deadline","type":"uint256"}],"name":"swapExactTokensForTokens","outputs":[{"internalType":"uint256[]","name":"amounts","type":"uint256[]"}],"stateMutability":"nonpayable","type":"function"}]'

estado = {"preco": 7.05, "vendidos": 0, "lucro": 0, "ultimo_erro": "Conectando no RPC novo...", "inicio": time.time(), "grids": []}
for i in range(1, 21):
    estado["grids"].append({"n": i, "venda": round(6.83 + (i*0.20),2), "status": "AGUARDANDO"})

def pega_preco():
    try:
        r = requests.get("https://api.binance.com/api/v3/ticker/price?symbol=UNIUSDT", timeout=5)
        return float(r.json()['price'])
    except: return estado["preco"]

def vender_real(qtd):
    try:
        if not PRIVATE_KEY:
            estado["ultimo_erro"] = "ERRO: PRIVATE_KEY não está no Render > Environment"
            return False
        
        if not w3.is_connected():
            estado["ultimo_erro"] = "RPC desconectado"
            return False

        bnb = w3.eth.get_balance(ACCOUNT)
        bnb_f = w3.from_wei(bnb,'ether')

        uni = w3.eth.contract(address=UNI_BSC, abi=ABI_TOKEN)
        balance = uni.functions.balanceOf(ACCOUNT).call()
        balance_f = w3.from_wei(balance, 'ether')

        estado["ultimo_erro"] = f"OK: Conectado. BNB={bnb_f:.4f} UNI={balance_f:.3f} - Verificando allowance..."

        router = w3.eth.contract(address=ROUTER_V2, abi=ABI_ROUTER)
        amt = w3.to_wei(qtd, 'ether')
        if balance < amt: amt = balance

        allowance = uni.functions.allowance(ACCOUNT, ROUTER_V2).call()
        if allowance < amt:
            tx = uni.functions.approve(ROUTER_V2, 2**256-1).build_transaction({
                'from': ACCOUNT, 'gas': 100000, 'gasPrice': w3.to_wei('3', 'gwei'),
                'nonce': w3.eth.get_transaction_count(ACCOUNT), 'chainId': 56
            })
            s = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
            h = w3.eth.send_raw_transaction(s.raw_transaction)
            estado["ultimo_erro"] = f"APROVANDO... Hash: {h.hex()} - Aguarde 15s"
            time.sleep(15)
            return True # na proxima volta ele vende

        path = [UNI_BSC, USDT_BSC]
        tx2 = router.functions.swapExactTokensForTokens(amt, 0, path, ACCOUNT, int(time.time())+600).build_transaction({
            'from': ACCOUNT, 'gas': 350000, 'gasPrice': w3.to_wei('3', 'gwei'),
            'nonce': w3.eth.get_transaction_count(ACCOUNT), 'chainId': 56
        })
        s2 = w3.eth.account.sign_transaction(tx2, PRIVATE_KEY)
        h2 = w3.eth.send_raw_transaction(s2.raw_transaction)
        estado["ultimo_erro"] = f"VENDA REAL ENVIADA: {h2.hex()} - Veja na BscScan"
        return True
    except Exception as e:
        estado["ultimo_erro"] = f"ERRO: {str(e)[:500]}"
        return False

def loop_bot():
    while True:
        preco = pega_preco()
        estado["preco"] = preco
        for g in estado["grids"]:
            if preco >= g["venda"] and g["status"] == "AGUARDANDO":
                if vender_real(0.1):
                    if "VENDA REAL ENVIADA" in estado["ultimo_erro"]:
                        g["status"] = "VENDIDO REAL"
                        estado["vendidos"] += 1
                break
        time.sleep(15)

threading.Thread(target=loop_bot, daemon=True).start()

@app.route("/dashboard")
def dashboard():
    html = f"<html><head><meta http-equiv='refresh' content='5'></head><body style='background:#111;color:#fff;font-family:Arial;padding:10px;word-break:break-all'>"
    html += f"<h2>VENDA REAL - Conta: {ACCOUNT}</h2><div style='background:#222;padding:10px;border-left:4px solid #0f0'>Preco UNI: ${estado['preco']:.4f}</div>"
    html += f"<div style='background:#331111;padding:10px;margin:10px 0;border-left:4px solid #f00'>{estado['ultimo_erro']}</div>"
    for g in estado["grids"]:
        html += f"<div>Grid {g['n']}: Venda ${g['venda']} -> {g['status']}</div>"
    html += "</body></html>"
    return html

@app.route("/")
def home(): return "Rodando LlamaRPC"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
