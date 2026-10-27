from flask import Flask
import requests, time, threading, os
app = Flask(__name__)

RPCS = ["https://bsc-dataseed.binance.org","https://bsc-dataseed1.binance.org"]
ACCOUNT = "0x8AEE0c5120f326C2389E3B6affa39E3BEBe82Fd3"
ACCOUNT_LC = ACCOUNT.lower()

# 2 contratos possíveis de UNI na BSC
UNI_TOKENS = [
 "0xBf5140A22578168FD562DCcF235E5D43A02Ce9B5".lower(),
 "0xfa7f8980b82d27e25093811d26411535ac6393c1".lower()
]

estado = {"preco": 7.05, "msg": "Iniciando...", "grids": []}
for i in range(1,21):
    estado["grids"].append({"n":i,"venda":round(6.83+i*0.20,2),"status":"AGUARDANDO"})

def get_balances_raw(rpc, wallet):
    # BNB
    payload = {"jsonrpc":"2.0","method":"eth_getBalance","params":[wallet,"latest"],"id":1}
    bnb = int(requests.post(rpc, json=payload, timeout=8).json()["result"],16)/1e18
    # UNI - tenta todos os contratos
    uni_total = 0
    detalhes = ""
    for token in UNI_TOKENS:
        data = "0x70a08231" + wallet[2:].zfill(64)
        payload = {"jsonrpc":"2.0","method":"eth_call","params":[{"to":token,"data":data},"latest"],"id":1}
        r = requests.post(rpc, json=payload, timeout=8).json()
        val = 0
        if "result" in r and r["result"] != "0x" and r["result"] != "0x0000000000000000000000000000000000000000000000000000000000000000":
            try: val = int(r["result"],16)/1e18
            except: val = 0
        uni_total += val
        detalhes += f" {token[:6]}:{val:.4f}"
    return bnb, uni_total, detalhes

def get_saldo():
    for rpc in RPCS:
        try:
            bnb, uni, det = get_balances_raw(rpc, ACCOUNT_LC)
            return f"CONECTADO OK! | RPC: {rpc} | BNB: {bnb:.5f} | UNI: {uni:.4f} | DET:{det} | Carteira: {ACCOUNT}"
        except Exception as e:
            last = f"{rpc} -> {str(e)[:150]}"
    return f"ERRO - {last}"

def pega_preco():
    try:
        r = requests.get("https://api.binance.com/api/v3/ticker/price?symbol=UNIUSDT", timeout=5)
        return float(r.json()['price'])
    except: return estado["preco"]

def loop():
    while True:
        estado["preco"] = pega_preco()
        estado["msg"] = get_saldo()
        time.sleep(10)

threading.Thread(target=loop, daemon=True).start()

@app.route("/dashboard")
def dash():
    h=f"<html><head><meta http-equiv='refresh' content='5'></head><body style='background:#111;color:#0f0;font-family:monospace;padding:10px;word-break:break-all'>"
    h+=f"<h2 style='color:#fff'>VENDA REAL - {ACCOUNT}</h2><div style='background:#222;padding:12px;border-left:4px solid #0f0'>Preco UNI: ${estado['preco']:.4f}<br>{estado['msg']}</div><br>"
    for g in estado["grids"]:
        h+=f"<div>Grid {g['n']}: ${g['venda']} -> {g['status']}</div>"
    h+="</body></html>"
    return h

@app.route("/")
def home(): return "Rodando"

if __name__=="__main__":
    app.run(host="0.0.0.0", port=10000)
