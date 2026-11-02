import streamlit as st
import os
import pandas as pd

st.set_page_config(page_title="Painel Grid - Estilo Neio", layout="wide")

# Mapeamento: o que aparece -> o que manda pra Gate
MAPA_TOKENS = {
    "BOLO": "CAKE",
    "UNI": "UNI",
    "BNB": "BNB",
    "AAVE": "AAVE",
    "BTC": "BTC",
    "ETH": "ETH"
}

TOKENS_PADRAO = [
    {"nome": "UNI", "abaixo": 15, "acima": 15, "dist": 3.0, "valor": 15, "ativo": True},
    {"nome": "BNB", "abaixo": 15, "acima": 15, "dist": 3.0, "valor": 15, "ativo": True},
    {"nome": "AAVE", "abaixo": 15, "acima": 15, "dist": 3.0, "valor": 15, "ativo": True},
    {"nome": "BTC", "abaixo": 15, "acima": 15, "dist": 3.0, "valor": 15, "ativo": True},
    {"nome": "ETH", "abaixo": 15, "acima": 15, "dist": 3.0, "valor": 15, "ativo": True},
    {"nome": "BOLO", "abaixo": 15, "acima": 15, "dist": 3.0, "valor": 10, "ativo": True},
]

if "tokens" not in st.session_state:
    st.session_state.tokens = TOKENS_PADRAO.copy()

st.markdown("<h1>Painel Grid Bot - Estilo Neio</h1>", unsafe_allow_html=True)

# Totais
total_pedidos = sum((t["abaixo"]+t["acima"]) for t in st.session_state.tokens if t["ativo"])
total_invest = sum((t["abaixo"]+t["acima"])*t["valor"] for t in st.session_state.tokens if t["ativo"])
pares_ativos = sum(1 for t in st.session_state.tokens if t["ativo"])

c1, c2, c3 = st.columns(3)
c1.metric("TOTAL DE PEDIDOS", total_pedidos, "Ordens ativas geradas")
c2.metric("INVESTIMENTO TOTAL", f"{total_invest} USDT")
c3.metric("STATUS DO BOT", "ATIVO", f"{pares_ativos} pares")

st.markdown("### Configuracao dos Bots - Grid Trading")

# CABECALHO
h = st.columns([1, 1.5, 1.5, 1.5, 1.5, 0.8, 0.6])
h[0].markdown("**TOKEN**")
h[1].markdown("**GRIDS ABAIXO**")
h[2].markdown("**GRIDS ACIMA**")
h[3].markdown("**% DISTANCIA**")
h[4].markdown("**VALOR POR 1 GRID**")
h[5].markdown("**ATIVO**")

for idx, token in enumerate(st.session_state.tokens):
    cols = st.columns([1, 1.5, 1.5, 1.5, 1.5, 0.8, 0.6])
    cols[0].markdown(f"**{token['nome']}**")
    token["abaixo"] = cols[1].number_input(f"ab_{idx}", 1, 100, token["abaixo"], label_visibility="collapsed", key=f"ab_{idx}")
    token["acima"] = cols[2].number_input(f"ac_{idx}", 1, 100, token["acima"], label_visibility="collapsed", key=f"ac_{idx}")
    token["dist"] = cols[3].number_input(f"dist_{idx}", 0.1, 20.0, float(token["dist"]), label_visibility="collapsed", key=f"dist_{idx}")
    token["valor"] = cols[4].number_input(f"val_{idx}", 1, 10000, token["valor"], label_visibility="collapsed", key=f"val_{idx}", help="Valor de CADA grid")
    token["ativo"] = cols[5].checkbox("SOBRE", token["ativo"], key=f"at_{idx}")
    if cols[6].button("❌", key=f"del_{idx}"):
        st.session_state.tokens.pop(idx)
        st.rerun()

st.markdown("---")
novo_nome = st.text_input("Novo Token (ex: SOL)").upper()
if st.button("Adicionar Token"):
    if novo_nome:
        st.session_state.tokens.append({"nome": novo_nome, "abaixo": 15, "acima": 15, "dist": 3.0, "valor": 15, "ativo": True})
        st.rerun()

if st.button("💾 Salvar e Zerar Planilha", type="primary", use_container_width=True):
    config_gate = [{"par": f"{MAPA_TOKENS.get(t['nome'], t['nome'])}_USDT", **t} for t in st.session_state.tokens]
    st.success(f"Salvo! BOLO enviado como CAKE")
    st.json(config_gate)
