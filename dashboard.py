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
if 'consultores' not in st.session_state:
    st.session_state.consultores = pd.DataFrame()
if 'resultado' not in st.session_state:
    st.session_state.resultado = None

st.title("🤖 Agente de Logística: Inteligência Mensal V2.6")

# --- BARRA LATERAL: IMPORTAÇÃO ---
with st.sidebar:
    st.header("📁 Gestão de Dados")
    # Certifica-te de arrastar o ficheiro .xlsx real, não o atalho .url
    arquivo_excel = st.file_uploader("Carregar Excel (.xlsx)", type=["xlsx"])
    
    if arquivo_excel:
        try:
            df_temp = pd.read_excel(arquivo_excel)
            
            # Identifica o mês atual em Português
            meses_pt = {1: 'Janeiro', 2: 'Fevereiro', 3: 'Março', 4: 'Abril', 5: 'Maio', 6: 'Junho', 
                        7: 'Julho', 8: 'Agosto', 9: 'Setembro', 10: 'Outubro', 11: 'Novembro', 12: 'Dezembro'}
            mes_atual = meses_pt[datetime.now().month]
            
            # Valida as colunas base
            if 'Consultor' in df_temp.columns and 'Unidade' in df_temp.columns:
                # Verifica se a coluna do mês atual existe
                if mes_atual in df_temp.columns:
                    # Limpeza de dados: remove % e troca vírgula por ponto
                    df_temp['Ocupacao'] = df_temp[mes_atual].astype(str).str.replace('%', '').str.replace(',', '.').astype(float)
                else:
                    st.warning(f"Coluna '{mes_atual}' não encontrada. Usando 0% por padrão.")
                    df_temp['Ocupacao'] = 0.0
                
                st.session_state.consultores = df_temp[['Consultor', 'Unidade', 'Ocupacao']]
                st.success(f"Dados de {mes_atual} carregados com sucesso!")
            else:
                st.error("Erro: O Excel deve conter as colunas 'Consultor' e 'Unidade'.")
        except Exception as e:
            st.error(f"Erro ao processar: {e}")

    if st.button("Limpar Tudo"):
        st.session_state.consultores = pd.DataFrame()
        st.session_state.resultado = None
        st.rerun()

# --- ÁREA DE CÁLCULO ---
if not st.session_state.consultores.empty:
    df = st.session_state.consultores.copy()
    st.subheader(f"📋 Lista de Consultores (Ocupação de {mes_atual})")
    st.dataframe(df, use_container_width=True)

    st.divider()
    destino = st.text_input("📍 Cidade de Destino do Atendimento:")

    if st.button("CALCULAR MELHOR LOGÍSTICA", type="primary"):
        geolocator = Nominatim(user_agent=f"agente_v26_{int(time.time())}", timeout=20)
        loc_dest = geolocator.geocode(f"{destino}, RS, Brasil")

        if loc_dest:
            with st.spinner("Buscando rota real pelas estradas..."):
                def analisar(row):
                    time.sleep(1.2) # Segurança contra bloqueio
                    l = geolocator.geocode(f"{row['Unidade']}, RS, Brasil")
                    if l:
                        origem = (l.latitude, l.longitude)
                        dest_c = (loc_dest.latitude, loc_dest.longitude)
                        cam, km = buscar_rota_real(origem, dest_c)
                        if not km: km = geodesic(origem, dest_c).km
                        return pd.Series([km, origem, cam])
                    return pd.Series([9999, None, None])

                df[['Distancia', 'Coords', 'Trajeto']] = df.apply(analisar, axis=1)
                
                # Seleciona o melhor (menor ocupação e depois menor distância)
                venc = df.sort_values(by=['Ocupacao', 'Distancia']).iloc[0]
                st.session_state.resultado = {'vencedor': venc, 'dest_coords': (loc_dest.latitude, loc_dest.longitude)}
        else:
            st.error("Não foi possível localizar o destino.")

    # --- MAPA PERSISTENTE ---
    if st.session_state.resultado:
        res = st.session_state.resultado
        v = res['vencedor']
        
        # Alerta Laranja para ocupação > 80%
        cor_pino = "orange" if v['Ocupacao'] > 80 else "green"
        
        st.info(f"🏆 Sugestão: **{v['Consultor']}** ({v['Ocupacao']:.1f}% de ocupação)")
        c1, c2 = st.columns(2)
        c1.metric("Distância por Estrada", f"{v['Distancia']:.1f} km")
        c2.metric("Ocupação", f"{v['Ocupacao']:.1f}%")

        m = folium.Map(location=res['dest_coords'], zoom_start=8)
        folium.Marker(res['dest_coords'], tooltip="Destino", icon=folium.Icon(color='red')).add_to(m)
        
        if v['Coords']:
            folium.Marker(v['Coords'], tooltip=v['Unidade'], icon=folium.Icon(color=cor_pino, icon='user')).add_to(m)
            if v['Trajeto']:
                folium.PolyLine(v['Trajeto'], color="blue", weight=5, opacity=0.7).add_to(m)

        st_folium(m, width=1200, height=500, key="mapa_v26")
else:
    st.info("💡 Carrega o ficheiro Excel (.xlsx) na barra lateral para começar.")
