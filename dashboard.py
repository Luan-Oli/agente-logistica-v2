import streamlit as st
import pandas as pd
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import folium
from streamlit_folium import st_folium
import requests
import time
from datetime import datetime

st.set_page_config(page_title="Agente Logística V2.9", layout="wide")

# --- MEMÓRIA DA SESSÃO ---
if 'consultores_base' not in st.session_state:
    st.session_state.consultores_base = pd.DataFrame()
if 'resultado' not in st.session_state:
    st.session_state.resultado = None

st.title("🤖 Agente de Logística: Painel Completo V2.9")

# --- BARRA LATERAL ---
with st.sidebar:
    st.header("📁 Gestão de Dados")
    arquivo_excel = st.file_uploader("Carregar Excel (.xlsx)", type=["xlsx"])
    
    if arquivo_excel:
        try:
            df_input = pd.read_excel(arquivo_excel)
            # LIMPEZA CRÍTICA: Remove espaços extras nos nomes das colunas
            df_input.columns = df_input.columns.astype(str).str.strip()
            st.session_state.consultores_base = df_input
            st.success("Excel carregado e colunas sincronizadas!")
        except Exception as e:
            st.error(f"Erro ao ler arquivo: {e}")

    mes_selecionado = None
    if not st.session_state.consultores_base.empty:
        st.divider()
        st.header("🗓️ Mês de Referência")
        lista_meses = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho', 
                       'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro']
        mes_atual_idx = datetime.now().month - 1
        mes_selecionado = st.selectbox("Selecione o mês:", options=lista_meses, index=mes_atual_idx)

    if st.button("Limpar Tudo"):
        st.session_state.consultores_base = pd.DataFrame()
        st.session_state.resultado = None
        st.rerun()

# --- ÁREA DE PROCESSAMENTO E TABELA ---
if not st.session_state.consultores_base.empty:
    df_temp = st.session_state.consultores_base.copy()
    
    # 1. TRATAMENTO DA OCUPAÇÃO (Converte "52,38%" para número)
    if mes_selecionado in df_temp.columns:
        df_temp['Ocupacao'] = df_temp[mes_selecionado].astype(str).str.replace('%', '').str.replace(',', '.').astype(float)
    else:
        st.warning(f"Coluna '{mes_selecionado}' não encontrada. Verifique o Excel.")
        df_temp['Ocupacao'] = 0.0

    # 2. EXIBIÇÃO DA TABELA (Garante que Unidade apareça)
    st.subheader(f"📋 Consultores e Disponibilidade - {mes_selecionado}")
    
    # Verificação de segurança para as colunas existirem antes de mostrar
    colunas_finais = ['Consultor', 'Unidade', 'Ocupacao']
    colunas_disponiveis = [c for c in colunas_finais if c in df_temp.columns]
    
    st.dataframe(df_temp[colunas_disponiveis], use_container_width=True)

    st.divider()
    destino = st.text_input("📍 Informe a Cidade de Destino (Ex: Xangri-la):")

    if st.button("CALCULAR MELHOR LOGÍSTICA", type="primary"):
        geolocator = Nominatim(user_agent=f"agente_luan_{int(time.time())}", timeout=20)
        loc_dest = geolocator.geocode(f"{destino}, RS, Brasil")

        if loc_dest:
            with st.spinner("Analisando rotas e unidades..."):
                def analisar(row):
                    time.sleep(1.2)
                    l = geolocator.geocode(f"{row['Unidade']}, RS, Brasil")
                    if l:
                        # (Lógica de rota real simplificada para o exemplo)
                        dist = geodesic((l.latitude, l.longitude), (loc_dest.latitude, loc_dest.longitude)).km
                        return pd.Series([dist, (l.latitude, l.longitude)])
                    return pd.Series([9999, None])

                df_temp[['Distancia', 'Coords']] = df_temp.apply(analisar, axis=1)
                venc = df_temp.sort_values(by=['Ocupacao', 'Distancia']).iloc[0]
                st.session_state.resultado = {'vencedor': venc, 'dest_coords': (loc_dest.latitude, loc_dest.longitude)}
        else:
            st.error("Cidade de destino não encontrada.")

    # --- MAPA PERSISTENTE ---
    if st.session_state.resultado:
        res = st.session_state.resultado
        v = res['vencedor']
        
        st.info(f"🏆 Melhor Escolha: **{v['Consultor']}** ({v['Unidade']})")
        c1, c2 = st.columns(2)
        c1.metric("Distância", f"{v['Distancia']:.1f} km")
        c2.metric(f"Ocupação ({mes_selecionado})", f"{v['Ocupacao']:.1f}%")
else:
    st.info("💡 Carregue o arquivo Excel na lateral para visualizar a tabela completa.")
