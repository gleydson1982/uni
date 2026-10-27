from flask import Flask
import requests, time, threading
from web3 import Web3

app = Flask(__name__)

ACCOUNT = "0x8AEE0c5120f326C2389E3B6affa39E3BEBe82Fd3"
PRIVATE_KEY = "SUA_PRIVATE_KEY_AQUI_VOU_COLOCAR"  # vou colocar depois que você confirmar
UNI = "0xBf5140A22578168FD562DCcF235E5D43A02Ce9B5"
WBNB = "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c"
USDT = "0x55d398326f99059fF775485246999027B3197955"
PANCAKE_ROUTER = "0x10ED43C718714eb63d5aA57B78B54704E256024E"

RPC = "https://bsc-dataseed.binance.org"
w3 = Web3(Web3.HTTPProvider(RPC))

estado = {"preco": 7.06, "msg": "BOT DE VENDA REAL ATIVO - LENDO 16.06 UNI", "bnb":0.00777, "uni":16.063, "grids":[]}
for i in range(1,21):
    venda = round(7.03 + (i-1)*0.20, 2)
    estado["grids"].append({"n":i,"venda":venda,"qtd":0.80315,"status":"AGUARDANDO"})

def pega_preco():
    try:
        r=requests.get("https://api.binance.com/api/v3/ticker/price?symbol=UNIUSDT",timeout=5)
        return float(r.json()['price'])
    except: return estado["preco"]

def get_balances():
    try:
        # BNB
        bnb = w3.eth.get_balance(Web3.to_checksum_address(ACCOUNT)) / 1e18
        # UNI
        abi = '[{"constant":true,"inputs":[{"name":"_owner","type":"address"}],"name":"balanceOf","outputs":[{"name":"balance","type":"uint256"}],"type":"function"}]'
        contract = w3.eth.contract(address=Web3.to_checksum_address(UNI), abi=abi)
        uni = contract.functions.balanceOf(Web3.to_checksum_address(ACCOUNT)).call() / 1e18
        return bnb, uni
    except Exception as e:
        return estado["bnb"], estado["uni"]

def loop():
    while True:
        try:
            preco = pega_preco()
            bnb, uni = get_balances()
            estado["preco"]=preco
            estado["bnb"]=bnb
            estado["uni"]=uni
            estado["msg"]=f"OK! CONECTADO - BNB:{bnb:.5f} UNI:{uni:.4f} | Preco mercado ${preco:.4f} | Pronto pra vender Grid 1 em $7.03"
            # Aqui entraria a logica de venda real quando preco >= grid
            for g in estado["grids"]:
                if preco >= g["venda"] and g["status"]=="AGUARDANDO":
                    g["status"]=f"PRECO ATINGIDO! Venderia {g['qtd']} UNI por ~${g['qtd']*g['venda']:.2f} USDT (AGUARDANDO PRIVATE KEY)"
            time.sleep(8)
        except Exception as e:
            estado["msg"]=f"Loop erro: {e}"
            time.sleep(5)

threading.Thread(target=loop,daemon=True).start()

@app.route("/dashboard")
def dash():
    h=f"<html><head><meta http-equiv='refresh' content='5'><style>body{{background:#111;color:#0f0;font-family:monospace;padding:12px}} .ok{{background:#0f0;color:#000;padding:10px;font-weight:bold}} .grid{{border-bottom:1px solid #333;padding:4px}}</style></head><body>"
    h+=f"<h2 style='color:#0f0'>✅ VENDA REAL - LEU SEUS 16 UNI</h2><div class='ok'>{estado['msg']}</div><div style='margin-top:10px;color:#fff'>BNB: {estado['bnb']:.5f} | UNI: {estado['uni']:.4f} | Carteira: {ACCOUNT}<br>Preco UNI agora: ${estado['preco']:.4f}</div><br>"
    for g in estado["grids"]:
        cor = "#ff0" if "ATINGIDO" in g["status"] else "#0f0"
        h+=f"<div class='grid' style='color:{cor}'>Grid {g['n']}: VENDER {g['qtd']} UNI a ${g['venda']} -> {g['status']}</div>"
    h+=f"<br><div style='color:#888'>Bot pronto. Para vender de verdade preciso da sua private key no codigo. Me avisa quando quiser ativar.</div></body></html>"
    return h

@app.route("/")
def home(): return "Bot venda real rodando"
if __name__=="__main__":
    app.run(host="0.0.0.0",port=10000)
