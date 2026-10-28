from flask import Flask
import os, requests, time, threading, json
from web3 import Web3
from datetime import datetime
app = Flask(__name__)
ACCOUNT = Web3.to_checksum_address("0x8AEE0c5120f326C2389E3B6affa39E3BEBe82Fd3")
UNI = Web3.to_checksum_address("0xBf5140A22578168FD562DCcF235E5D43A02Ce9B1")
USDT = Web3.to_checksum_address("0x55d398326f99059fF775485246999027B3197955")
ROUTER = Web3.to_checksum_address("0x10ED43C718714eb63d5aA57B78B54704E256024E")
WBNB = Web3.to_checksum_address("0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c")
RPC = "https://bsc-dataseed.binance.org"
w3 = Web3(Web3.HTTPProvider(RPC))
GRID_SIZE=20
GRID_SPACING=0.20
QTD_POR_GRID=0.80
PRECO_BASE=7.03
ARQ_ESTADO="estado.json"

def carregar_estado():
    if os.path.exists(ARQ_ESTADO):
        try:
            with open(ARQ_ESTADO,"r") as f: return json.load(f)
        except: pass
    # estado inicial
    grids=[]
    for i in range(1, GRID_SIZE+1):
        pv=round(PRECO_BASE + (i-1)*GRID_SPACING,2)
        pc=round(pv-GRID_SPACING,2)
        grids.append({"n":i,"venda":pv,"compra":pc,"qtd":QTD_POR_GRID,"status":"NEUTRO","tx":"","tipo":"","vezes":0,"lucro":0.0,"ultima_compra":0.0})
    return {"preco":7.06,"bnb":0,"uni":0,"usdt":0,"msg":"BOT INICIANDO","grids":grids,"trades":[],"lucro_total":0.0,"lucro_mes":0.0,"lucro_ano":0.0}

def salvar_estado():
    try:
        with open(ARQ_ESTADO,"w") as f: json.dump(estado,f)
    except: pass

estado=carregar_estado()

def pega_preco():
    try: return float(requests.get("https://api.binance.com/api/v3/ticker/price?symbol=UNIUSDT",timeout=5).json()['price'])
    except: return estado["preco"]

def get_bals():
    try:
        bnb=w3.eth.get_balance(ACCOUNT)/1e18
        abi='[{"constant":true,"inputs":[{"name":"_owner","type":"address"}],"name":"balanceOf","outputs":[{"name":"balance","type":"uint256"}],"type":"function"}]'
        uni_c=w3.eth.contract(address=UNI,abi=abi)
        usdt_c=w3.eth.contract(address=USDT,abi=abi)
        uni=uni_c.functions.balanceOf(ACCOUNT).call()/1e18
        usdt=usdt_c.functions.balanceOf(ACCOUNT).call()/1e18
        return bnb,uni,usdt
    except: return estado["bnb"],estado["uni"],estado["usdt"]

def swap_real(token_in,token_out,qtd):
    pk=os.environ.get("PRIVATE_KEY","").strip()
    if not pk: return False,"SEM PRIVATE_KEY"
    if not pk.startswith("0x"): pk="0x"+pk
    try:
        erc20_abi='[{"constant":false,"inputs":[{"name":"spender","type":"address"},{"name":"value","type":"uint256"}],"name":"approve","outputs":[{"name":"","type":"bool"}],"type":"function"},{"constant":true,"inputs":[{"name":"_owner","type":"address"},{"name":"_spender","type":"address"}],"name":"allowance","outputs":[{"name":"","type":"uint256"}],"type":"function"}]'
        router_abi='[{"inputs":[{"internalType":"uint256","name":"amountIn","type":"uint256"},{"internalType":"uint256","name":"amountOutMin","type":"uint256"},{"internalType":"address[]","name":"path","type":"address[]"},{"internalType":"address","name":"to","type":"address"},{"internalType":"uint256","name":"deadline","type":"uint256"}],"name":"swapExactTokensForTokens","outputs":[{"internalType":"uint256[]","name":"amounts","type":"uint256[]"}],"stateMutability":"nonpayable","type":"function"}]'
        tk_in_c=w3.eth.contract(address=token_in,abi=erc20_abi)
        router_c=w3.eth.contract(address=ROUTER,abi=router_abi)
        amount_in=int(qtd*1e18)
        allowance=tk_in_c.functions.allowance(ACCOUNT,ROUTER).call()
        if allowance < amount_in:
            tx_ap=tk_in_c.functions.approve(ROUTER,2**256-1).build_transaction({'from':ACCOUNT,'gas':65000,'gasPrice':w3.to_wei('0.05','gwei'),'nonce':w3.eth.get_transaction_count(ACCOUNT)})
            s=w3.eth.account.sign_transaction(tx_ap,private_key=pk)
            h=w3.eth.send_raw_transaction(s.rawTransaction)
            w3.eth.wait_for_transaction_receipt(h,timeout=60)
            time.sleep(2)
        path=[token_in,WBNB,token_out]
        deadline=int(time.time())+600
        tx_sw=router_c.functions.swapExactTokensForTokens(amount_in,0,path,ACCOUNT,deadline).build_transaction({'from':ACCOUNT,'gas':185000,'gasPrice':w3.to_wei('0.05','gwei'),'nonce':w3.eth.get_transaction_count(ACCOUNT)})
        s_sw=w3.eth.account.sign_transaction(tx_sw,private_key=pk)
        h_sw=w3.eth.send_raw_transaction(s_sw.rawTransaction)
        w3.eth.wait_for_transaction_receipt(h_sw,timeout=120)
        return True,h_sw.hex()
    except Exception as e: return False,str(e)[:250]

def registrar_trade(grid,tipo,preco,lucro=0):
    agora=datetime.now()
    estado["trades"].insert(0,{"data":agora.strftime("%d/%m %H:%M"),"mes":agora.month,"ano":agora.year,"grid":grid["n"],"tipo":tipo,"preco":preco,"qtd":grid["qtd"],"lucro":lucro,"tx":grid["tx"]})
    if len(estado["trades"])>100: estado["trades"]=estado["trades"][:100]
    if lucro>0:
        estado["lucro_total"]+=lucro
        estado["lucro_mes"]=sum(t["lucro"] for t in estado["trades"] if t["mes"]==agora.month and t["ano"]==agora.year)
        estado["lucro_ano"]=sum(t["lucro"] for t in estado["trades"] if t["ano"]==agora.year)
    salvar_estado()

def loop():
    while True:
        try:
            preco=pega_preco()
            bnb,uni,usdt=get_bals()
            estado["preco"]=preco; estado["bnb"]=bnb; estado["uni"]=uni; estado["usdt"]=usdt
            acao=""
            for g in estado["grids"]:
                if preco >= g["venda"] and g["tipo"] != "VENDIDO":
                    if uni >= g["qtd"]:
                        g["status"]=f"VENDENDO..."
                        ok,res=swap_real(UNI,USDT,g["qtd"])
                        if ok:
                            lucro=0
                            if g["ultima_compra"]>0:
                                lucro=round((g["venda"]-g["ultima_compra"])*g["qtd"],4)
                                g["lucro"]+=lucro; g["vezes"]+=1
                                registrar_trade(g,"VENDA",g["venda"],lucro)
                            else:
                                registrar_trade(g,"VENDA",g["venda"],0); g["vezes"]+=1
                            g["status"]=f"VENDIDO"; g["tx"]=res; g["tipo"]="VENDIDO"; acao=f"VENDEU G{g['n']} LUCRO ${lucro:.4f}"
                            salvar_estado()
                        else: g["status"]=f"ERRO: {res}"
                if preco <= g["compra"] and g["tipo"]=="VENDIDO":
                    need=g["qtd"]*g["compra"]
                    if usdt >= need*0.9:
                        g["status"]=f"COMPRANDO..."
                        ok,res=swap_real(USDT,UNI,need)
                        if ok:
                            g["ultima_compra"]=g["compra"]; g["status"]=f"COMPRADO"; g["tx"]=res; g["tipo"]="COMPRADO"
                            registrar_trade(g,"COMPRA",g["compra"],0); acao=f"COMPROU G{g['n']} a ${g['compra']}"
                            salvar_estado()
                        else: g["status"]=f"ERRO COMPRA: {res}"
            has_key=len(os.environ.get("PRIVATE_KEY",""))>10
            estado["msg"]=f"BOT TRAVADO PERSISTENTE {'KEY OK' if has_key else 'SEM KEY'} | BNB:{bnb:.5f} UNI:{uni:.3f} USDT:{usdt:.2f} | UNI=${preco:.4f} | {acao} | LUCRO TOTAL ${estado['lucro_total']:.4f}"
            time.sleep(12)
        except Exception as e:
            estado["msg"]=f"Erro: {e}"; time.sleep(10)

threading.Thread(target=loop,daemon=True).start()

@app.route("/dashboard")
def dash():
    h="""<html><head><meta http-equiv='refresh' content='10'><style>
    body{background:#0d1117;color:#c9d1d9;font-family:monospace;padding:12px}
    .ok{background:#238636;color:#fff;padding:12px;border-radius:8px}
    .card{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:12px;margin:8px 0}
    .grid-row{display:flex;justify-content:space-between;border-bottom:1px solid #21262d;padding:8px}
    .lucro{color:#3fb950;font-weight:bold} table{width:100%;border-collapse:collapse} th{color:#8b949e;text-align:left;padding:6px} td{padding:6px;border-bottom:1px solid #21262d}
    </style></head><body>"""
    h+=f"<h2>🔒 GRID UNI - BOT TRAVADO PERSISTENTE</h2><div class='ok'>{estado['msg']}</div>"
    h+=f"<div class='card'><b>CARTEIRA:</b> {ACCOUNT}<br>BNB: {estado['bnb']:.5f} | UNI: {estado['uni']:.4f} (${estado['uni']*estado['preco']:.2f}) | USDT: {estado['usdt']:.2f} | Preço UNI: ${estado['preco']:.4f}<br>"
    h+=f"<b style='color:#3fb950'>💰 LUCRO TOTAL: ${estado['lucro_total']:.4f} | MÊS: ${estado['lucro_mes']:.4f} | ANO: ${estado['lucro_ano']:.4f}</b></div>"
    h+=f"<div class='card'><b>GRID - 20 NÍVEIS ($0.20) - NÃO VENDE 2x O MESMO GRID</b><br>"
    h+=f"<div class='grid-row' style='color:#8b949e'><span>Grid</span><span>Venda / Compra</span><span>Status</span><span>Vezes / Lucro</span></div>"
    for g in estado["grids"]:
        cor="#f85149" if g["tipo"]=="VENDIDO" else "#3fb950" if g["tipo"]=="COMPRADO" else "#e3b341"
        link=f" <a style='color:#58a6ff' href='https://bscscan.com/tx/{g['tx']}' target='_blank'>Tx</a>" if g["tx"] else ""
        h+=f"<div class='grid-row'><span>G{g['n']}</span><span>V ${g['venda']:.2f} / C ${g['compra']:.2f}</span><span style='color:{cor}'>{g['status']}{link}</span><span class='lucro'>{g['vezes']}x / ${g['lucro']:.4f}</span></div>"
    h+=f"</div><div class='card'><b>📜 HISTÓRICO</b><table><tr><th>Data</th><th>Grid</th><th>Tipo</th><th>Preço</th><th>Qtd</th><th>Lucro</th></tr>"
    for t in estado["trades"][:20]:
        lc=f"${t['lucro']:.4f}" if t['lucro']>0 else "-"
        col="#3fb950" if t["tipo"]=="VENDA" else "#58a6ff"
        h+=f"<tr><td>{t['data']}</td><td>G{t['grid']}</td><td style='color:{col}'>{t['tipo']}</td><td>${t['preco']:.2f}</td><td>{t['qtd']}</td><td class='lucro'>{lc}</td></tr>"
    h+=f"</table></div><div style='color:#8b949e;margin-top:10px'>🔒 BOT TRAVADO PERSISTENTE - Não vende 2x mesmo após deploy | Taxa $0.01</div></body></html>"
    return h
@app.route("/")
def home(): return "Bot travado persistente"
if __name__=="__main__": app.run(host="0.0.0.0",port=10000)
