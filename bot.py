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

# GRID CONFIG - COMPRA E VENDA INFINITO
GRID_SIZE = 20
GRID_SPACING = 0.20
QTD_POR_GRID = 0.80
PRECO_BASE = 7.03

estado = {"preco":7.06,"bnb":0,"uni":0,"usdt":0,"msg":"GRID BAIXA TAXA INICIANDO","grids":[]}
for i in range(1, GRID_SIZE+1):
    preco = round(PRECO_BASE + (i-1)*GRID_SPACING, 2)
    estado["grids"].append({"n":i,"preco":preco,"qtd":QTD_POR_GRID,"status":"NEUTRO","tx":"","tipo":""})

def pega_preco():
    try: return float(requests.get("https://api.binance.com/api/v3/ticker/price?symbol=UNIUSDT",timeout=5).json()['price'])
    except: return estado["preco"]

def get_bals():
    try:
        bnb = w3.eth.get_balance(ACCOUNT) / 1e18
        abi = '[{"constant":true,"inputs":[{"name":"_owner","type":"address"}],"name":"balanceOf","outputs":[{"name":"balance","type":"uint256"}],"type":"function"}]'
        uni_c = w3.eth.contract(address=UNI, abi=abi)
        usdt_c = w3.eth.contract(address=USDT, abi=abi)
        uni = uni_c.functions.balanceOf(ACCOUNT).call() / 1e18
        usdt = usdt_c.functions.balanceOf(ACCOUNT).call() / 1e18
        return bnb, uni, usdt
    except: return estado["bnb"], estado["uni"], estado["usdt"]

# FUNCAO CORRIGIDA - TAXA $0.01 IGUAL SEU PC
def swap_real(token_in, token_out, qtd):
    pk = os.environ.get("PRIVATE_KEY","").strip()
    if not pk: return False, "SEM PRIVATE_KEY"
    if not pk.startswith("0x"): pk = "0x"+pk
    try:
        erc20_abi = '[{"constant":false,"inputs":[{"name":"spender","type":"address"},{"name":"value","type":"uint256"}],"name":"approve","outputs":[{"name":"","type":"bool"}],"type":"function"},{"constant":true,"inputs":[{"name":"_owner","type":"address"},{"name":"_spender","type":"address"}],"name":"allowance","outputs":[{"name":"","type":"uint256"}],"type":"function"}]'
        router_abi = '[{"inputs":[{"internalType":"uint256","name":"amountIn","type":"uint256"},{"internalType":"uint256","name":"amountOutMin","type":"uint256"},{"internalType":"address[]","name":"path","type":"address[]"},{"internalType":"address","name":"to","type":"address"},{"internalType":"uint256","name":"deadline","type":"uint256"}],"name":"swapExactTokensForTokens","outputs":[{"internalType":"uint256[]","name":"amounts","type":"uint256[]"}],"stateMutability":"nonpayable","type":"function"}]'
        tk_in_c = w3.eth.contract(address=token_in, abi=erc20_abi)
        router_c = w3.eth.contract(address=ROUTER, abi=router_abi)
        
        amount_in = int(qtd * 1e18)
        allowance = tk_in_c.functions.allowance(ACCOUNT, ROUTER).call()
        if allowance < amount_in:
            tx_ap = tk_in_c.functions.approve(ROUTER, 2**256-1).build_transaction({
                'from': ACCOUNT, 
                'gas': 65000, 
                'gasPrice': w3.to_wei('0.05','gwei'),
                'nonce': w3.eth.get_transaction_count(ACCOUNT)
            })
            s = w3.eth.account.sign_transaction(tx_ap, private_key=pk)
            h = w3.eth.send_raw_transaction(s.rawTransaction)
            w3.eth.wait_for_transaction_receipt(h, timeout=60)
            time.sleep(2)

        path = [token_in, WBNB, token_out]
        deadline = int(time.time()) + 600
        tx_sw = router_c.functions.swapExactTokensForTokens(amount_in, 0, path, ACCOUNT, deadline).build_transaction({
            'from': ACCOUNT, 
            'gas': 185000,
            'gasPrice': w3.to_wei('0.05','gwei'),
            'nonce': w3.eth.get_transaction_count(ACCOUNT)
        })
        s_sw = w3.eth.account.sign_transaction(tx_sw, private_key=pk)
        h_sw = w3.eth.send_raw_transaction(s_sw.rawTransaction)
        w3.eth.wait_for_transaction_receipt(h_sw, timeout=120)
        return True, h_sw.hex()
    except Exception as e:
        return False, str(e)[:250]

def loop():
    while True:
        try:
            preco = pega_preco()
            bnb, uni, usdt = get_bals()
            estado["preco"]=preco; estado["bnb"]=bnb; estado["uni"]=uni; estado["usdt"]=usdt
            acao = ""
            for g in estado["grids"]:
                if preco >= g["preco"] and g["tipo"] != "VENDIDO":
                    if uni >= g["qtd"]:
                        g["status"]="VENDENDO $0.01..."
                        ok, res = swap_real(UNI, USDT, g["qtd"])
                        if ok: g["status"]=f"VENDIDO ${g['preco']}"; g["tx"]=res; g["tipo"]="VENDIDO"; acao=f"VENDEU Grid {g['n']} TAXA $0.01"
                        else: g["status"]=f"ERRO VENDA: {res}"
                if preco <= (g["preco"] - GRID_SPACING) and g["tipo"] == "VENDIDO":
                    qtd_usdt_needed = g["qtd"] * g["preco"]
                    if usdt >= qtd_usdt_needed * 0.9:
                        g["status"]="COMPRANDO $0.01..."
                        ok, res = swap_real(USDT, UNI, qtd_usdt_needed)
                        if ok: g["status"]=f"COMPRADO ${g['preco']:.2f}"; g["tx"]=res; g["tipo"]="COMPRADO"; acao=f"COMPROU Grid {g['n']}"
                        else: g["status"]=f"ERRO COMPRA: {res}"
                    else:
                        g["status"]=f"VENDIDO - Aguarda queda p/ recomprar (USDT {usdt:.2f})"

            has_key = len(os.environ.get("PRIVATE_KEY",""))>10
            estado["msg"]=f"GRID BAIXA TAXA {'KEY OK' if has_key else 'SEM KEY'} | BNB:{bnb:.5f} UNI:{uni:.3f} USDT:{usdt:.2f} | UNI=${preco:.4f} {acao}"
            time.sleep(15)
        except Exception as e:
            estado["msg"]=f"Erro: {e}"
            time.sleep(10)

threading.Thread(target=loop,daemon=True).start()

@app.route("/dashboard")
def dash():
    h=f"<html><head><meta http-equiv='refresh' content='10'><style>body{{background:#111;color:#0f0;font-family:monospace;padding:12px}} .ok{{background:#0f0;color:#000;padding:10px}}</style></head><body>"
    h+=f"<h2>♻️ BOT GRID $0.01 TAXA BAIXA</h2><div class='ok'>{estado['msg']}</div>"
    h+=f"<div style='color:#fff;margin-top:10px'>BNB:{estado['bnb']:.5f} | UNI:{estado['uni']:.4f} | USDT:{estado['usdt']:.2f} | Preco:${estado['preco']:.4f}</div><br>"
    for g in estado["grids"]:
        cor = "#ff4444" if "VENDIDO" in g["status"] else "#00ff88" if "COMPRADO" in g["status"] else "#ffff00"
        link = f" <a style='color:#0ff' href='https://bscscan.com/tx/{g['tx']}' target='_blank'>BscScan</a>" if g["tx"] else ""
        h+=f"<div style='color:{cor};border-bottom:1px solid #333;padding:6px'>Grid {g['n']}: ${g['preco']:.2f} | {g['qtd']} UNI -> {g['status']}{link}</div>"
    h+=f"<br><div style='color:#888'>Taxa configurada: 0.05 Gwei ~ $0.01 por trade (51x mais barato)</div></body></html>"
    return h
@app.route("/")
def home(): return "Grid bot taxa baixa ativo"
if __name__=="__main__": app.run(host="0.0.0.0",port=10000)
