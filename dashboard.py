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
st.set_page_config(page_title="Agente Logística V2.8", layout="wide")

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

st.title("🤖 Agente de Logística: Planejamento V2.8")

# --- BARRA LATERAL: GESTÃO ---
with st.sidebar:
    st.header("📁 Gestão de Dados")
    # Lembre-se: Arraste o arquivo .xlsx real, não o atalho .url
    arquivo_excel = st.file_uploader("Carregar Excel (.xlsx)", type=["xlsx"])
    
    if arquivo_excel:
        try:
            st.session_state.consultores_base = pd.read_excel(arquivo_excel)
            st.success("Excel carregado!")
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

# --- PROCESSAMENTO DOS DADOS ---
if not st.session_state.consultores_base.empty:
    df_temp = st.session_state.consultores_base.copy()
    
    # Ajuste dinâmico para os dados do seu Excel
    if mes_selecionado in df_temp.columns:
        # Converte "52,38%" (string) para 52.38 (número)
        df_temp['Ocupacao'] = df_temp[mes_selecionado].astype(str).str.replace('%', '').str.replace(',', '.').astype(float)
    else:
        st.warning(f"Coluna {mes_selecionado} não encontrada.")
        df_temp['Ocupacao'] = 0.0

    # FIX LINHA 98: Sintaxe corrigida para evitar o erro da imagem
    st.subheader(f"📋 Consultores Disponíveis - {mes_selecionado}")
    st.dataframe(df_temp[['Consultor', 'Unidade', 'Ocupacao']], use_container_width=True)

    st.divider()
    destino = st.text_input("📍 Informe a Cidade de Destino:")

    if st.button("CALCULAR LOGÍSTICA", type="primary"):
        geolocator = Nominatim(user_agent=f"agente_v28_{int(time.time())}", timeout=20)
        loc_dest = geolocator.geocode(f"{destino}, RS, Brasil")

        if loc_dest:
            with st.spinner("Traçando rotas reais..."):
                def analisar(row):
                    time.sleep(1.2) # Evita erro 403
                    l = geolocator.geocode(f"{row['Unidade']}, RS, Brasil")
                    if l:
                        origem = (l.latitude, l.longitude)
                        cam, km = buscar_rota_real(origem, (loc_dest.latitude, loc_dest.longitude))
                        if not km: km = geodesic(origem, (loc_dest.latitude, loc_dest.longitude)).km
                        return pd.Series([km, origem, cam])
                    return pd.Series([9999, None, None])

                df_temp[['Distancia', 'Coords', 'Trajeto']] = df_temp.apply(analisar, axis=1)
                venc = df_temp.sort_values(by=['Ocupacao', 'Distancia']).iloc[0]
                st.session_state.resultado = {'vencedor': venc, 'dest_coords': (loc_dest.latitude, loc_dest.longitude)}
        else:
            st.error("Cidade não encontrada.")

    # --- MAPA FINAL ---
    if st.session_state.resultado:
        res = st.session_state.resultado
        v = res['vencedor']
        cor = "orange" if v['Ocupacao'] > 80 else "green"

        st.info(f"🏆 Melhor Sugestão: **{v['Consultor']}**")
        c1, c2 = st.columns(2)
        c1.metric("Distância Estrada", f"{v['Distancia']:.1f} km")
        c2.metric(f"Ocupação ({mes_selecionado})", f"{v['Ocupacao']:.1f}%")

        m = folium.Map(location=res['dest_coords'], zoom_start=8)
        folium.Marker(res['dest_coords'], tooltip="Destino", icon=folium.Icon(color='red')).add_to(m)
        if v['Coords']:
            folium.Marker(v['Coords'], tooltip=v['Consultor'], icon=folium.Icon(color=cor, icon='user')).add_to(m)
            if v['Trajeto']:
                folium.PolyLine(v['Trajeto'], color="blue", weight=5, opacity=0.7).add_to(m)

        st_folium(m, width=1200, height=500, key="mapa_v28")
else:
    st.info("💡 Arraste o seu arquivo Excel para começar.")
