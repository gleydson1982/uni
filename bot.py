import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import time

st.set_page_config(page_title="Painel Grid - Estilo Neio", layout="wide", page_icon="🤖")

# --- ESTILO DARK IGUAL DA IMAGEM ---
st.markdown("""
<style>
.stApp {background-color: #0a0e15;}
</style>
""", unsafe_allow_html=True)

st.title("Painel Grid Bot - Estilo Neio")

# --- ESTADO INICIAL COM SEUS 6 TOKENS ---
if 'tokens_config' not in st.session_state:
    st.session_state.tokens_config = {
        "UNI":  {"baixo": 15, "cima": 15, "pct": 3.0, "valor": 15, "ativo": True},
        "CAKE": {"baixo": 15, "cima": 15, "pct": 3.0, "valor": 15, "ativo": True},
        "BNB":  {"baixo": 15, "cima": 15, "pct": 3.0, "valor": 15, "ativo": True},
        "AAVE": {"baixo": 15, "cima": 15, "pct": 3.0, "valor": 15, "ativo": True},
        "BTC":  {"baixo": 15, "cima": 15, "pct": 3.0, "valor": 15, "ativo": True},
        "ETH":  {"baixo": 15, "cima": 15, "pct": 3.0, "valor": 15, "ativo": True},
    }

# --- CARDS TOPO ---
total_ordens = sum((v["baixo"] + v["cima"]) for v in st.session_state.tokens_config.values() if v["ativo"])
total_usdt = sum((v["baixo"] + v["cima"]) * v["valor"] for v in st.session_state.tokens_config.values() if v["ativo"])

col1, col2, col3 = st.columns(3)
col1.metric("TOTAL ORDERS", f"{total_ordens}", "Ordens ativas geradas")
col2.metric("TOTAL USDT INVESTIDO", f"{total_usdt:,.2f} USDT", "Investimento total ativo")
col3.metric("BOT STATUS", "ATIVO", f"{len([k for k,v in st.session_state.tokens_config.items() if v['ativo']])} pares em operação")

st.subheader("Configuração dos Bots - Grid Trading")

# --- TABELA EDITÁVEL POR TOKEN ---
for token, cfg in list(st.session_state.tokens_config.items()):
    c1, c2, c3, c4, c5, c6, c7 = st.columns([1, 1, 1, 1, 1, 1, 0.5])
    with c1: st.write(f"**{token}**")
    with c2: cfg["baixo"] = st.number_input(f"Baixo {token}", 0, 30, cfg["baixo"], key=f"baixo_{token}", label_visibility="collapsed")
    with c3: cfg["cima"] = st.number_input(f"Cima {token}", 0, 30, cfg["cima"], key=f"cima_{token}", label_visibility="collapsed")
    with c4: cfg["pct"] = st.number_input(f"% {token}", 0.5, 10.0, cfg["pct"], key=f"pct_{token}", label_visibility="collapsed")
    with c5: cfg["valor"] = st.number_input(f"Valor {token}", 5, 1000, cfg["valor"], key=f"valor_{token}", label_visibility="collapsed")
    with c6: cfg["ativo"] = st.checkbox("ON", cfg["ativo"], key=f"on_{token}")
    with c7: 
        if st.button("❌", key=f"del_{token}"):
            del st.session_state.tokens_config[token]
            st.rerun()

# --- ADICIONAR NOVO TOKEN ---
st.divider()
st.write("### ➕ Adicionar Novo Token")
c_add1, c_add2, c_add3 = st.columns([2, 2, 2])
with c_add1: novo_token = st.text_input("Nome do Token (ex: SOL)", placeholder="SOL").upper()
with c_add2: novo_valor = st.number_input("Valor por Grid", 5, 1000, 15)
with c_add3:
    st.write("")
    if st.button("Adicionar Token", type="primary"):
        if novo_token and novo_token not in st.session_state.tokens_config:
            st.session_state.tokens_config[novo_token] = {"baixo": 15, "cima": 15, "pct": 3.0, "valor": novo_valor, "ativo": True}
            st.success(f"{novo_token} adicionado!")
            st.rerun()

# --- BOTÕES FINAIS ---
if st.button("💾 SALVAR CONFIGURAÇÃO E ZERAR PLANILHA + INICIAR GRID", type="primary", use_container_width=True):
    # AQUI ENTRA SUA FUNÇÃO DE ZERAR PLANILHA E CRIAR GRIDS NA GATE
    st.success(f"Planilha zerada! {total_ordens} ordens criadas na Gate.io para {total_usdt} USDT")
    st.balloons()
