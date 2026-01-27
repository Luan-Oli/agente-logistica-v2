import streamlit as st
import pandas as pd
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import folium
from streamlit_folium import st_folium
import requests
import time

# Configuração da Página
st.set_page_config(page_title="Agente Logística V2.3", layout="wide")

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
if 'consultores' not in st.session_state:
    st.session_state.consultores = pd.DataFrame()
if 'resultado' not in st.session_state:
    st.session_state.resultado = None

st.title("🤖 Agente de Logística: Importação de Excel e Rotas Reais")

# --- BARRA LATERAL: IMPORTAÇÃO ---
with st.sidebar:
    st.header("📁 Importar Dados")
    arquivo_excel = st.file_uploader("Selecione o arquivo Excel (.xlsx)", type=["xlsx"])
    
    if arquivo_excel:
        try:
            # Lê o Excel e carrega na memória
            df_excel = pd.read_excel(arquivo_excel)
            # Verifica se as colunas necessárias existem
            colunas_esperadas = ['Consultor', 'Unidade', 'Ocupacao']
            if all(col in df_excel.columns for col in colunas_esperadas):
                st.session_state.consultores = df_excel[colunas_esperadas]
                st.success(f"{len(df_excel)} consultores carregados!")
            else:
                st.error(f"Erro! O Excel precisa das colunas: {colunas_esperadas}")
        except Exception as e:
            st.error(f"Erro ao ler arquivo: {e}")

    if st.button("Limpar Todos os Dados"):
        st.session_state.consultores = pd.DataFrame()
        st.session_state.resultado = None
        st.rerun()

# --- ÁREA DE ANÁLISE ---
if not st.session_state.consultores.empty:
    df = st.session_state.consultores.copy()
    st.subheader("📋 Lista de Consultores Ativa")
    st.dataframe(df, use_container_width=True)

    st.divider()
    st.subheader("📍 Definir Destino do Atendimento")
    destino = st.text_input("Cidade de Destino (Ex: Xangri-la):")

    if st.button("CALCULAR MELHOR LOGÍSTICA", type="primary"):
        # User Agent único para evitar bloqueio 403
        geolocator = Nominatim(user_agent=f"agente_v23_{int(time.time())}", timeout=20)
        loc_dest = geolocator.geocode(f"{destino}, RS, Brasil")

        if loc_dest:
            with st.spinner("Analisando rotas rodoviárias..."):
                def calcular(row):
                    time.sleep(1.2) # Segurança para API de mapas
                    l = geolocator.geocode(f"{row['Unidade']}, RS, Brasil")
                    if l:
                        origem = (l.latitude, l.longitude)
                        dest = (loc_dest.latitude, loc_dest.longitude)
                        caminho, km = buscar_rota_real(origem, dest)
                        # Backup para linha reta se rota real falhar
                        if not km: km = geodesic(origem, dest).km
                        return pd.Series([km, origem, caminho])
                    return pd.Series([9999, None, None])

                df[['Distancia', 'Coords', 'Trajeto']] = df.apply(calcular, axis=1)
                
                # Lógica: Menor Ocupação -> Menor Distância
                venc = df.sort_values(by=['Ocupacao', 'Distancia']).iloc[0]
                st.session_state.resultado = {
                    'vencedor': venc, 
                    'dest_coords': (loc_dest.latitude, loc_dest.longitude)
                }
        else:
            st.error("Cidade não encontrada.")

    # --- MAPA PERSISTENTE (Sem balões) ---
    if st.session_state.resultado:
        res = st.session_state.resultado
        v = res['vencedor']
        
        st.info(f"🏆 Consultor Selecionado: **{v['Consultor']}**")
        c1, c2 = st.columns(2)
        c1.metric("KM Real (Estrada)", f"{v['Distancia']:.1f} km")
        c2.metric("Ocupação Mensal", f"{v['Ocupacao']}%")

        # Gerar Mapa
        m = folium.Map(location=res['dest_coords'], zoom_start=8)
        folium.Marker(res['dest_coords'], tooltip="Destino", icon=folium.Icon(color='red')).add_to(m)
        
        if v['Coords']:
            folium.Marker(v['Coords'], tooltip=v['Unidade'], icon=folium.Icon(color='green')).add_to(m)
            if v['Trajeto']:
                folium.PolyLine(v['Trajeto'], color="blue", weight=5, opacity=0.8).add_to(m)
            else:
                folium.PolyLine([res['dest_coords'], v['Coords']], color="gray", dash_array='5').add_to(m)

        st_folium(m, width=1200, height=500, key="mapa_estratificado")
else:
    st.info("💡 Arraste seu arquivo Excel para a barra lateral para começar.")
