import streamlit as st
import pandas as pd
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import folium
from streamlit_folium import st_folium
import requests
import time
from datetime import datetime

# Configuração da Página para evitar o erro de largura
st.set_page_config(page_title="Agente Logística V3.2", layout="wide")

# --- FUNÇÃO DE ROTA REAL ---
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
if 'base' not in st.session_state:
    st.session_state.base = pd.DataFrame()
if 'resultado' not in st.session_state:
    st.session_state.resultado = None

st.title("🤖 Agente de Logística: Painel de Precisão V3.2")

# --- BARRA LATERAL: GESTÃO ---
with st.sidebar:
    st.header("📁 Gestão de Dados")
    # Lembrete: Arraste o .xlsx real, não o atalho .url
    arquivo = st.file_uploader("Carregar Excel (.xlsx)", type=["xlsx"])
    
    if arquivo:
        try:
            df_input = pd.read_excel(arquivo)
            # LIMPEZA: Remove espaços nos nomes das colunas e garante que são strings
            df_input.columns = df_input.columns.astype(str).str.strip()
            # Remove linhas vazias ou repetidas
            df_input = df_input.dropna(subset=['Consultor'])
            st.session_state.base = df_input
            st.success("Dados sincronizados com sucesso!")
        except Exception as e:
            st.error(f"Erro ao ler arquivo: {e}")

    mes_ref = None
    if not st.session_state.base.empty:
        st.divider()
        lista_meses = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho', 
                       'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro']
        mes_atual_idx = datetime.now().month - 1
        mes_ref = st.selectbox("Selecione o Mês:", options=lista_meses, index=mes_atual_idx)

    if st.button("Limpar Sistema"):
        st.session_state.base = pd.DataFrame()
        st.session_state.resultado = None
        st.rerun()

# --- EXIBIÇÃO DA TABELA COMPLETA ---
if not st.session_state.base.empty:
    df_temp = st.session_state.base.copy()
    
    # 1. TRATAMENTO DA OCUPAÇÃO (Mês Selecionado)
    if mes_ref in df_temp.columns:
        # Transforma "52,38%" (texto) em 52.38 (número)
        df_temp['Ocupacao'] = df_temp[mes_ref].astype(str).str.replace('%', '').str.replace(',', '.').astype(float)
    else:
        st.warning(f"Coluna {mes_ref} não encontrada. Usando 0%.")
        df_temp['Ocupacao'] = 0.0

    # 2. TABELA COM CONSULTOR, UNIDADE E OCUPAÇÃO
    # FIX: Subheader com f-string corrigido (sem SyntaxError)
    st.subheader(f"📋 Equipa: {mes_ref}")
    
    # Selecionamos apenas as 3 colunas que você quer ver
    cols_vistas = ['Consultor', 'Unidade', 'Ocupacao']
    st.dataframe(df_temp[cols_vistas], use_container_width=True)

    st.divider()
    destino = st.text_input("📍 Informe a Cidade do Cliente (RS):")

    if st.button("CALCULAR MELHOR LOGÍSTICA", type="primary"):
        geolocator = Nominatim(user_agent=f"agente_v32_{int(time.time())}", timeout=20)
        loc_dest = geolocator.geocode(f"{destino}, RS, Brasil")

        if loc_dest:
            with st.spinner("Calculando rotas reais pelas estradas..."):
                def analisar(row):
                    time.sleep(1.2) # Segurança do Geopy
                    l = geolocator.geocode(f"{row['Unidade']}, RS, Brasil")
                    if l:
                        origem = (l.latitude, l.longitude)
                        dest_c = (loc_dest.latitude, loc_dest.longitude)
                        cam, km = buscar_rota_real(origem, dest_c)
                        if not km: km = geodesic(origem, dest_c).km
                        return pd.Series([km, origem, cam])
                    return pd.Series([9999, None, None])

                df_temp[['Distancia', 'Coords', 'Trajeto']] = df_temp.apply(analisar, axis=1)
                venc = df_temp.sort_values(by=['Ocupacao', 'Distancia']).iloc[0]
                st.session_state.resultado = {'venc': venc, 'dest': (loc_dest.latitude, loc_dest.longitude)}
        else:
            st.error("Destino não localizado.")

    # --- RESULTADOS E MAPA ---
    if st.session_state.resultado:
        res = st.session_state.resultado
        v = res['venc']
        cor = "orange" if v['Ocupacao'] > 80 else "green"

        st.info(f"🏆 Sugestão: **{v['Consultor']}** ({v['Unidade']})")
        c1, c2 = st.columns(2)
        c1.metric("Distância Real", f"{v['Distancia']:.1f} km")
        c2.metric(f"Ocupação ({mes_ref})", f"{v['Ocupacao']:.1f}%")

        m = folium.Map(location=res['dest'], zoom_start=8)
        folium.Marker(res['dest'], tooltip="Cliente", icon=folium.Icon(color='red')).add_to(m)
        if v['Coords']:
            folium.Marker(v['Coords'], tooltip=v['Unidade'], icon=folium.Icon(color=cor, icon='user')).add_to(m)
            if v['Trajeto']:
                folium.PolyLine(v['Trajeto'], color="blue", weight=5, opacity=0.7).add_to(m)
        st_folium(m, width=1200, height=500, key="mapa_final")
else:
    st.info("💡 Carregue o arquivo Excel na lateral para visualizar a tabela completa.")
