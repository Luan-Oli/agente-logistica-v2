import streamlit as st
import pandas as pd
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import folium
from streamlit_folium import st_folium
import requests
import time
from datetime import datetime

# Configuração da Página
st.set_page_config(page_title="Agente Logística V2.7", layout="wide")

# --- FUNÇÃO DE ROTA REAL (OSRM) ---
def buscar_rota_real(ponto_a, ponto_b):
    url = f"http://router.project-osrm.org/route/v1/driving/{ponto_a[1]},{ponto_a[0]};{ponto_b[1]},{ponto_b[0]}?overview=full&geometries=geojson"
    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        if data['code'] == 'Ok':
            rota = [[p[1], p[0]] for p in data['routes'][0]['geometry']['coordinates']]
            distancia = data['routes'][0]['distance'] / 1000
            return rota, distancia
    except:
        return None, None

# --- MEMÓRIA DA SESSÃO ---
if 'consultores_base' not in st.session_state:
    st.session_state.consultores_base = pd.DataFrame()
if 'resultado' not in st.session_state:
    st.session_state.resultado = None

st.title("🤖 Agente de Logística: Planeamento e Rotas V2.7")

# --- BARRA LATERAL: GESTÃO E PLANEAMENTO ---
with st.sidebar:
    st.header("📁 Gestão de Dados")
    arquivo_excel = st.file_uploader("Carregar Excel (.xlsx)", type=["xlsx"])
    
    if arquivo_excel:
        try:
            st.session_state.consultores_base = pd.read_excel(arquivo_excel)
            st.success("Excel carregado com sucesso!")
        except Exception as e:
            st.error(f"Erro ao ler ficheiro: {e}")

    # --- NOVO: SELETOR DE MÊS PARA SIMULAÇÃO ---
    mes_selecionado = None
    if not st.session_state.consultores_base.empty:
        st.divider()
        st.header("🗓️ Planeamento")
        
        lista_meses = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho', 
                       'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro']
        
        # Define o mês atual como padrão
        mes_atual_nome = lista_meses[datetime.now().month - 1]
        
        mes_selecionado = st.selectbox(
            "Selecionar Mês de Referência:",
            options=lista_meses,
            index=lista_meses.index(mes_atual_nome),
            help="O sistema usará a ocupação deste mês para o cálculo."
        )

    # FILTRO POR UNIDADE
    unidades_selecionadas = []
    if not st.session_state.consultores_base.empty:
        st.divider()
        st.header("🔍 Filtrar Unidades")
        todas_unidades = sorted(st.session_state.consultores_base['Unidade'].unique())
        unidades_selecionadas = st.multiselect(
            "Unidades Ativas:",
            options=todas_unidades,
            default=todas_unidades
        )

    if st.button("Limpar Tudo"):
        st.session_state.consultores_base = pd.DataFrame()
        st.session_state.resultado = None
        st.rerun()

# --- ÁREA DE PROCESSAMENTO ---
if not st.session_state.consultores_base.empty:
    df_temp = st.session_state.consultores_base.copy()
    
    # Validação e Limpeza da Coluna de Ocupação do Mês Selecionado
    if mes_selecionado in df_temp.columns:
        # Trata formatos como "52,38%" para números flutuantes
        df_temp['Ocupacao'] = df_temp[mes_selecionado].astype(str).str.replace('%', '').str.replace(',', '.').astype(float)
    else:
        st.warning(f"A coluna '{mes_selecionado}' não existe no Excel. Ocupação definida como 0%.")
        df_temp['Ocupacao'] = 0.0

    # Aplica filtro de unidade
    df_filtrado = df_temp[df_temp['Unidade'].isin(unidades_selecionadas)]
    
    st.subheader(f"📋 Consultores Dispon
