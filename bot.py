from flask import Flask
import os, requests, time, threading
from web3 import Web3

app = Flask(__name__)

ACCOUNT = Web3.to_checksum_address("0x8AEE0c5120f326C2389E3B6affa39E3BEBe82Fd3")
UNI = Web3.to_checksum_address("0xBf5140A22578168FD562DCcF235E5D43A02Ce9B1")
USDT = Web3.to_checksum_address("0x55d398326f99059fF775485246999027B3197955")
ROUTER = Web3.to_checksum_address("0x10ED43C718714eb63d5aA57B78B54704E256024E")
WBNB = Web3.to_checksum_address("0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c")

RPC = "https://bsc-dataseed.binance.org"
w3 = Web3(Web3.HTTPProvider(RPC))

estado = {"preco":7.06,"bnb":0,"uni":16.063,"msg":"BOT AUTO VENDA REAL .env","grids":[]}
for i in range(1,21):
    v = round(7.03 + (i-1)*0.20, 2)
    estado["grids"].append({"n":i,"venda":v,"qtd":0.80315,"status":"AGUARDANDO","tx":""})

def pega_preco():
    try: return float(requests.get("https://api.binance.com/api/v3/ticker/price?symbol=UNIUSDT",timeout=5).json()['price'])
    except: return estado["preco"]

def get_bal():
    try:
        bnb = w3.eth.get_balance(ACCOUNT) / 1e18
        abi = '[{"constant":true,"inputs":[{"name":"_owner","type":"address"}],"name":"balanceOf","outputs":[{"name":"balance","type":"uint256"}],"type":"function"}]'
        c = w3.eth.contract(address=UNI, abi=abi)
        uni = c.functions.balanceOf(ACCOUNT).call() / 1e18
        return bnb, uni
    except: return estado["bnb"], estado["uni"]

def vender_real(qtd_uni):
    pk = os.environ.get("PRIVATE_KEY","").strip()
    if not pk: return False, "SEM PRIVATE_KEY no Environment"
    if not pk.startswith("0x"): pk = "0x"+pk
    try:
        erc20_abi = '[{"constant":false,"inputs":[{"name":"spender","type":"address"},{"name":"value","type":"uint256"}],"name":"approve","outputs":[{"name":"","type":"bool"}],"type":"function"},{"constant":true,"inputs":[{"name":"_owner","type":"address"},{"name":"_spender","type":"address"}],"name":"allowance","outputs":[{"name":"","type":"uint256"}],"type":"function"}]'
        router_abi = '[{"inputs":[{"internalType":"uint256","name":"amountIn","type":"uint256"},{"internalType":"uint256","name":"amountOutMin","type":"uint256"},{"internalType":"address[]","name":"path","type":"address[]"},{"internalType":"address","name":"to","type":"address"},{"internalType":"uint256","name":"deadline","type":"uint256"}],"name":"swapExactTokensForTokens","outputs":[{"internalType":"uint256[]","name":"amounts","type":"uint256[]"}],"stateMutability":"nonpayable","type":"function"}]'
        uni_c = w3.eth.contract(address=UNI, abi=erc20_abi)
        router_c = w3.eth.contract(address=ROUTER, abi=router_abi)
        amount_in = int(qtd_uni * 1e18)
        allowance = uni_c.functions.allowance(ACCOUNT, ROUTER).call()
        if allowance < amount_in:
            tx_approve = uni_c.functions.approve(ROUTER, 2**256-1).build_transaction({'from': ACCOUNT, 'gas': 100000, 'gasPrice': w3.to_wei('3','gwei'), 'nonce': w3.eth.get_transaction_count(ACCOUNT)})
            signed = w3.eth.account.sign_transaction(tx_approve, private_key=pk)
            tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
            w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
            time.sleep(3)
        path = [UNI, WBNB, USDT]
        deadline = int(time.time()) + 600
        tx_swap = router_c.functions.swapExactTokensForTokens(amount_in, 0, path, ACCOUNT, deadline).build_transaction({'from': ACCOUNT, 'gas': 300000, 'gasPrice': w3.to_wei('3','gwei'), 'nonce': w3.eth.get_transaction_count(ACCOUNT)})
        signed_swap = w3.eth.account.sign_transaction(tx_swap, private_key=pk)
        tx_hash_swap = w3.eth.send_raw_transaction(signed_swap.rawTransaction)
        w3.eth.wait_for_transaction_receipt(tx_hash_swap, timeout=120)
        return True, tx_hash_swap.hex()
    except Exception as e:
        return False, str(e)[:200]

def loop():
    while True:
        try:
            preco = pega_preco()
            bnb, uni = get_bal()
            estado["preco"]=preco
            estado["bnb"]=bnb
            estado["uni"]=uni
            has_key = len(os.environ.get("PRIVATE_KEY",""))>10
            estado["msg"]=f"AUTO VENDA REAL {'KEY OK' if has_key else 'SEM KEY'} | BNB:{bnb:.5f} UNI:{uni:.4f} | UNI=${preco:.4f}"
            for g in estado["grids"]:
                if preco >= g["venda"] and g["status"]=="AGUARDANDO":
                    if uni < g["qtd"]: g["status"]=f"SALDO INSUFICIENTE {uni:.4f}"
                    else:
                        g["status"]="VENDENDO..."
                        ok, result = vender_real(g["qtd"])
                        if ok: g["status"]=f"VENDIDO! Tx:{result[:20]}..."; g["tx"]=result
                        else: g["status"]=f"ERRO: {result}"
            time.sleep(15)
        except Exception as e:
            estado["msg"]=f"Erro loop: {e}"
            time.sleep(10)

threading.Thread(target=loop,daemon=True).start()

@app.route("/dashboard")
def dash():
    h=f"<html><head><meta http-equiv='refresh' content='10'><style>body{{background:#111;color:#0f0;font-family:monospace;padding:12px}} .ok{{background:#0f0;color:#000;padding:10px}} .sell{{background:#ff4444;color:#fff;padding:10px}}</style></head><body>"
    h+=f"<h2>🤖 BOT VENDA REAL - CARTEIRA BOT</h2><div class='ok'>{estado['msg']}</div><div style='color:#fff;margin-top:10px'>Carteira: {ACCOUNT}<br>BNB:{estado['bnb']:.5f} | UNI:{estado['uni']:.4f} | Preco:${estado['preco']:.4f}</div><br>"
    for g in estado["grids"]:
        cor = "#ff4444" if "VENDIDO" in g["status"] else "#ff0" if "VENDENDO" in g["status"] else "#0f0"
        link = f" <a style='color:#0ff' href='https://bscscan.com/tx/{g['tx']}' target='_blank'>BscScan</a>" if g["tx"] else ""
        h+=f"<div style='color:{cor};border-bottom:1px solid #333;padding:6px'>Grid {g['n']}: VENDER {g['qtd']} UNI a ${g['venda']} -> {g['status']}{link}</div>"
    h+=f"<br><div style='color:#888'>Venda automatica via PancakeSwap quando UNI >= Grid. Chave lida do .env.</div></body></html>"
    return h
@app.route("/")
def home(): return "Bot venda real ativo"
if __name__=="__main__": app.run(host="0.0.0.0",port=10000)
