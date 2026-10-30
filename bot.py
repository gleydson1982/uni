import os
import time
import threading
from datetime import datetime
from flask import Flask, jsonify, render_template_string
from web3 import Web3

app = Flask(__name__)

# UNI e USDT na BNB Smart Chain. O contrato UNI é o endereço informado pelo usuário.
RPC_URL = os.getenv("BSC_RPC_URL", "https://bsc-dataseed.binance.org/")
ROUTER_ADDRESS = Web3.to_checksum_address(
    "0x10ED43C718714eB63B5aA57B78B54704E256024E"
)
UNI_ADDRESS = Web3.to_checksum_address(
    "0xBf5140A22578168FD562DCcF235E5D43A02ce9B1"
)
USDT_ADDRESS = Web3.to_checksum_address(
    "0x55d398326f99059fF775485246999027B3197955"
)
WBNB_ADDRESS = Web3.to_checksum_address(
    "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c"
)

# Parâmetros da simulação
CAPITAL_USDT = 1.00
NIVEIS = 5
FAIXA_PERCENTUAL = 0.05
ORDEM_USDT = 0.10
SLIPPAGE_PERCENTUAL = 0.01
CUSTO_ESTIMADO_PERCENTUAL = 0.003
PERDA_MAXIMA_USDT = 0.10
INTERVALO_SEGUNDOS = 30

w3 = Web3(Web3.HTTPProvider(RPC_URL, request_kwargs={"timeout": 12}))

ERC20_ABI = [
    {
        "inputs": [],
        "name": "decimals",
        "outputs": [{"type": "uint8", "name": ""}],
        "stateMutability": "view",
        "type": "function",
    }
]

ROUTER_ABI = [
    {
        "inputs": [
            {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
            {"internalType": "address[]", "name": "path", "type": "address[]"},
        ],
        "name": "getAmountsOut",
        "outputs": [
            {"internalType": "uint256[]", "name": "amounts", "type": "uint256[]"}
        ],
        "stateMutability": "view",
        "type": "function",
    }
]

router = w3.eth.contract(address=ROUTER_ADDRESS, abi=ROUTER_ABI)
uni_contract = w3.eth.contract(address=UNI_ADDRESS, abi=ERC20_ABI)
usdt_contract = w3.eth.contract(address=USDT_ADDRESS, abi=ERC20_ABI)

lock = threading.RLock()

STATE = {
    "status": "Iniciando consulta da BNB Chain",
    "preco": None,
    "preco_referencia": None,
    "saldo_usdt_virtual": 0.0,
    "saldo_uni_virtual": 0.0,
    "resultado_usdt": 0.0,
    "valor_carteira_virtual": 0.0,
    "trades": 0,
    "perda_maxima_usdt": PERDA_MAXIMA_USDT,
    "parado_por_limite": False,
    "ultima_atualizacao": None,
    "last_error": "",
    "grids": [],
    "logs": [],
    "historico": [],
}

def log(mensagem):
    registro = f"{datetime.now().strftime('%d/%m/%Y %H:%M:%S')} · {mensagem}"
    with lock:
        STATE["logs"].insert(0, registro)
        STATE["logs"] = STATE["logs"][:30]
    print(registro, flush=True)

def obter_decimais(token):
    return int(token.functions.decimals().call())

def cotacao_por_rota(amount_in, path, decimals_saida):
    amounts = router.functions.getAmountsOut(amount_in, path).call()
    if len(amounts) < 2:
        raise ValueError("A PancakeSwap não retornou uma cotação válida.")
    return amounts[-1] / (10 ** decimals_saida)

def obter_preco_uni_usdt():
    if not w3.is_connected():
        raise ConnectionError("Não foi possível conectar à BNB Smart Chain.")

    uni_decimals = obter_decimais(uni_contract)
    usdt_decimals = obter_decimais(usdt_contract)
    amount_uni = 10 ** uni_decimals

    try:
        # Primeiro tenta a rota direta UNI → USDT.
        return cotacao_por_rota(
            amount_uni,
            [UNI_ADDRESS, USDT_ADDRESS],
            usdt_decimals,
        )
    except Exception:
        # Se não houver rota direta, tenta UNI → WBNB → USDT.
        return cotacao_por_rota(
            amount_uni,
            [UNI_ADDRESS, WBNB_ADDRESS, USDT_ADDRESS],
            usdt_decimals,
        )

def calcular_resultado():
    preco = STATE["preco"]
    if preco is None:
        return

    valor = (
        STATE["saldo_usdt_virtual"]
        + STATE["saldo_uni_virtual"] * preco
    )
    resultado = valor - CAPITAL_USDT

    STATE["valor_carteira_virtual"] = valor
    STATE["resultado_usdt"] = resultado

    if resultado <= -PERDA_MAXIMA_USDT:
        STATE["parado_por_limite"] = True
        STATE["status"] = "Parado pelo limite de perda simulada"

def iniciar_carteira_virtual(preco):
    STATE["preco_referencia"] = preco
    STATE["saldo_usdt_virtual"] = CAPITAL_USDT / 2
    STATE["saldo_uni_virtual"] = (CAPITAL_USDT / 2) / preco

    minimo = preco * (1 - FAIXA_PERCENTUAL)
    maximo = preco * (1 + FAIXA_PERCENTUAL)
    passo = (maximo - minimo) / (NIVEIS - 1)

    STATE["grids"] = [
        {
            "id": i + 1,
            "preco": minimo + i * passo,
            "operacoes": 0,
            "ultima_operacao": "Aguardando cruzamento",
        }
        for i in range(NIVEIS)
    ]

    calcular_resultado()
    log(f"Simulação iniciada. Preço de referência: ${preco:.6f}.")

def registrar_operacao(tipo, nivel, preco):
    custo = CUSTO_ESTIMADO_PERCENTUAL
    slippage = SLIPPAGE_PERCENTUAL

    if tipo == "COMPRA":
        valor = min(ORDEM_USDT, STATE["saldo_usdt_virtual"])
        if valor <= 0:
            return

        preco_execucao_estimado = preco * (1 + slippage)
        quantidade = (valor * (1 - custo)) / preco_execucao_estimado

        STATE["saldo_usdt_virtual"] -= valor
        STATE["saldo_uni_virtual"] += quantidade
        descricao = f"Compra simulada de {quantidade:.8f} UNI"

    else:
        preco_execucao_estimado = preco * (1 - slippage)
        quantidade_desejada = ORDEM_USDT / preco_execucao_estimado
        quantidade = min(quantidade_desejada, STATE["saldo_uni_virtual"])

        if quantidade <= 0:
            return

        valor_bruto = quantidade * preco_execucao_estimado
        valor_liquido = valor_bruto * (1 - custo)

        STATE["saldo_uni_virtual"] -= quantidade
        STATE["saldo_usdt_virtual"] += valor_liquido
        descricao = f"Venda simulada de {quantidade:.8f} UNI"

    STATE["trades"] += 1
    grid = STATE["grids"][nivel]
    grid["operacoes"] += 1
    grid["ultima_operacao"] = tipo

    registro = {
        "hora": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "tipo": tipo,
        "nivel": nivel + 1,
        "preco": preco,
        "descricao": descricao,
        "observacao": "Simulação; nenhuma transação real foi enviada.",
    }
    STATE["historico"].insert(0, registro)
    STATE["historico"] = STATE["historico"][:50]

    log(
        f"{tipo} simulada no nível G{nivel + 1}, "
        f"preço de referência ${preco:.6f}."
    )

def processar_movimento(preco_anterior, preco_atual):
    if STATE["parado_por_limite"]:
        return

    for indice, grid in enumerate(STATE["grids"]):
        nivel = grid["preco"]

        if preco_anterior > nivel and preco_atual <= nivel:
            registrar_operacao("COMPRA", indice, preco_atual)

        elif preco_anterior < nivel and preco_atual >= nivel:
            registrar_operacao("VENDA", indice, preco_atual)

        if STATE["parado_por_limite"]:
            break

def atualizar_cotacao():
    preco_novo = obter_preco_uni_usdt()

    if preco_novo <= 0:
        raise ValueError("A cotação retornada não é positiva.")

    with lock:
        preco_anterior = STATE["preco"]
        STATE["preco"] = preco_novo
        STATE["ultima_atualizacao"] = datetime.now().strftime(
            "%d/%m/%Y %H:%M:%S"
        )
        STATE["last_error"] = ""

        if STATE["preco_referencia"] is None:
            iniciar_carteira_virtual(preco_novo)
        elif preco_anterior is not None:
            processar_movimento(preco_anterior, preco_novo)

        calcular_resultado()

        if not STATE["parado_por_limite"]:
            STATE["status"] = "Monitorando em modo de simulação"

    return preco_novo

def loop_bot():
    log("Monitoramento iniciado em modo de simulação. Sem transações reais.")

    while True:
        try:
            preco = atualizar_cotacao()
            log(f"Preço consultado: ${preco:.6f} USDT por UNI.")
        except Exception as erro:
            with lock:
                STATE["last_error"] = str(erro)[:250]
                if not STATE["parado_por_limite"]:
                    STATE["status"] = "Erro ao consultar preço"
            log(f"Falha na consulta de preço: {erro}")

        time.sleep(INTERVALO_SEGUNDOS)

HTML = """
<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>UNI Grid · Simulação</title>
<style>
*{box-sizing:border-box}
body{margin:0;padding:20px;background:#0b1220;color:#e8eef8;font:14px Arial,sans-serif}
main{max-width:1100px;margin:auto}
h1{margin:0 0 5px;font-size:23px}
p{color:#aebbd0}
.notice{padding:12px;border:1px solid #76602d;background:#211d12;border-radius:9px;color:#f3dda1;margin:16px 0}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:10px}
.card{background:#121e30;border:1px solid #283a54;border-radius:10px;padding:14px}
.label{color:#9eafc7;font-size:12px}
.value{display:block;font-size:20px;font-weight:bold;margin-top:7px;overflow-wrap:anywhere}
.columns{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:12px}
.box{background:#121e30;border:1px solid #283a54;border-radius:10px;padding:14px}
.item{padding:9px 0;border-bottom:1px solid #26374e;font-size:12px}
.item:last-child{border-bottom:0}
.error{color:#ff8b96}
.good{color:#55e0a6}
.muted{color:#9eafc7;font-size:12px}
@media(max-width:700px){body{padding:12px}.columns{grid-template-columns:1fr}}
</style>
</head>
<body>
<main>
  <h1>UNI/USDT · Grid em simulação</h1>
  <p>BNB Smart Chain · PancakeSwap · Painel somente para leitura</p>
  <div class="notice">
    Este bot não compra nem vende tokens reais. Ele simula as operações e não usa
    chave privada. O preço pode variar e a simulação não garante lucro.
  </div>

  <section class="cards">
    <div class="card"><span class="label">Preço consultado</span><strong class="value" id="price">Aguardando</strong></div>
    <div class="card"><span class="label">USDT virtual</span><strong class="value" id="usdt">Aguardando</strong></div>
    <div class="card"><span class="label">UNI virtual</span><strong class="value" id="uni">Aguardando</strong></div>
    <div class="card"><span class="label">Resultado simulado</span><strong class="value" id="pnl">Aguardando</strong></div>
  </section>

  <p id="status">Conectando...</p>
  <p class="muted" id="updated"></p>
  <p class="error" id="error"></p>

  <section class="columns">
    <div class="box">
      <h2>Níveis do grid</h2>
      <div id="grids"></div>
    </div>
    <div class="box">
      <h2>Últimas operações simuladas</h2>
      <div id="history"></div>
    </div>
  </section>

  <section class="box" style="margin-top:12px">
    <h2>Registro do bot</h2>
    <div id="logs"></div>
  </section>
</main>

<script>
function fmt(n,d=6){
  if(n===null||n===undefined)return "Aguardando";
  return Number(n).toLocaleString("pt-BR",{minimumFractionDigits:2,maximumFractionDigits:d});
}
function safeText(value){
  const el=document.createElement("span");
  el.textContent=String(value ?? "");
  return el.innerHTML;
}
async function load(){
  try{
    const response=await fetch("/api/state",{cache:"no-store"});
    const s=await response.json();

    document.getElementById("price").textContent=
      s.preco===null?"Aguardando":"$"+fmt(s.preco,6)+" USDT";
    document.getElementById("usdt").textContent=
      fmt(s.saldo_usdt_virtual,6)+" USDT";
    document.getElementById("uni").textContent=
      fmt(s.saldo_uni_virtual,8)+" UNI";
    document.getElementById("pnl").textContent=
      (s.resultado_usdt>=0?"+":"")+"$"+fmt(s.resultado_usdt,4);
    document.getElementById("status").textContent="Status: "+s.status;
    document.getElementById("updated").textContent=
      s.ultima_atualizacao?"Última atualização: "+s.ultima_atualizacao:"";
    document.getElementById("error").textContent=s.last_error||"";

    document.getElementById("grids").innerHTML=(s.grids||[]).map(g=>
      '<div class="item">G'+g.id+' · $'+fmt(g.preco,6)+
      ' · operações: '+g.operacoes+
      ' · última: '+safeText(g.ultima_operacao)+'</div>'
    ).join("")||'<div class="muted">Aguardando cotação inicial.</div>';

    document.getElementById("history").innerHTML=(s.historico||[]).map(h=>
      '<div class="item"><b>'+safeText(h.tipo)+'</b> · G'+h.nivel+
      '<br>'+safeText(h.hora)+' · '+safeText(h.descricao)+
      '<br><span class="muted">'+safeText(h.observacao)+'</span></div>'
    ).join("")||'<div class="muted">Ainda sem operações simuladas.</div>';

    document.getElementById("logs").innerHTML=(s.logs||[]).map(x=>
      '<div class="item">'+safeText(x)+'</div>'
    ).join("")||'<div class="muted">Aguardando registro.</div>';
  }catch(e){
    document.getElementById("error").textContent="Não foi possível carregar o painel.";
  }
}
load();
setInterval(load,5000);
</script>
</body>
</html>
"""

@app.route("/")
def home():
    return render_template_string(HTML)

@app.route("/api/state")
def api_state():
    with lock:
        return jsonify(STATE)

@app.route("/health")
def health():
    return jsonify({"ok": True, "mode": "simulation"})

def iniciar_thread():
    thread = threading.Thread(target=loop_bot, daemon=True)
    thread.start()

# Use um único worker Gunicorn para evitar iniciar várias cópias do bot.
iniciar_thread()

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", "10000")),
        threaded=True,
    )
