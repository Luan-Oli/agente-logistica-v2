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
st.set_page_config(page_title="Agente Logística V2.6", layout="wide")

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

st.title("🤖 Agente de Logística: Inteligência Mensal V2.6")

# --- BARRA LATERAL: IMPORTAÇÃO ---
with st.sidebar:
    st.header("📁 Gestão de Dados")
    arquivo_excel = st.file_uploader("Carregar Excel (.xlsx)", type=["xlsx"])
    
    if arquivo_excel:
        try:
            df_temp = pd.read_excel(arquivo_excel)
            # Mapeamento automático do mês atual
            meses_pt = {1: 'Janeiro', 2: 'Fevereiro', 3: 'Março', 4: 'Abril', 5: 'Maio', 6: 'Junho', 
                        7: 'Julho', 8: 'Agosto', 9: 'Setembro', 10: 'Outubro', 11: 'Novembro', 12: 'Dezembro'}
            mes_atual = meses_pt[datetime.now().month]
            
            if 'Consultor' in df_temp.columns and 'Unidade' in df_temp.columns:
                # Se a coluna do mês existir, usamos ela como 'Ocupacao'
                if mes_atual in df_temp.columns:
                    df_temp['Ocupacao'] = df_temp[mes_atual]
                    # Converte percentagem (ex: 52,38%) para número se necessário
                    if df_temp['Ocupacao'].dtype == object:
                        df_temp['Ocupacao'] = df_temp['Ocupacao'].str.replace('%','').str.replace(',','.').astype(float)
                else:
                    st.warning(f"Coluna '{mes_atual}' não encontrada. Usando 0% por defeito.")
                    df_temp['Ocupacao'] = 0
                
                st.session_state.consultores = df_temp[['Consultor', 'Unidade', 'Ocupacao']]
                st.success(f"Dados de {mes_atual} carregados!")
            else:
                st.error("O Excel deve conter as colunas 'Consultor' e 'Unidade'.")
        except Exception as e:
            st.error(f"Erro ao ler ficheiro: {e}")

    if st.button("Limpar Tudo"):
        st.session_state.consultores = pd.DataFrame()
        st.session_state.resultado = None
        st.rerun()

# --- ÁREA DE CÁLCULO ---
if not st.session_state.consultores.empty:
    df = st.session_state.consultores.copy()
    st.subheader("📋 Ocupação da Equipa (Mês Atual)")
    st.dataframe(df, use_container_width=True)

    st.divider()
    destino = st.text_input("📍 Cidade de Destino (Ex: Caxias do Sul):")

    if st.button("CALCULAR MELHOR LOGÍSTICA", type="primary"):
        geolocator = Nominatim(user_agent=f"agente_v26_{int(time.time())}", timeout=20)
        loc_dest = geolocator.geocode(f"{destino}, RS, Brasil")

        if loc_dest:
            with st.spinner("A traçar rotas reais..."):
                def calcular(row):
                    time.sleep(1.2) # Segurança API
                    l = geolocator.geocode(f"{row['Unidade']}, RS, Brasil")
                    if l:
                        origem, dest_coords = (l.latitude, l.longitude), (loc_dest.latitude, loc_dest.longitude)
                        caminho, km = buscar_rota_real(origem, dest_coords)
                        if not km: km = geodesic(origem, dest_coords).km
                        return pd.Series([km, origem, caminho])
                    return pd.Series([9999, None, None])

                df[['Distancia', 'Coords', 'Trajeto']] = df.apply(calcular, axis=1)
                # Lógica: Menor Ocupação -> Menor Distância
                venc = df.sort_values(by=['Ocupacao', 'Distancia']).iloc[0]
                st.session_state.resultado = {'vencedor': venc, 'dest_coords': (loc_dest.latitude, loc_dest.longitude)}
        else:
            st.error("Destino não localizado.")

    # --- MAPA COM ALERTA DE OCUPAÇÃO (>80%) ---
    if st.session_state.resultado:
        res = st.session_state.resultado
        v = res['vencedor']
        
        # Alerta Laranja para ocupação alta
        cor_pino = "orange" if v['Ocupacao'] > 80 else "green"
        aviso = "⚠️ OCUPAÇÃO ALTA" if v['Ocupacao'] > 80 else "✅ DISPONÍVEL"

        st.info(f"🏆 Sugestão: **{v['Consultor']}** | {aviso}")
        c1, c2 = st.columns(2)
        c1.metric("Distância Real", f"{v['Distancia']:.1f} km")
        c2.metric("Ocupação", f"{v['Ocupacao']:.1f}%")

        m = folium.Map(location=res['dest_coords'], zoom_start=8)
        folium.Marker(res['dest_coords'], tooltip="Destino", icon=folium.Icon(color='red')).add_to(m)
        
        if v['Coords']:
            folium.Marker(
                v['Coords'], 
                tooltip=f"{v['Consultor']} ({v['Ocupacao']}%)", 
                icon=folium.Icon(color=cor_pino, icon='user')
            ).add_to(m)
            if v['Trajeto']:
                folium.PolyLine(v['Trajeto'], color="blue", weight=5, opacity=0.7).add_to(m)

        st_folium(m, width=1200, height=500, key="mapa_final_v26")
else:
    st.info("💡 Arraste o seu ficheiro Excel (.xlsx) para a barra lateral para começar.")
