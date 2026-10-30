# bot.py - VERSÃO COM TRAVA ANTES DE ZERAR O BNB
from web3 import Web3
import time
from datetime import datetime

W3 = Web3(Web3.HTTPProvider("https://bsc-dataseed.binance.org/"))
CARTEIRA = "0x8AEE...82Fd3" # COLOCA SEU ENDEREÇO COMPLETO AQUI

# --- CONFIG DAS TRAVAS (NÃO MEXER NO EXCEL) ---
MIN_BNB = 0.0005  # Se tiver menos que isso ($0,35) ele PARA antes de zerar
MAX_FALHAS_SEGUIDAS = 3
MAX_GASTO_DIA_USD = 0.30
GAS_ESCALONADO_GWEI = [0.35, 0.7, 1.0] # $0,01 / $0,02 / $0,03
SLIPPAGE = 1.5

falhas = {}
gasto_hoje_usd = 0.0

def get_bnb():
    bal = W3.eth.get_balance(CARTEIRA)
    return float(W3.from_wei(bal, 'ether'))

def pode_operar(grid_id):
    global gasto_hoje_usd
    bnb = get_bnb()
    
    # TRAVA 1 - Para ANTES de acabar
    if bnb < MIN_BNB:
        print(f"[{datetime.now()}] ⛔ TRAVADO! BNB atual {bnb:.7f} < {MIN_BNB}. Tem ${bnb*704:.2f} ainda. Recarregue antes de zerar!")
        return False
    
    # TRAVA 3 - Gasto do dia
    if gasto_hoje_usd >= MAX_GASTO_DIA_USD:
        print(f"[{datetime.now()}] ⛔ TRAVADO! Já gastou ${gasto_hoje_usd:.2f} em falhas hoje.")
        return False
        
    # TRAVA 2 - Mesmo grid falhando
    if falhas.get(grid_id, 0) >= MAX_FALHAS_SEGUIDAS:
        print(f"[{datetime.now()}] ⏸️ Grid {grid_id} pausado após 3 falhas.")
        return False
        
    return True

def comprar_grid(grid_id, qtd_uni, preco):
    global gasto_hoje_usd
    if not pode_operar(grid_id):
        return False

    for gwei in GAS_ESCALONADO_GWEI:
        try:
            print(f"Tentando {grid_id} com {gwei} gwei...")
            # AQUI VAI SUA CHAMADA DA PANCAKE COM SLIPPAGE 1.5%
            # ex: router.functions.swapExactTokensForTokens(...)
            
            # Se chegou aqui, deu certo
            falhas[grid_id] = 0
            print(f"✅ {grid_id} COMPRADO com {gwei} gwei")
            return True

        except Exception as e:
            err = str(e).lower()
            custo_usd = gwei * 0.028 # aprox
            gasto_hoje_usd += custo_usd

            if "insufficient funds" in err:
                print(f"⛔ ERRO FATAL: Sem BNB! Parando tudo. {e}")
                return False # para na hora, não tenta próximo gwei

            falhas[grid_id] = falhas.get(grid_id, 0) + 1
            print(f"⚠️ Falha {grid_id}: {e}. Gasto hoje ${gasto_hoje_usd:.3f}")
            time.sleep(3)
            continue
            
    return False

# SEU LOOP PRINCIPAL CONTINUA IGUAL
# while True:
#    comprar_grid("G7", ...)
