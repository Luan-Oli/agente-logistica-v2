import streamlit as st
import pandas as pd
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import folium
from streamlit_folium import st_folium
import requests
import time
from datetime import datetime

st.set_page_config(page_title="Agente Logística V3.1", layout="wide")

# --- MEMÓRIA DA SESSÃO ---
if 'consultores_base' not in st.session_state:
    st.session_state.consultores_base = pd.DataFrame()
if 'resultado' not in st.session_state:
    st.session_state.resultado = None

st.title("🤖 Agente de Logística: Painel Completo V3.1")

# --- BARRA LATERAL: IMPORTAÇÃO ---
with st.sidebar:
    st.header("📁 Gestão de Dados")
    # Lembrete: Carregue o .xlsx real, não o atalho .url
    arquivo_excel = st.file_uploader("Carregar Excel (.xlsx)", type=["xlsx"])
    
    if arquivo_excel:
        try:
            # Lê o Excel e limpa espaços extras nos nomes das colunas
            df_input = pd.read_excel(arquivo_excel)
            df_input.columns = df_input.columns.astype(str).str.strip()
            
            # Remove linhas que repetem o cabeçalho ou estão vazias
            df_input = df_input[df_input['Consultor'] != 'Consultor'].dropna(subset=['Consultor'])
            
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

# --- ÁREA DA TABELA E CÁLCULOS ---
if not st.session_state.consultores_base.empty:
    df_temp = st.session_state.consultores_base.copy()
    
    # TRATAMENTO DE DADOS: Transforma "52,38%" em número real
    if mes_selecionado in df_temp.columns:
        df_temp['Ocupacao'] = df_temp[mes_selecionado].astype(str).str.replace('%', '').str.replace(',', '.').astype(float)
    else:
        st.warning(f"Coluna '{mes_selecionado}' não encontrada no Excel.")
        df_temp['Ocupacao'] = 0.0

    # FIX LINHA 98: Sintaxe corrigida para evitar o erro de SyntaxError
    st.subheader(f"📋 Consultores Disponíveis - {mes_selecionado}")
    
    # Exibe especificamente as colunas desejadas
    colunas_finais = ['Consultor', 'Unidade', 'Ocupacao']
    # Garante que as colunas existem antes de exibir para evitar erros de KeyError
    colunas_para_exibir = [c for c in colunas_finais if c in df_temp.columns]
    
    st.dataframe(df_temp[colunas_para_exibir], use_container_width=True)

    st.divider()
    destino = st.text_input("📍 Informe a Cidade de Destino:")

    if st.button("CALCULAR MELHOR LOGÍSTICA", type="primary"):
        geolocator = Nominatim(user_agent=f"agente_v31_{int(time.time())}", timeout=20)
        loc_dest = geolocator.geocode(f"{destino}, RS, Brasil")

        if loc_dest:
            with st.spinner("Analisando rotas reais..."):
                def analisar(row):
                    time.sleep(1.2)
                    l = geolocator.geocode(f"{row['Unidade']}, RS, Brasil")
                    if l:
                        origem = (l.latitude, l.longitude)
                        dest_c = (loc_dest.latitude, loc_dest.longitude)
                        # Cálculo de distância simples para garantir a funcionalidade
                        dist = geodesic(origem, dest_c).km
                        return pd.Series([dist, origem])
                    return pd.Series([9999, None])

                df_temp[['Distancia', 'Coords']] = df_temp.apply(analisar, axis=1)
                venc = df_temp.sort_values(by=['Ocupacao', 'Distancia']).iloc[0]
                st.session_state.resultado = {'vencedor': venc, 'dest_coords': (loc_dest.latitude, loc_dest.longitude)}
        else:
            st.error("Cidade não localizada.")

    # --- RESULTADOS ---
    if st.session_state.resultado:
        res = st.session_state.resultado
        v = res['vencedor']
        st.success(f"🏆 Melhor Sugestão: **{v['Consultor']}** ({v['Unidade']})")
        st.metric("Distância", f"{v['Distancia']:.1f} km")
else:
    st.info("💡 Arraste o arquivo Excel para a lateral para visualizar a tabela.")
