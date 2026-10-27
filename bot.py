from flask import Flask
import requests, time, threading, json
app = Flask(__name__)

ACCOUNT = "0x8AEE0c5120f326C2389E3B6affa39E3BEBe82Fd3"
ACCOUNT_LC = ACCOUNT.lower()
UNI = "0xBf5140A22578168FD562DCcF235E5D43A02Ce9B1"

RPCS = [
    "https://bsc-dataseed.binance.org",
    "https://bsc-dataseed1.binance.org",
    "https://bsc.publicnode.com",
    "https://1rpc.io/bnb",
    "https://rpc.ankr.com/bsc",
    "https://bsc.meowrpc.com"
]

estado = {"preco": 7.06, "msg": "Testando RPCs...", "grids":[]}
for i in range(1,21):
    estado["grids"].append({"n":i,"venda":round(6.83+i*0.20,2),"status":"AGUARDANDO"})

def call_token_balance(rpc):
    data = "0x70a08231" + ACCOUNT_LC[2:].zfill(64)
    payload = {"jsonrpc":"2.0","id":1,"method":"eth_call","params":[{"to":UNI,"data":data},"latest"]}
    r = requests.post(rpc, json=payload, timeout=8)
    j = r.json()
    result = j.get("result","0x0")
    if not result or result=="0x":
        return 0, result
    try:
        val = int(result,16)/1e18
        return val, result
    except:
        return 0, result

def call_bnb(rpc):
    payload = {"jsonrpc":"2.0","id":1,"method":"eth_getBalance","params":[ACCOUNT,"latest"]}
    r = requests.post(rpc, json=payload, timeout=8).json()
    return int(r["result"],16)/1e18

def get_all():
    logs=[]
    uni_final=0
    bnb_final=0
    for rpc in RPCS:
        try:
            bnb = call_bnb(rpc)
            uni, raw = call_token_balance(rpc)
            logs.append(f"{rpc.split('//')[1][:18]} -> BNB:{bnb:.5f} UNI:{uni:.4f} RAW:{raw[:18]}")
            if uni>0:
                uni_final=uni
                bnb_final=bnb
                break
            if bnb>0 and uni_final==0:
                bnb_final=bnb
                # guarda mesmo se UNI 0, pra tentar próximo RPC
                uni_final=uni
        except Exception as e:
            logs.append(f"{rpc[:20]} ERRO:{str(e)[:80]}")
    if uni_final==0 and bnb_final>0:
        # se todos deram 0, mostra todos os logs pra debugar
        return f"RPCs testados mas UNI=0 - { ' | '.join(logs) } | BNB:{bnb_final:.5f} | UNI lido:0 | Contrato {UNI} | Isso significa que na blockchain BSC essa carteira tem 0 UNI desse contrato. Verifique se Trust está em outra carteira. Carteira {ACCOUNT}"
    return f"OK! BNB:{bnb_final:.5f} UNI:{uni_final:.4f} | {' | '.join(logs)}"

def pega_preco():
    try:
        r=requests.get("https://api.binance.com/api/v3/ticker/price?symbol=UNIUSDT",timeout=5)
        return float(r.json()['price'])
    except: return estado["preco"]

def loop():
    while True:
        estado["preco"]=pega_preco()
        estado["msg"]=get_all()
        time.sleep(12)

threading.Thread(target=loop,daemon=True).start()

@app.route("/dashboard")
def dash():
    h=f"<html><head><meta http-equiv='refresh' content='6'></head><body style='background:#111;color:#0f0;font-family:monospace;padding:10px;word-break:break-all'>"
    h+=f"<h2>VENDA REAL - {ACCOUNT}</h2><div style='background:#222;padding:10px;border-left:4px solid #0f0'>Preco:${estado['preco']:.4f}<br><br>{estado['msg']}</div><br>"
    for g in estado["grids"]:
        h+=f"<div>Grid {g['n']}: ${g['venda']} -> {g['status']}</div>"
    h+="</body></html>"
    return h
@app.route("/")
def home(): return "ok"
if __name__=="__main__":
    app.run(host="0.0.0.0",port=10000)
