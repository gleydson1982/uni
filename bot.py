import copy
import json
import os
import threading
import time
from datetime import datetime

from flask import Flask, jsonify, render_template_string
from web3 import Web3

app = Flask(__name__)

# MODO SIMULAÇÃO: este código não usa chave privada e não envia transações.
CHAIN_ID = 56
POLL_SECONDS = 12
CAPITAL_USDT = 1.00
GRID_LEVELS = 5
GRID_RANGE = 0.05
ORDER_USDT = CAPITAL_USDT / GRID_LEVELS
MAX_LOSS_USDT = 0.10
SLIPPAGE_PERCENT = 0.01
ESTIMATED_FEE_RATE = 0.003

ROUTER = Web3.to_checksum_address(
    "0x10ED43C718714eB63B5aA57B78B54704E256024E"
)
UNI = Web3.to_checksum_address(
    "0xBf5140A22578168FD562DCcF235E5D43A02ce9B1"
)
USDT = Web3.to_checksum_address(
    "0x55d398326f99059fF775485246999027B3197955"
)
WBNB = Web3.to_checksum_address(
    "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c"
)

# Endereço público consultado somente para mostrar os saldos.
READ_ONLY_WALLET = Web3.to_checksum_address(
    os.getenv(
        "READ_ONLY_WALLET",
        "0x8AEE0c5120f326C2389E3B6affa39E3BEBe82Fd3"
    )
)

RPC_URLS = []
custom_rpc = os.getenv("BSC_RPC_URL", "").strip()
if custom_rpc:
    RPC_URLS.append(custom_rpc)

RPC_URLS.extend([
    "https://bsc-dataseed.binance.org/",
    "https://bsc-dataseed1.binance.org/",
    "https://bsc-dataseed2.binance.org/",
    "https://bsc-rpc.publicnode.com",
])
RPC_URLS = list(dict.fromkeys(RPC_URLS))

STATE_FILE = os.getenv("SIM_STATE_FILE", "estado_simulacao.json")
STATE_LOCK = threading.RLock()

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

ERC20_ABI = [
    {
        "constant": True,
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function",
    },
]


def fresh_state():
    return {
        "mode": "SIMULAÇÃO",
        "reference_price": None,
        "price": None,
        "price_route": "",
        "last_price": None,
        "rpc": "",
        "wallet": READ_ONLY_WALLET,
        "wallet_balances": {"bnb": None, "uni": None, "usdt": None},
        "virtual_usdt": CAPITAL_USDT,
        "virtual_uni": 0.0,
        "equity": CAPITAL_USDT,
        "pnl_total": 0.0,
        "pnl_realized": 0.0,
        "pnl_unrealized": 0.0,
        "grids": [],
        "trades": [],
        "stopped": False,
        "message": "Aguardando consulta inicial da BNB Chain.",
        "last_error": "",
        "updated_at": "",
    }


def load_state():
    state = fresh_state()
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as file:
            saved = json.load(file)

        if (
            saved.get("mode") == "SIMULAÇÃO"
            and isinstance(saved.get("grids"), list)
            and len(saved["grids"]) == GRID_LEVELS
            and saved.get("reference_price") is not None
        ):
            state.update(saved)
    except (OSError, ValueError, TypeError):
        pass
    return state


STATE = load_state()


def save_state():
    try:
        temporary_file = STATE_FILE + ".tmp"
        with open(temporary_file, "w", encoding="utf-8") as file:
            json.dump(STATE, file, ensure_ascii=False)
        os.replace(temporary_file, STATE_FILE)
    except Exception as error:
        print(f"Não foi possível salvar a simulação: {error}")


def connect_bsc():
    errors = []

    for url in RPC_URLS:
        try:
            w3 = Web3(
                Web3.HTTPProvider(
                    url,
                    request_kwargs={"timeout": 8},
                )
            )

            if not w3.is_connected():
                errors.append(f"{url}: sem conexão")
                continue

            if w3.eth.chain_id != CHAIN_ID:
                errors.append(f"{url}: rede inesperada")
                continue

            if not w3.eth.get_code(ROUTER):
                errors.append(f"{url}: contrato do roteador não encontrado")
                continue

            return w3, url

        except Exception as error:
            errors.append(f"{url}: {str(error)[:120]}")

    raise RuntimeError(
        "Nenhuma RPC da BNB Chain respondeu corretamente. "
        + " | ".join(errors[:4])
    )


def get_price(w3):
    uni_contract = w3.eth.contract(address=UNI, abi=ERC20_ABI)
    usdt_contract = w3.eth.contract(address=USDT, abi=ERC20_ABI)
    router_contract = w3.eth.contract(address=ROUTER, abi=ROUTER_ABI)

    uni_decimals = uni_contract.functions.decimals().call()
    usdt_decimals = usdt_contract.functions.decimals().call()
    one_uni = 10 ** uni_decimals

    routes = [
        ([UNI, USDT], "UNI/USDT"),
        ([UNI, WBNB, USDT], "UNI/WBNB/USDT"),
    ]
    errors = []

    for route, route_name in routes:
        try:
            amounts = router_contract.functions.getAmountsOut(
                one_uni, route
            ).call()

            if amounts and amounts[-1] > 0:
                price = amounts[-1] / (10 ** usdt_decimals)
                return float(price), route_name

        except Exception as error:
            errors.append(str(error)[:120])

    raise RuntimeError(
        "A PancakeSwap não retornou cotação. "
        + (" | ".join(errors) if errors else "Rota sem preço.")
    )


def get_wallet_balances(w3):
    uni_contract = w3.eth.contract(address=UNI, abi=ERC20_ABI)
    usdt_contract = w3.eth.contract(address=USDT, abi=ERC20_ABI)

    bnb_balance = w3.eth.get_balance(READ_ONLY_WALLET) / 10**18
    uni_decimals = uni_contract.functions.decimals().call()
    usdt_decimals = usdt_contract.functions.decimals().call()

    uni_balance = (
        uni_contract.functions.balanceOf(READ_ONLY_WALLET).call()
        / (10 ** uni_decimals)
    )
    usdt_balance = (
        usdt_contract.functions.balanceOf(READ_ONLY_WALLET).call()
        / (10 ** usdt_decimals)
    )

    return {
        "bnb": float(bnb_balance),
        "uni": float(uni_balance),
        "usdt": float(usdt_balance),
    }


def initialize_grid(reference_price):
    # Cinco níveis espaçados dentro de uma faixa total de ±5%.
    step_fraction = (2 * GRID_RANGE) / GRID_LEVELS
    grids = []

    for index in range(GRID_LEVELS):
        buy_fraction = -GRID_RANGE + index * step_fraction
        sell_fraction = buy_fraction + step_fraction

        grids.append({
            "n": index + 1,
            "buy_price": reference_price * (1 + buy_fraction),
            "sell_price": reference_price * (1 + sell_fraction),
            "status": "Aguardando queda",
            "units": 0.0,
            "cost": 0.0,
            "entry_price": None,
        })

    return grids


def update_simulation(price):
    if STATE["reference_price"] is None:
        STATE["reference_price"] = price
        STATE["grids"] = initialize_grid(price)
        STATE["last_price"] = price
        STATE["message"] = "Cotação inicial registrada. Simulação pronta."
        return

    previous_price = STATE.get("last_price")
    if previous_price is None:
        STATE["last_price"] = price
        return

    if STATE["stopped"]:
        STATE["last_price"] = price
        STATE["message"] = (
            f"Simulação parada: limite de perda de "
            f"US$ {MAX_LOSS_USDT:.2f} atingido."
        )
        return

    # Venda simulada quando o preço cruza o alvo do nível para cima.
    for grid in STATE["grids"]:
        crossed_up = previous_price < grid["sell_price"] <= price

        if crossed_up and grid["units"] > 0:
            proceeds = grid["units"] * price * (1 - ESTIMATED_FEE_RATE)
            trade_pnl = proceeds - grid["cost"]

            STATE["virtual_usdt"] += proceeds
            STATE["virtual_uni"] -= grid["units"]
            STATE["pnl_realized"] += trade_pnl

            STATE["trades"].insert(0, {
                "time": datetime.now().strftime("%d/%m %H:%M:%S"),
                "type": "VENDA simulada",
                "price": price,
                "quantity": grid["units"],
                "pnl": trade_pnl,
            })

            grid["units"] = 0.0
            grid["cost"] = 0.0
            grid["entry_price"] = None
            grid["status"] = "Aguardando nova queda"

    # Compra simulada de US$ 0,20 quando o preço cruza o nível para baixo.
    for grid in STATE["grids"]:
        crossed_down = previous_price > grid["buy_price"] >= price

        if crossed_down and grid["units"] <= 0:
            if STATE["virtual_usdt"] + 1e-9 < ORDER_USDT:
                grid["status"] = "Saldo virtual insuficiente"
                continue

            spend = ORDER_USDT
            units = (spend * (1 - ESTIMATED_FEE_RATE)) / price

            STATE["virtual_usdt"] -= spend
            STATE["virtual_uni"] += units
            grid["units"] = units
            grid["cost"] = spend
            grid["entry_price"] = price
            grid["status"] = "Comprado na simulação"

            STATE["trades"].insert(0, {
                "time": datetime.now().strftime("%d/%m %H:%M:%S"),
                "type": "COMPRA simulada",
                "price": price,
                "quantity": units,
                "pnl": 0.0,
            })

    STATE["trades"] = STATE["trades"][:20]

    open_value = sum(
        grid["units"] * price
        for grid in STATE["grids"]
        if grid["units"] > 0
    )
    open_cost = sum(
        grid["cost"]
        for grid in STATE["grids"]
        if grid["units"] > 0
    )

    STATE["virtual_uni"] = sum(grid["units"] for grid in STATE["grids"])
    STATE["equity"] = STATE["virtual_usdt"] + open_value
    STATE["pnl_unrealized"] = open_value - open_cost
    STATE["pnl_total"] = STATE["equity"] - CAPITAL_USDT

    if STATE["pnl_total"] <= -MAX_LOSS_USDT:
        STATE["stopped"] = True
        STATE["message"] = (
            f"Simulação parada: limite de perda de "
            f"US$ {MAX_LOSS_USDT:.2f} atingido."
        )
    else:
        STATE["message"] = (
            "Simulação ativa. Nenhuma compra ou venda real é enviada."
        )

    STATE["last_price"] = price


def monitoring_loop():
    while True:
        try:
            w3, rpc_url = connect_bsc()
            price, route_name = get_price(w3)
            balances = get_wallet_balances(w3)

            with STATE_LOCK:
                STATE["price"] = price
                STATE["price_route"] = route_name
                STATE["rpc"] = rpc_url
                STATE["wallet_balances"] = balances
                STATE["updated_at"] = datetime.now().strftime(
                    "%d/%m/%Y %H:%M:%S"
                )
                STATE["last_error"] = ""

                update_simulation(price)
                save_state()

            print(
                f"{datetime.now().strftime('%d/%m/%Y %H:%M:%S')} "
                f"Preço UNI: ${price:.6f} | {route_name} | simulação"
            )

        except Exception as error:
            with STATE_LOCK:
                STATE["last_error"] = str(error)[:1000]
                STATE["message"] = (
                    "Falha na consulta da BNB Chain; "
                    "nenhum preço substituto será usado."
                )
                STATE["updated_at"] = datetime.now().strftime(
                    "%d/%m/%Y %H:%M:%S"
                )
                save_state()

            print(f"Erro de monitoramento: {error}")

        time.sleep(POLL_SECONDS)


def display_state():
    with STATE_LOCK:
        data = copy.deepcopy(STATE)

    data["price_text"] = (
        f"${data['price']:.6f}" if data["price"] is not None else "Aguardando"
    )
    data["reference_text"] = (
        f"${data['reference_price']:.6f}"
        if data["reference_price"] is not None
        else "Aguardando cotação"
    )

    balances = data["wallet_balances"]
    data["bnb_text"] = (
        f"{balances['bnb']:.6f} BNB"
        if balances["bnb"] is not None else "Aguardando"
    )
    data["uni_text"] = (
        f"{balances['uni']:.6f} UNI"
        if balances["uni"] is not None else "Aguardando"
    )
    data["usdt_text"] = (
        f"{balances['usdt']:.4f} USDT"
        if balances["usdt"] is not None else "Aguardando"
    )

    data["virtual_usdt_text"] = f"${data['virtual_usdt']:.4f}"
    data["virtual_uni_text"] = f"{data['virtual_uni']:.6f} UNI"
    data["equity_text"] = f"${data['equity']:.4f}"
    data["pnl_text"] = f"${data['pnl_total']:+.4f}"

    for grid in data["grids"]:
        grid["buy_text"] = f"${grid['buy_price']:.6f}"
        grid["sell_text"] = f"${grid['sell_price']:.6f}"

    for trade in data["trades"]:
        trade["price_text"] = f"${trade['price']:.6f}"
        trade["quantity_text"] = f"{trade['quantity']:.6f} UNI"
        trade["pnl_text"] = f"${trade['pnl']:+.4f}"

    return data


HTML = """
<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="refresh" content="12">
  <title>UNI Grid | Simulação</title>
  <style>
    *{box-sizing:border-box}
    body{margin:0;background:#0b1020;color:#e8edf7;font-family:Arial,sans-serif}
    main{max-width:1100px;margin:auto;padding:20px}
    h1{font-size:24px;margin:0 0 6px}
    h2{font-size:17px;margin:0 0 12px}
    .muted,.small{color:#9aa8c0;font-size:13px;line-height:1.55}
    .notice{margin:16px 0;padding:14px;border:1px solid #e0a52b;
      background:#2a2111;border-radius:12px;color:#ffe1a1;line-height:1.5}
    .cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px}
    .card,.panel{background:#141c2e;border:1px solid #26344c;
      border-radius:14px;padding:16px}
    .label{color:#9aa8c0;font-size:12px;text-transform:uppercase;letter-spacing:.05em}
    .value{font-size:24px;font-weight:700;margin-top:8px;overflow-wrap:anywhere}
    .panel{margin-top:14px}
    .status{padding:10px 12px;border-radius:10px;background:#101a2b;
      margin-top:12px;overflow-wrap:anywhere}
    .wrap{overflow-x:auto}
    table{border-collapse:collapse;width:100%;min-width:540px}
    th,td{text-align:left;padding:10px;border-bottom:1px solid #26344c;font-size:13px}
    th{color:#9aa8c0}
    .good{color:#68e0a1}.bad{color:#ff8787}
    @media(max-width:480px){
      main{padding:14px}
      .value{font-size:21px}
      h1{font-size:21px}
    }
  </style>
</head>
<body>
<main>
  <h1>UNI/USDT · Grid em simulação</h1>
  <div class="muted">BNB Smart Chain · PancakeSwap · atualização automática</div>

  <div class="notice">
    <b>Somente leitura e simulação.</b> Consulta cotação e saldos públicos.
    Não usa chave privada, não aprova tokens e não envia transações reais.
  </div>

  <div class="cards">
    <div class="card">
      <div class="label">Preço UNI consultado</div>
      <div class="value">{{ state.price_text }}</div>
      <div class="small">{{ state.price_route or "Sem cotação" }}</div>
    </div>
    <div class="card">
      <div class="label">USDT virtual</div>
      <div class="value">{{ state.virtual_usdt_text }}</div>
    </div>
    <div class="card">
      <div class="label">UNI virtual</div>
      <div class="value">{{ state.virtual_uni_text }}</div>
    </div>
    <div class="card">
      <div class="label">Resultado simulado</div>
      <div class="value {% if state.pnl_total >= 0 %}good{% else %}bad{% endif %}">
        {{ state.pnl_text }}
      </div>
    </div>
  </div>

  <div class="status">
    <b>Status:</b> {{ state.message }}<br>
    <span class="small">
      Atualizado: {{ state.updated_at or "aguardando" }} ·
      Preço inicial: {{ state.reference_text }}
    </span>
  </div>

  <section class="panel">
    <h2>Saldos reais consultados, somente leitura</h2>
    <div class="small">Carteira: {{ state.wallet }}</div>
    <div class="cards" style="margin-top:12px">
      <div><div class="label">BNB</div><b>{{ state.bnb_text }}</b></div>
      <div><div class="label">UNI</div><b>{{ state.uni_text }}</b></div>
      <div><div class="label">USDT</div><b>{{ state.usdt_text }}</b></div>
    </div>
  </section>

  <section class="panel">
    <h2>Configuração do teste</h2>
    <div class="small">
      Capital virtual: US$ 1,00 · 5 níveis em ±5% · US$ 0,20 por nível ·
      limite de perda: US$ 0,10 · slippage de referência: 1% ·
      custo estimado da simulação: 0,30% por operação.
      O slippage não se aplica, pois não há transações reais.
    </div>
  </section>

  <section class="panel">
    <h2>Níveis do grid</h2>
    <div class="wrap">
      <table>
        <thead>
          <tr><th>Nível</th><th>Compra simulada</th><th>Venda simulada</th><th>Status</th></tr>
        </thead>
        <tbody>
        {% for grid in state.grids %}
          <tr>
            <td>G{{ grid.n }}</td>
            <td>{{ grid.buy_text }}</td>
            <td>{{ grid.sell_text }}</td>
            <td>{{ grid.status }}</td>
          </tr>
        {% else %}
          <tr><td colspan="4">Aguardando cotação inicial da PancakeSwap.</td></tr>
        {% endfor %}
        </tbody>
      </table>
    </div>
  </section>

  <section class="panel">
    <h2>Últimas operações simuladas</h2>
    <div class="wrap">
      <table>
        <thead>
          <tr><th>Data</th><th>Tipo</th><th>Preço</th><th>Quantidade</th><th>Resultado</th></tr>
        </thead>
        <tbody>
        {% for trade in state.trades %}
          <tr>
            <td>{{ trade.time }}</td>
            <td>{{ trade.type }}</td>
            <td>{{ trade.price_text }}</td>
            <td>{{ trade.quantity_text }}</td>
            <td>{{ trade.pnl_text }}</td>
          </tr>
        {% else %}
          <tr><td colspan="5">Ainda sem operações simuladas.</td></tr>
        {% endfor %}
        </tbody>
      </table>
    </div>
  </section>

  {% if state.last_error %}
  <section class="panel bad">
    <b>Erro na consulta:</b> {{ state.last_error }}
  </section>
  {% endif %}

  <section class="panel small">
    RPC atual: {{ state.rpc or "ainda não conectada" }}<br>
    Patrimônio virtual: {{ state.equity_text }} ·
    carteira real consultada sem permissão para movimentar fundos.
  </section>
</main>
</body>
</html>
"""


@app.route("/")
@app.route("/dashboard")
def dashboard():
    return render_template_string(HTML, state=display_state())


@app.route("/api/status")
def api_status():
    return jsonify(display_state())


@app.route("/health")
def health():
    return jsonify({"status": "ok", "mode": "simulacao"})


def start_monitor():
    if not getattr(app, "_monitor_started", False):
        app._monitor_started = True
        threading.Thread(target=monitoring_loop, daemon=True).start()


start_monitor()


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", "10000"))
    )
