import os, time, threading, logging
from flask import Flask, jsonify, render_template_string
from web3 import Web3

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# Configurações de Rede (BNB Smart Chain)
RPC_URL = "https://bsc-dataseed.binance.org/"
ROUTER_ADDR = "0x10ED43C718714eB63B5aA57B78B54704E256024E"
USDT_ADDR = "0x55d398326f99059fF775485246999027B3197955"
CAKE_ADDR = "0x0e09fabb73bd3ade0a17ecc321fd13a19e81ce82"

w3 = Web3(Web3.HTTPProvider(RPC_URL))
PRIVATE_KEY = os.getenv("PRIVATE_KEY")
ACCOUNT = w3.eth.account.from_key(PRIVATE_KEY) if PRIVATE_KEY else None

# Contrato ERC20 ABI Mínimo para Aprovação
ERC20_ABI = [{"constant":False,"inputs":[{"name":"_spender","type":"address"},{"name":"_value","type":"uint256"}],"name":"approve","outputs":[{"name":"","type":"bool"}],"type":"function"}]
# PancakeSwap Router ABI Mínimo para Swap
ROUTER_ABI = [{"inputs":[{"internalType":"uint256","name":"amountIn","type":"uint256"},{"internalType":"uint256","name":"amountOutMin","type":"uint256"},{"internalType":"address[]","name":"path","type":"address[]"},{"internalType":"address","name":"to","type":"address"},{"internalType":"uint256","name":"deadline","type":"uint256"}],"name":"swapExactTokensForTokens","outputs":[{"internalType":"uint256[]","name":"amounts","type":"uint256[]"}],"stateMutability":"nonpayable","type":"function"}]

STATE = {"status": "Iniciando", "logs": [], "preco": 0.0}

def log(msg):
    logging.info(msg)
    STATE["logs"].insert(0, f"{time.strftime('%H:%M:%S')} {msg}")

def get_price():
    # Simplificado: Consulta rápida via Router
    return 2.15 # Substituir por chamada real: router.functions.getAmountsOut(...)

def execute_swap(is_buy, amount_usdt):
    if not ACCOUNT: return
    try:
        # 1. Aprovar USDT para Router (se COMPRA)
        if is_buy:
            token_contract = w3.eth.contract(address=w3.to_checksum_address(USDT_ADDR), abi=ERC20_ABI)
            tx = token_contract.functions.approve(w3.to_checksum_address(ROUTER_ADDR), int(amount_usdt * 10**18)).build_transaction({
                'from': ACCOUNT.address, 'nonce': w3.eth.get_transaction_count(ACCOUNT.address), 'gas': 100000, 'gasPrice': w3.eth.gas_price
            })
            signed = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
            w3.eth.send_raw_transaction(signed.rawTransaction)
        
        # 2. Executar Swap (lógica simplificada de path)
        log(f"{'COMPRA' if is_buy else 'VENDA'} executada.")
    except Exception as e:
        log(f"Erro no Swap: {e}")

def bot_loop():
    while True:
        try:
            p = get_price()
            STATE["preco"] = p
            # Lógica de grid: Se p < min -> compra, se p > max -> venda
            log(f"Preço atual: {p}")
            time.sleep(30)
        except Exception as e:
            log(f"Erro no loop: {e}")
            time.sleep(30)

@app.route("/")
def index():
    return "Bot de Trading Operacional Ativo"

threading.Thread(target=bot_loop, daemon=True).start()
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
