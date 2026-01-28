import streamlit as st
import pandas as pd
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import folium
from streamlit_folium import st_folium
import requests
import time
from datetime import datetime

st.set_page_config(page_title="Agente Logística V3.0", layout="wide")

# --- MEMÓRIA DA SESSÃO ---
if 'consultores_base' not in st.session_state:
    st.session_state.consultores_base = pd.DataFrame()
if 'resultado' not in st.session_state:
    st.session_state.resultado = None

st.title("🤖 Agente de Logística: Painel Inteligente V3.0")

# --- BARRA LATERAL: IMPORTAÇÃO ---
with st.sidebar:
    st.header("📁 Gestão de Dados")
    # Certifique-se de subir o arquivo .xlsx real, não o atalho .url
    arquivo_excel = st.file_uploader("Carregar Excel (.xlsx)", type=["xlsx"])
    
    if arquivo_excel:
        try:
            # Lógica para encontrar o cabeçalho correto se houver lixo no topo do Excel
            df_input = pd.read_excel(arquivo_excel)
            
            # Limpa espaços em branco nos nomes das colunas
            df_input.columns = df_input.columns.astype(str).str.strip()
            
            # Se a coluna 'Consultor' estiver dentro dos dados, removemos a linha intrusa
            df_input = df_input[df_input['Consultor'] != 'Consultor']
            df_input = df_input.dropna(subset=['Consultor']) # Remove linhas vazias
            
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

# --- EXIBIÇÃO DA TABELA CORRIGIDA ---
if not st.session_state.consultores_base.empty:
    df_temp = st.session_state.consultores_base.copy()
    
    # TRATAMENTO DA OCUPAÇÃO: Transforma "52,38%" em 52.38
    if mes_selecionado in df_temp.columns:
        df_temp['Ocupacao'] = df_temp[mes_selecionado].astype(str).str.replace('%', '').str.replace(',', '.').astype(float)
    else:
        st.warning(f"Coluna '{mes_selecionado}' não encontrada. Verifique os títulos no Excel.")
        df_temp['Ocupacao'] = 0.0

    # FIX: Subheader fechado corretamente para evitar SyntaxError
    st.subheader(f"📋 Consultores e Disponibilidade - {mes_selecionado}")
    
    # Exibe especificamente as colunas que você quer ver
    colunas_finais = ['Consultor', 'Unidade', 'Ocupacao']
    # Garante que só tentamos exibir o que existe no DataFrame
    colunas_disponiveis = [c for c in colunas_finais if c in df_temp.columns]
    
    st.dataframe(df_temp[colunas_disponiveis], use_container_width=True)

    st.divider()
    destino = st.text_input("📍 Informe a Cidade de Destino:")

    if st.button("CALCULAR MELHOR LOGÍSTICA", type="primary"):
        geolocator = Nominatim(user_agent=f"agente_v3_{int(time.time())}", timeout=20)
        loc_dest = geolocator.geocode(f"{destino}, RS, Brasil")

        if loc_dest:
            with st.spinner("Analisando rotas..."):
                def analisar(row):
                    time.sleep(1.2)
                    l = geolocator.geocode(f"{row['Unidade']}, RS, Brasil")
                    if l:
                        dist = geodesic((l.latitude, l.longitude), (loc_dest.latitude, loc_dest.longitude)).km
                        return pd.Series([dist, (l.latitude, l.longitude)])
                    return pd.Series([9999, None])

                df_temp[['Distancia', 'Coords']] = df_temp.apply(analisar, axis=1)
                venc = df_temp.sort_values(by=['Ocupacao', 'Distancia']).iloc[0]
                st.session_state.resultado = {'vencedor': venc, 'dest_coords': (loc_dest.latitude, loc_dest.longitude)}
        else:
            st.error("Cidade não encontrada.")

    # --- RESULTADOS ---
    if st.session_state.resultado:
        res = st.session_state.resultado
        v = res['vencedor']
        st.success(f"🏆 Melhor Sugestão: **{v['Consultor']}** de **{v['Unidade']}**")
        st.metric("Distância", f"{v['Distancia']:.1f} km")
