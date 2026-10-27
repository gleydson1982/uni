from flask import Flask
import requests
import time
import threading
import os
from web3 import Web3

app = Flask(__name__)

# --- CONFIG BSC ---
BSC_RPC = "https://bsc-dataseed.binance.org/"
w3 = Web3(Web3.HTTPProvider(BSC_RPC))

PRIVATE_KEY = os.getenv("PRIVATE_KEY")
ACCOUNT = w3.eth.account.from_key(PRIVATE_KEY).address if PRIVATE_KEY else "SEM CHAVE"
print(f"Conta carregada: {ACCOUNT}")

# CONTRATOS CORRETOS NA BSC
UNI_BSC = "0xBf5140A22578168FD562DCcF235E5D43A02Ce9B5"  # UNI BSC
USDT_BSC = "0x55d398326f99059fF775485246999027B3197955" # USDT BSC
ROUTER_V2 = "0x10ED43C718714eb63d5aA57B78B54704E256024E" # Pancake Router V2

ROUTER_ABI = '[{"inputs":[{"internalType":"uint256","name":"amountIn","type":"uint256"},{"internalType":"uint256","name":"amountOutMin","type":"uint256"},{"internalType":"address[]","name":"path","type":"address[]"},{"internalType":"address","name":"to","type":"address"},{"internalType":"uint256","name":"deadline","type":"uint256"}],"name":"swapExactTokensForTokens","outputs":[{"internalType":"uint256[]","name":"amounts","type":"uint256[]"}],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"address","name":"owner","type":"address"},{"internalType":"address","name":"spender","type":"address"}],"name":"allowance","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"address","name":"spender","type":"address"},{"internalType":"uint256","name":"amount","type":"uint256"}],"name":"approve","outputs":[{"internalType":"bool","name":"","type":"bool"}],"stateMutability":"nonpayable","type":"function"}]'

estado = {
    "preco": 7.05, "base": 6.83, "vendidos": 0, "lucro": 0,
    "status": "Rodando VENDA REAL", "ultimo_erro": "Iniciando...",
    "inicio": time.time(), "grids": []
}

# Cria os 20 grids
for i in range(1, 21):
    estado["grids"].append({
        "n": i, 
        "compra": round(6.83 - (i*0.20),2), 
        "venda": round(6.83 + (i*0.20),2), 
        "status": "AGUARDANDO"
    })

def pega_preco():
    try:
        r = requests.get("https://api.binance.com/api/v3/ticker/price?symbol=UNIUSDT", timeout=5)
        return float(r.json()['price'])
    except:
        return estado["preco"]

def vender_real(qtd_uni):
    try:
        if not PRIVATE_KEY:
            estado["ultimo_erro"] = "ERRO: Sem PRIVATE_KEY"
            return False
            
        uni = w3.eth.contract(address=Web3.to_checksum_address(UNI_BSC), abi=ROUTER_ABI)
        router = w3.eth.contract(address=Web3.to_checksum_address(ROUTER_V2), abi=ROUTER_ABI)
        
        # 1. Verifica se precisa aprovar
        allowance = uni.functions.allowance(ACCOUNT, ROUTER_V2).call()
        amount_in_wei = w3.to_wei(qtd_uni, 'ether')
        
        if allowance < amount_in_wei:
            estado["ultimo_erro"] = f"Aprovando UNI..."
            tx_approve = uni.functions.approve(ROUTER_V2, 2**256-1).build_transaction({
                'from': ACCOUNT,
                'gas': 100000,
                'gasPrice': w3.to_wei('1', 'gwei'),
                'nonce': w3.eth.get_transaction_count(ACCOUNT)
            })
            signed = w3.eth.account.sign_transaction(tx_approve, PRIVATE_KEY)
            tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
            estado["ultimo_erro"] = f"Aprovado! Hash: {tx_hash.hex()[:10]}..."
            time.sleep(8) # espera aprovar

        # 2. Vende de verdade
        path = [Web3.to_checksum_address(UNI_BSC), Web3.to_checksum_address(USDT_BSC)]
        deadline = int(time.time()) + 600
        
        tx = router.functions.swapExactTokensForTokens(
            amount_in_wei, 0, path, ACCOUNT, deadline
        ).build_transaction({
            'from': ACCOUNT,
            'gas': 300000,
            'gasPrice': w3.to_wei('1', 'gwei'),
            'nonce': w3.eth.get_transaction_count(ACCOUNT)
        })
        signed = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        estado["ultimo_erro"] = f"VENDA REAL ENVIADA: {tx_hash.hex()}"
        print(f"Venda enviada: {tx_hash.hex()}")
        return True
        
    except Exception as e:
        estado["ultimo_erro"] = f"Erro na venda: {str(e)[:200]}"
        print(f"Erro: {e}")
        return False

def loop_bot():
    while True:
        try:
            preco = pega_preco()
            estado["preco"] = preco
            
            for g in estado["grids"]:
                if preco >= g["venda"] and g["status"] == "AGUARDANDO":
                    sucesso = vender_real(0.5) # vende 0.5 UNI por grid
                    if sucesso:
                        g["status"] = "VENDIDO REAL"
                        estado["vendidos"] += 1
                        estado["lucro"] += 0.20
                    break
        except Exception as e:
            estado["ultimo_erro"] = str(e)
        
        time.sleep(15)

threading.Thread(target=loop_bot, daemon=True).start()

@app.route("/")
def home():
    return f"Bot VENDA REAL rodando! Conta: {ACCOUNT} | Preco: ${estado['preco']}"

@app.route("/dashboard")
def dashboard():
    uptime = int(time.time() - estado["inicio"])
    html = f"""
    <html>
    <head><meta http-equiv='refresh' content='5'>
    <style>
        body{{background:#111;color:#fff;font-family:Arial;padding:10px}}
        .box{{background:#222;padding:15px;border-radius:10px;margin-bottom:10px;border-left:4px solid #0f0}}
        .erro{{background:#331111;border-left:4px solid #f00}}
        .grid{{background:#1a1a1a;padding:8px;margin:4px 0;border-radius:5px}}
    </style></head><body>
    <h2>UNI/USDT GRID - VENDA REAL NA BSC</h2>
    <div class='box'>Conta: {ACCOUNT}<br>Preco ATUAL (Binance): ${estado['preco']:.4f}<br>Uptime: {uptime}s</div>
    <div class='box erro'>STATUS / ULTIMO TX: {estado['ultimo_erro']}</div>
    <div class='box'>Vendidos: {estado['vendidos']}/20 | Lucro estimado: ${estado['lucro']:.2f}</div>
    <h3>Grids:</h3>
    {''.join([f"<div class='grid'>Grid {g['n']}: Compra ${g['compra']} | Venda ${g['venda']} -> <b>{g['status']}</b></div>" for g in estado['grids']])}
    </body></html>
    """
    return html

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
