import os
import time
import threading
from datetime import datetime

from flask import Flask, jsonify, render_template_string
from web3 import Web3

app = Flask(__name__)

# PancakeSwap V2 e tokens na BNB Smart Chain.
FACTORY_ADDRESS = Web3.to_checksum_address(
    "0xcA143Ce32Fe78f1f7019d7d551a6402fC5350c73"
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

# Pode receber um RPC próprio em BSC_RPC_URL.
# Se não for definido ou falhar, o bot tenta os RPCs públicos.
RPC_URLS = [
    os.getenv("BSC_RPC_URL", "").strip(),
    "https://bsc-dataseed.binance.org/",
    "https://bsc-dataseed1.binance.org/",
    "https://bsc-dataseed2.binance.org/",
    "https://bsc-dataseed3.binance.org/",
    "https://bsc-dataseed4.binance.org/",
    "https://bsc-rpc.publicnode.com",
    "https://1rpc.io/bnb",
]
RPC_URLS = list(dict.fromkeys(url for url in RPC_URLS if url))

CAPITAL_USDT = 1.00
NIVEIS = 5
FAIXA_PERCENTUAL = 0.05
ORDEM_USDT = 0.10
SLIPPAGE_PERCENTUAL = 0.01
CUSTO_ESTIMADO_PERCENTUAL = 0.003
PERDA_MAXIMA_USDT = 0.10
INTERVALO_SEGUNDOS = 30
TEMPO_LIMITE_RPC = 12

FACTORY_ABI = [
    {
        "inputs": [
            {"internalType": "address", "name": "tokenA", "type": "address"},
            {"internalType": "address", "name": "tokenB", "type": "address"},
        ],
        "name": "getPair",
        "outputs": [{"internalType": "address", "name": "pair", "type": "address"}],
        "stateMutability": "view",
        "type": "function",
    }
]

PAIR_ABI = [
    {
        "inputs": [],
        "name": "token0",
        "outputs": [{"internalType": "address", "name": "", "type": "address"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "getReserves",
        "outputs": [
            {"internalType": "uint112", "name": "reserve0", "type": "uint112"},
            {"internalType": "uint112", "name": "reserve1", "type": "uint112"},
            {"internalType": "uint32", "name": "blockTimestampLast", "type": "uint32"},
        ],
        "stateMutability": "view",
        "type": "function",
    },
]

ERC20_ABI = [
    {
        "inputs": [],
        "name": "decimals",
        "outputs": [{"internalType": "uint8", "name": "", "type": "uint8"}],
        "stateMutability": "view",
        "type": "function",
    }
]

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
    "rpc_usado": "",
    "rota_usada": "",
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

def nome_rpc(url):
    return url.split("://", 1)[-1].split("/", 1)[0]

def verificar_endereco(cliente, nome, endereco):
    codigo = cliente.eth.get_code(endereco)
    if len(bytes(codigo)) == 0:
        raise ValueError(
            f"Não foi encontrado código de contrato para {nome} na BNB Chain."
        )

def obter_decimais(cliente, endereco):
    contrato = cliente.eth.contract(address=endereco, abi=ERC20_ABI)
    return int(contrato.functions.decimals().call())

def preco_no_par(cliente, factory, token_a, token_b, decimais_a, decimais_b):
    endereco_par = factory.functions.getPair(token_a, token_b).call()

    if endereco_par.lower() == "0x0000000000000000000000000000000000000000":
        raise ValueError("Não existe pool V2 para esse par.")

    endereco_par = Web3.to_checksum_address(endereco_par)
    contrato_par = cliente.eth.contract(address=endereco_par, abi=PAIR_ABI)
    endereco_token0 = contrato_par.functions.token0().call()
    reserva0, reserva1, _ = contrato_par.functions.getReserves().call()

    if reserva0 <= 0 or reserva1 <= 0:
        raise ValueError("O pool existe, mas não tem reservas disponíveis.")

    token0_e_a = endereco_token0.lower() == token_a.lower()

    if token0_e_a:
        reserva_a = reserva0 / (10 ** decimais_a)
        reserva_b = reserva1 / (10 ** decimais_b)
    else:
        reserva_a = reserva1 / (10 ** decimais_a)
        reserva_b = reserva0 / (10 ** decimais_b)

    if reserva_a <= 0 or reserva_b <= 0:
        raise ValueError("As reservas do pool retornaram um valor inválido.")

    return reserva_b / reserva_a

def obter_preco_em_rpc(url):
    cliente = Web3(
        Web3.HTTPProvider(
            url,
            request_kwargs={"timeout": TEMPO_LIMITE_RPC},
        )
    )

    if not cliente.is_connected():
        raise ConnectionError("Não foi possível conectar a este RPC.")

    chain_id = cliente.eth.chain_id
    if chain_id != 56:
        raise ConnectionError(
            f"O RPC respondeu pela rede {chain_id}, não pela BNB Smart Chain."
        )

    verificar_endereco(cliente, "Factory PancakeSwap V2", FACTORY_ADDRESS)
    verificar_endereco(cliente, "UNI", UNI_ADDRESS)
    verificar_endereco(cliente, "USDT", USDT_ADDRESS)
    verificar_endereco(cliente, "WBNB", WBNB_ADDRESS)

    factory = cliente.eth.contract(address=FACTORY_ADDRESS, abi=FACTORY_ABI)

    decimais_uni = obter_decimais(cliente, UNI_ADDRESS)
    decimais_usdt = obter_decimais(cliente, USDT_ADDRESS)
    decimais_wbnb = obter_decimais(cliente, WBNB_ADDRESS)

    try:
        preco = preco_no_par(
            cliente,
            factory,
            UNI_ADDRESS,
            USDT_ADDRESS,
            decimais_uni,
            decimais_usdt,
        )
        return preco, "UNI/USDT direto"
    except Exception as erro_direto:
        erro_direto = str(erro_direto)

    try:
        preco_uni_wbnb = preco_no_par(
            cliente,
            factory,
            UNI_ADDRESS,
            WBNB_ADDRESS,
            decimais_uni,
            decimais_wbnb,
        )
        preco_wbnb_usdt = preco_no_par(
            cliente,
            factory,
            WBNB_ADDRESS,
            USDT_ADDRESS,
            decimais_wbnb,
            decimais_usdt,
        )
        return preco_uni_wbnb * preco_wbnb_usdt, "UNI/WBNB → WBNB/USDT"
    except Exception as erro_rota:
        raise RuntimeError(
            "Não foi possível obter cotação nem pelo pool direto UNI/USDT "
            "nem pela rota via WBNB. "
            f"Direto: {erro_direto[:180]} | Via WBNB: {str(erro_rota)[:180]}"
        )

def obter_preco_uni_usdt():
    erros = []

    for url in RPC_URLS:
        servidor = nome_rpc(url)
        try:
            preco, rota = obter_preco_em_rpc(url)
            with lock:
                STATE["rpc_usado"] = servidor
                STATE["rota_usada"] = rota
            return preco
        except Exception as erro:
            erros.append(f"{servidor}: {str(erro)[:250]}")

    raise ConnectionError(
        "Todos os RPCs falharam. " + " || ".join(erros)
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
            "id": indice + 1,
            "preco": minimo + indice * passo,
            "operacoes": 0,
            "ultima_operacao": "Aguardando cruzamento",
        }
        for indice in range(NIVEIS)
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

        preco_execucao = preco * (1 + slippage)
        quantidade = (valor * (1 - custo)) / preco_execucao

        STATE["saldo_usdt_virtual"] -= valor
        STATE["saldo_uni_virtual"] += quantidade
        descricao = f"Compra simulada de {quantidade:.8f} UNI"
    else:
        preco_execucao = preco * (1 - slippage)
        quantidade_desejada = ORDEM_USDT / preco_execucao
        quantidade = min(quantidade_desejada, STATE["saldo_uni_virtual"])

        if quantidade <= 0:
            return

        valor_liquido = quantidade * preco_execucao * (1 - custo)
        STATE["saldo_uni_virtual"] -= quantidade
        STATE["saldo_usdt_virtual"] += valor_liquido
        descricao = f"Venda simulada de {quantidade:.8f} UNI"

    STATE["trades"] += 1
    grid = STATE["grids"][nivel]
    grid["operacoes"] += 1
    grid["ultima_operacao"] = tipo

    STATE["historico"].insert(
        0,
        {
            "hora": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            "tipo": tipo,
            "nivel": nivel + 1,
            "preco": preco,
            "descricao": descricao,
            "observacao": "Simulação; nenhuma transação real foi enviada.",
        },
    )
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
            mensagem = str(erro)[:1200]
            with lock:
                STATE["last_error"] = mensagem
                if not STATE["parado_por_limite"]:
                    STATE["status"] = "Erro ao consultar preço"
            log(f"Falha na consulta de preço: {mensagem}")

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
h2{font-size:17px;margin:0 0 10px}
p{color:#aebbd0;overflow-wrap:anywhere}
.notice{padding:12px;border:1px solid #76602d;background:#211d12;border-radius:9px;color:#f3dda1;margin:16px 0}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:10px}
.card,.box{background:#121e30;border:1px solid #283a54;border-radius:10px;padding:14px;min-width:0}
.label{color:#9eafc7;font-size:12px}
.value{display:block;font-size:20px;font-weight:bold;margin-top:7px;overflow-wrap:anywhere}
.columns{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:12px}
.item{padding:9px 0;border-bottom:1px solid #26374e;font-size:12px;overflow-wrap:anywhere}
.item:last-child{border-bottom:0}
.error{color:#ff8b96;white-space:pre-wrap}
.muted{color:#9eafc7;font-size:12px;overflow-wrap:anywhere}
@media(max-width:700px){body{padding:12px}.columns{grid-template-columns:1fr}.value{font-size:18px}}
</style>
</head>
<body>
<main>
  <h1>UNI/USDT · Grid em simulação</h1>
  <p>BNB Smart Chain · PancakeSwap V2 · Painel somente para leitura</p>
  <div class="notice">
    Este bot não compra nem vende tokens reais. Ele consulta as reservas dos pools
    e simula operações. Não usa chave privada e não garante lucro.
  </div>

  <section class="cards">
    <div class="card"><span class="label">Preço consultado</span><strong class="value" id="price">Aguardando</strong></div>
    <div class="card"><span class="label">USDT virtual</span><strong class="value" id="usdt">Aguardando</strong></div>
    <div class="card"><span class="label">UNI virtual</span><strong class="value" id="uni">Aguardando</strong></div>
    <div class="card"><span class="label">Resultado simulado</span><strong class="value" id="pnl">Aguardando</strong></div>
  </section>

  <p id="status">Conectando...</p>
  <p class="muted" id="route"></p>
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
    if(!response.ok)throw new Error("Falha ao consultar o estado do bot.");
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
    document.getElementById("route").textContent=
      s.rpc_usado
        ? "RPC: "+s.rpc_usado+" · Rota: "+(s.rota_usada||"aguardando")
        : "";
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
    document.getElementById("error").textContent=
      "Não foi possível carregar o painel. Atualize a página.";
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

iniciar_thread()

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", "10000")),
        threaded=True,
    )
