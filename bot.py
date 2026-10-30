# CORRIGIDO - UNI GRID COM TRAVAS
from flask import Flask
import os, requests, time, threading, json
from web3 import Web3
from datetime import datetime

app = Flask(__name__)
GOOGLE_SHEET_URL = os.environ.get("GOOGLE_SHEET_URL", "").strip() or os.environ.get("GOOGLE_SHEETS_URL", "").strip()

def salva_na_planilha(tipo, preco, qtd, lucro_trade, hash_tx, usdt_atual, uni_atual):
    try:
        if not GOOGLE_SHEET_URL: return
        agora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        total = round(preco * qtd, 2)
        payload = {"data": agora,"tipo": tipo,"preco": preco,"qtd": qtd,"total": total,"lucro_trade": lucro_trade,"lucro_total": round(estado.get("lucro_total", 0), 2),"hash": str(hash_tx)[:66],"saldo_usdt": round(usdt_atual, 2),"saldo_uni": round(uni_atual, 4)}
        requests.post(GOOGLE_SHEET_URL, json=payload, timeout=8)
    except Exception as e:
        print(f"Erro planilha: {e}")

ACCOUNT = Web3.to_checksum_address("0x8AEE0c5120f326C2389E3B6affa39E3BEBe82Fd3")
UNI = Web3.to_checksum_address("0xBf5140A22578168FD562DCcF235E5D43A02Ce9B1")
USDT = Web3.to_checksum_address("0x55d398326f99059fF775485246999027B319DC7") # CORRIGIDO DC7
ROUTER = Web3.to_checksum_address("0x10ED43C718714eb63d5aA57B78B54704E256024E")
WBNB = Web3.to_checksum_address("0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c")
RPC = "https://bsc-dataseed.binance.org"
w3 = Web3(Web3.HTTPProvider(RPC))

GRID_SIZE = 20
GRID_SPACING = 0.20
GRID_START = 5.31
USDT_POR_GRID = 9.0
UNI_POR_GRID = 2.40247
ARQ_ESTADO = "estado.json"

# --- SUAS TRAVAS ---
MIN_BNB = 0.0005
GAS_ESCALA = [0.6, 0.8, 1.2] # CORRIGIDO - ANTES 0.1 DAVA FALHA E COMIA BNB

def pega_preco_agora():
    try:
        r=requests.get("https://api.binance.com/api/v3/ticker/price?symbol=UNIUSDT",timeout=4).json()
        if 'price' in r: return float(r['price']), "Binance", "OK"
    except: pass
    try:
        r=requests.get("https://api.coinbase.com/v2/prices/UNI-USD/spot",timeout=4).json()
        return float(r['data']['amount']), "Coinbase", "OK"
    except: pass
    try:
        r=requests.get("https://api.coingecko.com/api/v3/simple/price?ids=uniswap&vs_currencies=usd",timeout=5).json()
        return float(r['uniswap']['usd']), "CoinGecko", "OK"
    except: pass
    return 7.37, "CACHE", "FALHA"

def criar_grids(preco_atual):
    grids=[]
    for i in range(1, GRID_SIZE+1):
        preco = round(GRID_START + (i-1)*GRID_SPACING, 2)
        venda = round(preco+GRID_SPACING,2)
        if preco_atual >= preco:
            qtd = round(USDT_POR_GRID / preco, 4)
            grids.append({"n":i,"preco":preco,"venda":venda,"compra":preco,"qtd":qtd,"usdt":USDT_POR_GRID,"status":f"VENDIDO - Pronto p/ compra","tipo":"VENDIDO","vezes":0,"lucro":0.0,"ultima_compra":preco,"ultimo_tempo":0})
        else:
            grids.append({"n":i,"preco":preco,"venda":venda,"compra":preco,"qtd":UNI_POR_GRID,"usdt":0,"status":f"COMPRADO ${preco} - Pronto p/ venda","tipo":"COMPRADO","vezes":0,"lucro":0.0,"ultima_compra":preco,"ultimo_tempo":0})
    return grids

preco_init, fonte_init, status_init = pega_preco_agora()

# FORÇA RECRIAR GRID SE TIVER 0 USDT ERRADO
if os.path.exists(ARQ_ESTADO):
    os.remove(ARQ_ESTADO) # APAGA ESTADO VELHO COM G7 0 USDT

estado={"preco":preco_init,"preco_real":preco_init,"preco_fonte":fonte_init,"preco_update":datetime.now().strftime("%H:%M:%S"),"preco_status":status_init,"bnb":0.0063,"uni":24.0247,"usdt":90.4355,"msg":f"GRID NOVO COM G7 9 USDT - PRECO REAL ${preco_init}","grids":criar_grids(preco_init),"trades":[],"lucro_total":1.92}

def salvar():
    try:
        with open(ARQ_ESTADO,"w") as f: json.dump(estado,f)
    except: pass

def get_bals():
    try:
        bnb=w3.eth.get_balance(ACCOUNT)/1e18
        if bnb < MIN_BNB:
            print(f"⛔ TRAVADO BNB BAIXO {bnb:.6f}")
        abi='[{"constant":true,"inputs":[{"name":"_owner","type":"address"}],"name":"balanceOf","outputs":[{"name":"balance","type":"uint256"}],"type":"function"}]'
        uni_c=w3.eth.contract(address=UNI,abi=abi); usdt_c=w3.eth.contract(address=USDT,abi=abi)
        uni=uni_c.functions.balanceOf(ACCOUNT).call()/1e18
        usdt=usdt_c.functions.balanceOf(ACCOUNT).call()/1e18
        return bnb,uni,usdt
    except: return estado["bnb"],estado["uni"],estado["usdt"]

def swap_real(token_in,token_out,qtd):
    if token_in==USDT and qtd > 10.5: return False, f"TRAVA MAX $10"
    pk=os.environ.get("PRIVATE_KEY","").strip()
    if not pk: return False,"SEM PRIVATE_KEY"
    if not pk.startswith("0x"): pk="0x"+pk
    last_err = "sem tentativa"
    try:
        bnb_atual = w3.eth.get_balance(ACCOUNT)/1e18
        if bnb_atual < MIN_BNB:
            return False, f"TRAVADO BNB {bnb_atual:.6f} < {MIN_BNB} - RECARREGUE"
        erc20_abi='[{"constant":false,"inputs":[{"name":"spender","type":"address"},{"name":"value","type":"uint256"}],"name":"approve","outputs":[{"name":"","type":"bool"}],"type":"function"},{"constant":true,"inputs":[{"name":"_owner","type":"address"},{"name":"_spender","type":"address"}],"name":"allowance","outputs":[{"name":"","type":"uint256"}],"type":"function"}]'
        router_abi='[{"inputs":[{"internalType":"uint256","name":"amountIn","type":"uint256"},{"internalType":"uint256","name":"amountOutMin","type":"uint256"},{"internalType":"address[]","name":"path","type":"address[]"},{"internalType":"address","name":"to","type":"address"},{"internalType":"uint256","name":"deadline","type":"uint256"}],"name":"swapExactTokensForTokens","outputs":[{"internalType":"uint256[]","name":"amounts","type":"uint256[]"}],"stateMutability":"nonpayable","type":"function"}]'
        tk_in_c=w3.eth.contract(address=token_in,abi=erc20_abi)
        router_c=w3.eth.contract(address=ROUTER,abi=router_abi)
        amount_in=int(qtd*1e18)
        if tk_in_c.functions.allowance(ACCOUNT,ROUTER).call() < amount_in:
            for gas_gwei in GAS_ESCALA:
                try:
                    tx_ap=tk_in_c.functions.approve(ROUTER,2**256-1).build_transaction({'from':ACCOUNT,'gas':70000,'gasPrice':w3.to_wei(gas_gwei,'gwei'),'nonce':w3.eth.get_transaction_count(ACCOUNT)})
                    s=w3.eth.account.sign_transaction(tx_ap,private_key=pk)
                    h=w3.eth.send_raw_transaction(s.rawTransaction)
                    receipt=w3.eth.wait_for_transaction_receipt(h,timeout=90)
                    if receipt.status==1: break
                except Exception as e:
                    last_err=str(e)[:180]; time.sleep(1); continue
            time.sleep(2)
        path=[token_in,WBNB,token_out]
        for gas_gwei in GAS_ESCALA:
            try:
                tx_sw=router_c.functions.swapExactTokensForTokens(amount_in,0,path,ACCOUNT,int(time.time())+600).build_transaction({'from':ACCOUNT,'gas':250000,'gasPrice':w3.to_wei(gas_gwei,'gwei'),'nonce':w3.eth.get_transaction_count(ACCOUNT)})
                s_sw=w3.eth.account.sign_transaction(tx_sw,private_key=pk)
                h_sw=w3.eth.send_raw_transaction(s_sw.rawTransaction)
                receipt=w3.eth.wait_for_transaction_receipt(h_sw,timeout=120)
                if receipt.status==1: return True,h_sw.hex()
                else: last_err=f"tx reverted status 0 - {h_sw.hex()} - gas {gas_gwei} gwei"; time.sleep(1); continue
            except Exception as e:
                last_err=str(e)[:180] + f" gas {gas_gwei}"; time.sleep(1); continue
        return False, last_err
    except Exception as e:
        return False,str(e)[:180]

def loop():
    while True:
        try:
            preco,fonte,status = pega_preco_agora()
            bnb,uni,usdt=get_bals()
            estado["preco"]=preco; estado["preco_real"]=preco; estado["preco_fonte"]=fonte; estado["preco_update"]=datetime.now().strftime("%d/%m %H:%M:%S"); estado["preco_status"]=status
            estado["bnb"]=bnb; estado["uni"]=uni; estado["usdt"]=usdt
            agora=time.time()
            for g in estado["grids"]:
                if agora - g["ultimo_tempo"] < 180: continue
                if preco >= g["venda"] and g["tipo"]=="COMPRADO":
                    if uni >= g["qtd"]*0.9:
                        ok,res=swap_real(UNI,USDT,g["qtd"])
                        if ok:
                            lucro=(g["venda"] - g["ultima_compra"])*g["qtd"]
                            g["lucro"]+=lucro; g["tipo"]="VENDIDO"; g["status"]=f"VENDIDO +${lucro:.2f} - Pronto p/ compra"; g["vezes"]+=1; g["ultimo_tempo"]=agora
                            estado["trades"].insert(0,{"data":datetime.now().strftime("%d/%m %H:%M"),"tipo":"VENDA","preco":g["venda"],"qtd":g["qtd"],"lucro":lucro})
                            estado["lucro_total"]+=lucro; salva_na_planilha("VENDA", g["venda"], g["qtd"], lucro, res, usdt, uni); salvar()
                        else: estado["msg"]=f"VENDA G{g['n']} FALHOU - {res}"
                if preco <= g["preco"] and g["tipo"]=="VENDIDO":
                    need = g["usdt"]
                    if usdt >= need*0.9 and need <= 10.5:
                        ok,res=swap_real(USDT,UNI,need)
                        if ok:
                            g["ultima_compra"]=preco; g["tipo"]="COMPRADO"; g["status"]=f"COMPRADO ${preco} - Pronto p/ venda"; g["ultimo_tempo"]=agora
                            estado["trades"].insert(0,{"data":datetime.now().strftime("%d/%m %H:%M"),"tipo":"COMPRA","preco":preco,"qtd":g["qtd"],"lucro":0})
                            salva_na_planilha("COMPRA", preco, g["qtd"], 0, res, usdt, uni); salvar()
                        else: estado["msg"]=f"COMPRA G{g['n']} FALHOU - {res}"
            estado["msg"]=f"PRECO REAL ${preco:.4f} ({fonte}) | BNB:{bnb:.4f} UNI:{uni:.2f} USDT:{usdt:.2f} | Lucro ${estado['lucro_total']:.2f}"
            salvar(); time.sleep(12)
        except Exception as e:
            estado["msg"]=f"Erro loop {e}"; estado["preco_status"]=f"Erro {e}"[:120]; time.sleep(10)

threading.Thread(target=loop,daemon=True).start()

@app.route("/dashboard")
def dash():
    cor_status = "#22c55e" if estado.get("preco_status")=="OK" else "#ef4444"
    fonte = estado.get("preco_fonte","-"); update = estado.get("preco_update","-"); status = estado.get("preco_status","-"); preco_real = estado.get("preco_real", estado.get("preco",0))
    html=f"<html><head><meta http-equiv='refresh' content='5'><meta name='viewport' content='width=device-width'><style>body{{background:#0d0d0f;color:#fff;font-family:Arial;padding:12px}} .card{{background:#1a1a1e;border-radius:12px;padding:14px;margin:10px 0}} .row{{display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid #222;font-size:13px}} .grid2{{display:grid;grid-template-columns:1fr 1fr;gap:10px}} @media(max-width:700px){{.grid2{{grid-template-columns:1fr}}}}</style></head><body>"
    html+=f"<div class='card' style='display:flex;justify-content:space-between'><div><b>🤖 UNI GRID - TRAVA BNB ATIVA</b><br><span style='font-size:12px;background:#0f2a1a;color:#22c55e;padding:4px 8px;border-radius:20px'>● COMPRA E VENDE SOZINHO - NAO ZERA BNB</span></div><div style='text-align:right'>BNB {estado['bnb']:.4f}<br>UNI {estado['uni']:.2f}<br>USDT {estado['usdt']:.2f}</div></div>"
    html+=f"<div class='card' style='border:2px solid {cor_status}'><b>PREÇO REAL UNI</b><div style='display:flex;justify-content:space-between;margin-top:10px'><div><div style='font-size:36px;font-weight:bold;color:{cor_status}'>${preco_real:.4f}</div><div style='font-size:12px;color:#8b949e'>Fonte: {fonte} | Update: {update}</div></div><div style='text-align:right'><div style='font-size:12px;padding:6px 10px;border-radius:8px;background:#222;color:{cor_status}'><b>Status: {status}</b></div></div></div></div>"
    html+=f"<div class='grid2'><div class='card'><b>CARTEIRA</b><div class='row'><span>UNI</span><span>{estado['uni']:.4f} = ${estado['uni']*estado['preco']:.2f}</span></div><div class='row'><span>USDT</span><span>{estado['usdt']:.4f}</span></div><div style='background:#0f1e3a;border-radius:10px;padding:12px;margin-top:10px'><div style='color:#60a5fa;font-weight:bold'>SALDO USDT</div><div style='font-size:32px;color:#3b82f6;font-weight:bold'>${estado['usdt']:.2f}</div><div style='color:#8b949e;font-size:12px'>{estado['msg']}</div></div></div>"
    html+=f"<div class='card'><b>Lucro</b><div style='font-size:36px;color:#22c55e'>+${estado['lucro_total']:.2f}</div><div style='color:#8b949e'>Gas minimo 0.6 gwei - nao come BNB</div></div></div>"
    html+=f"<div class='grid2'><div class='card'><b>GRID 20 NIVEIS - TUDO 9 USDT</b>"
    for g in estado["grids"]:
        cor="#22c55e" if g["tipo"]=="COMPRADO" else "#ef4444"
        qtdinfo = f"{g['usdt']} USDT" if g["tipo"]=="VENDIDO" else f"{g['qtd']} UNI"
        html+=f"<div class='row'><span>G{g['n']} ${g['preco']:.2f} ({qtdinfo})</span><span style='color:{cor}'>{g['status']}</span><span>{g['vezes']}x ${g['lucro']:.2f}</span></div>"
    html+=f"</div><div><div class='card'><b>Historico</b>"
    for t in estado["trades"][:8]:
        html+=f"<div class='row'>{t['data']} {t['tipo']} {t['qtd']} @ ${t['preco']:.2f}</div>"
    if not estado["trades"]: html+=f"<div class='row'>Aguardando</div>"
    html+=f"</div><div class='card'><b>Lucro Acumulado</b><div style='font-size:32px;color:#22c55e'>+${estado['lucro_total']:.2f}</div></div></div></div></body></html>"
    return html

@app.route("/")
def home(): return "Bot com trava BNB - /dashboard"
if __name__=="__main__": app.run(host="0.0.0.0",port=10000)
