from flask import Flask
import requests, time, threading
app = Flask(__name__)

ACCOUNT = "0x8AEE0c5120f326C2389E3B6affa39E3BEBe82Fd3"
UNI_CONTRACT = "0xBf5140A22578168FD562DCcF235E5D43A02Ce9B1"

estado = {"preco": 7.06, "msg": "Iniciando...", "grids": []}
for i in range(1,21):
    estado["grids"].append({"n":i,"venda":round(6.83+i*0.20,2),"status":"AGUARDANDO"})

def get_saldo_bscscan():
    try:
        # Tenta BscScan API direto
        url = f"https://api.bscscan.com/api?module=account&action=tokenbalance&contractaddress={UNI_CONTRACT}&address={ACCOUNT}&tag=latest"
        r = requests.get(url, timeout=10).json()
        uni = 0
        if r.get("status") == "1":
            uni = int(r["result"]) / 1e18
        # BNB
        url2 = f"https://api.bscscan.com/api?module=account&action=balance&address={ACCOUNT}&tag=latest"
        r2 = requests.get(url2, timeout=10).json()
        bnb = int(r2["result"]) / 1e18 if r2.get("status")=="1" else 0
        return f"CONECTADO BSCSCAN OK! | BNB: {bnb:.5f} | UNI: {uni:.4f} | Contrato: {UNI_CONTRACT[:10]}... | Carteira: {ACCOUNT}"
    except Exception as e:
        return f"ERRO BSCSCAN: {str(e)[:200]}"

def pega_preco():
    try:
        r = requests.get("https://api.binance.com/api/v3/ticker/price?symbol=UNIUSDT", timeout=5)
        return float(r.json()['price'])
    except: return estado["preco"]

def loop():
    while True:
        estado["preco"] = pega_preco()
        estado["msg"] = get_saldo_bscscan()
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
