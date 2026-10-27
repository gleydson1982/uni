import time, json, os, requests, threading
from web3 import Web3
from flask import Flask, jsonify, render_template_string

RPCS = ["https://1rpc.io/bnb","https://bsc-dataseed4.binance.org","https://bsc-dataseed.bnbchain.org"]
web3 = None
for rpc in RPCS:
    try:
        w = Web3(Web3.HTTPProvider(rpc, request_kwargs={'timeout': 10}))
        if w.is_connected():
            web3 = w
            print(f"Conectado: {rpc}")
            break
    except: continue

PRIVATE_KEY = os.getenv("PRIVATE_KEY","").strip()
ACCOUNT = web3.eth.account.from_key(PRIVATE_KEY) if PRIVATE_KEY else None
ADDRESS = ACCOUNT.address if ACCOUNT else "0x0"
print(f"Carteira: {ADDRESS}")

USDT = web3.to_checksum_address("0x55d398326f99059fF775485246999027B3197955")
WBNB = web3.to_checksum_address("0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c")
UNI = web3.to_checksum_address("0xBf5140A22578168FD562DCcF235E5D43A02ce9B1")
ROUTER = web3.to_checksum_address("0x10ED43C718714eb63d5aA57B78B54704E256024E")

ABI_ROUTER = json.loads('[{"inputs":[{"internalType":"uint256","name":"amountIn","type":"uint256"},{"internalType":"uint256","name":"amountOutMin","type":"uint256"},{"internalType":"address[]","name":"path","type":"address[]"},{"internalType":"address","name":"to","type":"address"},{"internalType":"uint256","name":"deadline","type":"uint256"}],"name":"swapExactTokensForTokensSupportingFeeOnTransferTokens","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"uint256","name":"amountIn","type":"uint256"},{"internalType":"address[]","name":"path","type":"address[]"}],"name":"getAmountsOut","outputs":[{"internalType":"uint256[]","name":"amounts","type":"uint256[]"}],"stateMutability":"view","type":"function"}]')
ABI_ERC20 = json.loads('[{"inputs":[{"internalType":"address","name":"spender","type":"address"},{"internalType":"uint256","name":"amount","type":"uint256"}],"name":"approve","outputs":[{"internalType":"bool","name":"","type":"bool"}],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"address","name":"account","type":"address"}],"name":"balanceOf","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"}]')

router = web3.eth.contract(address=ROUTER, abi=ABI_ROUTER)
usdt_c = web3.eth.contract(address=USDT, abi=ABI_ERC20)
uni_c = web3.eth.contract(address=UNI, abi=ABI_ERC20)

PRECO_BASE=6.83
GRID_PCT=0.03
NUM_GRIDS=20
USDT_POR_GRID=6.5
UNI_POR_GRID=0.95
grids_comprados=set()
grids_vendidos=set()
trades=[]
estado={"preco_atual":PRECO_BASE,"saldo_uni":0,"saldo_usdt":0,"ultimo_update":"","status":"iniciando"}

def saldo_usdt():
    try: return usdt_c.functions.balanceOf(ADDRESS).call()/1e18
    except: return 0
def saldo_uni():
    try: return uni_c.functions.balanceOf(ADDRESS).call()/1e18
    except: return 0
def preco_atual():
    try:
        r=requests.get("https://api.binance.com/api/v3/ticker/price?symbol=UNIUSDT",timeout=5).json()
        return float(r['price'])
    except: return PRECO_BASE

def comprar(v):
    if not ACCOUNT: return True
    for sli in [0.98,0.96]:
        try:
            amt=int(v*1e18)
            tx=usdt_c.functions.approve(ROUTER,amt).build_transaction({'from':ADDRESS,'gas':80000,'gasPrice':int(web3.eth.gas_price*1.2),'nonce':web3.eth.get_transaction_count(ADDRESS)})
            s=web3.eth.account.sign_transaction(tx,PRIVATE_KEY)
            h=web3.eth.send_raw_transaction(s.rawTransaction)
            web3.eth.wait_for_transaction_receipt(h)
            time.sleep(2)
            amounts=router.functions.getAmountsOut(amt,[USDT,WBNB,UNI]).call()
            min_out=int(amounts[2]*sli)
            tx=router.functions.swapExactTokensForTokensSupportingFeeOnTransferTokens(amt,min_out,[USDT,WBNB,UNI],ADDRESS,int(time.time())+600).build_transaction({'from':ADDRESS,'gas':350000,'gasPrice':int(web3.eth.gas_price*1.2),'nonce':web3.eth.get_transaction_count(ADDRESS)})
            s=web3.eth.account.sign_transaction(tx,PRIVATE_KEY)
            h=web3.eth.send_raw_transaction(s.rawTransaction)
            web3.eth.wait_for_transaction_receipt(h)
            return True
        except Exception as e:
            print(f"Falha compra {e}")
            continue
    return False

def vender(v):
    if not ACCOUNT: return True
    for sli in [0.98,0.96]:
        try:
            amt=int(v*1e18)
            tx=uni_c.functions.approve(ROUTER,amt).build_transaction({'from':ADDRESS,'gas':80000,'gasPrice':int(web3.eth.gas_price*1.2),'nonce':web3.eth.get_transaction_count(ADDRESS)})
            s=web3.eth.account.sign_transaction(tx,PRIVATE_KEY)
            h=web3.eth.send_raw_transaction(s.rawTransaction)
            web3.eth.wait_for_transaction_receipt(h)
            time.sleep(2)
            amounts=router.functions.getAmountsOut(amt,[UNI,WBNB,USDT]).call()
            min_out=int(amounts[2]*sli)
            tx=router.functions.swapExactTokensForTokensSupportingFeeOnTransferTokens(amt,min_out,[UNI,WBNB,USDT],ADDRESS,int(time.time())+600).build_transaction({'from':ADDRESS,'gas':350000,'gasPrice':int(web3.eth.gas_price*1.2),'nonce':web3.eth.get_transaction_count(ADDRESS)})
            s=web3.eth.account.sign_transaction(tx,PRIVATE_KEY)
            h=web3.eth.send_raw_transaction(s.rawTransaction)
            web3.eth.wait_for_transaction_receipt(h)
            return True
        except Exception as e:
            print(f"Falha venda {e}")
            continue
    return False

def bot_loop():
    while True:
        try:
            p=preco_atual()
            ub=saldo_uni()
            us=saldo_usdt()
            estado["preco_atual"]=p
            estado["saldo_uni"]=ub
            estado["saldo_usdt"]=us
            estado["ultimo_update"]=time.strftime('%H:%M:%S')
            estado["status"]="rodando"
            print(f"[{estado['ultimo_update']}] ${p:.4f} UNI {ub:.3f} USDT {us:.2f}")
            for i in range(1,21):
                g=PRECO_BASE*(1-GRID_PCT*i)
                if p<=g and i not in grids_comprados:
                    print(f">>> COMPRA {i} ${g:.2f}")
                    if comprar(USDT_POR_GRID):
                        grids_comprados.add(i)
                        trades.append({"tipo":"COMPRA","nivel":i,"preco_gatilho":round(g,4),"preco_exec":round(p,4),"usdt":USDT_POR_GRID,"hora":estado["ultimo_update"],"pnl":0})
            for i in range(1,21):
                g=PRECO_BASE*(1+GRID_PCT*i)
                if p>=g and i not in grids_vendidos:
                    print(f">>> VENDA {i} ${g:.2f}")
                    if vender(UNI_POR_GRID):
                        grids_vendidos.add(i)
                        lucro=UNI_POR_GRID*(g-PRECO_BASE)
                        trades.append({"tipo":"VENDA","nivel":i,"preco_gatilho":round(g,4),"preco_exec":round(p,4),"uni":UNI_POR_GRID,"hora":estado["ultimo_update"],"pnl":round(lucro,2)})
        except Exception as e:
            print(f"Erro {e}")
            estado["status"]=str(e)
        time.sleep(15)

app=Flask(__name__)
HTML="<!DOCTYPE html><html><head><meta name='viewport' content='width=device-width, initial-scale=1'><title>UNI GRID</title><style>body{font-family:Arial;background:#0f0f0f;color:#fff;padding:15px}.card{background:#1e1e1e;border-radius:12px;padding:15px;margin-bottom:15px}.green{color:#00ff88}.grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}table{width:100%;border-collapse:collapse;font-size:13px}th,td{padding:8px;border-bottom:1px solid #333}</style></head><body><h2>UNI/USDT GRID - BNB</h2><div class='card grid'><div><b>Preco:</b> ${{estado.preco_atual}}<br><b>Base:</b> $6.83</div><div><b>UNI:</b> {{ '%.3f'|format(estado.saldo_uni) }}<br><b>USDT:</b> ${{ '%.2f'|format(estado.saldo_usdt) }}</div></div><div class='card grid'><div><b>Comprados:</b> {{comprados}}/20<br><b>Vendidos:</b> {{vendidos}}/20</div><div><b>Lucro:</b> <span class='green'>${{pnl_total}}</span><br><b>Status:</b> {{estado.status}} {{estado.ultimo_update}}</div></div><div class='card'><h3>P&L por Grid</h3><table><tr><th>Nivel</th><th>Gatilho</th><th>Tipo</th><th>Exec</th><th>PnL</th><th>Hora</th></tr>{% for t in trades[::-1][:30] %}<tr><td>{{t.nivel}}</td><td>${{t.preco_gatilho}}</td><td>{{t.tipo}}</td><td>${{t.preco_exec}}</td><td class='green'>${{t.pnl}}</td><td>{{t.hora}}</td></tr>{% endfor %}</table></div><div class='card'><h3>Grid Levels</h3><table><tr><th>N</th><th>Compra</th><th>Venda</th><th>Status</th></tr>{% for i in range(1,21) %}<tr><td>{{i}}</td><td>${{ '%.2f'|format(6.83*(1-0.03*i)) }}</td><td>${{ '%.2f'|format(6.83*(1+0.03*i)) }}</td><td>{% if i in comprados_set %}COMPRADO{% elif i in vendidos_set %}VENDIDO{% else %}AGUARDANDO{% endif %}</td></tr>{% endfor %}</table></div><script>setTimeout(()=>location.reload(),15000)</script></body></html>"

@app.route("/")
def home(): return f"Bot GRID online - {ADDRESS} - <a href='/dashboard'>Dashboard</a>"
@app.route("/dashboard")
def dashboard():
    pnl=sum(t.get("pnl",0) for t in trades)
    return render_template_string(HTML,estado=estado,trades=trades,comprados=len(grids_comprados),vendidos=len(grids_vendidos),pnl_total=round(pnl,2),comprados_set=grids_comprados,vendidos_set=grids_vendidos,range=range)

if __name__=="__main__":
    threading.Thread(target=bot_loop,daemon=True).start()
    port=int(os.getenv("PORT",10000))
    app.run(host="0.0.0.0",port=port)
