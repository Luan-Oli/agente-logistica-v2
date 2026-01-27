import streamlit as st
import pandas as pd
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import folium
from streamlit_folium import st_folium
import requests
import time

# Configuração da Página
st.set_page_config(page_title="Agente de Logística V2.1", layout="wide")

# --- FUNÇÃO DE ROTA REAL (OSRM) ---
def buscar_rota_real(ponto_a, ponto_b):
    """Retorna o caminho pelas estradas e a distância real em KM"""
    # OSRM usa [Longitude, Latitude]
    url = f"http://router.project-osrm.org/route/v1/driving/{ponto_a[1]},{ponto_a[0]};{ponto_b[1]},{ponto_b[0]}?overview=full&geometries=geojson"
    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        if data['code'] == 'Ok':
            # Inverte para [Lat, Lon] para o Folium
            rota = [[p[1], p[0]] for p in data['routes'][0]['geometry']['coordinates']]
            distancia = data['routes'][0]['distance'] / 1000
            return rota, distancia
    except:
        return None, None

# --- INICIALIZAÇÃO DE MEMÓRIA (Session State) ---
# Garante que os dados e o mapa não sumam após cliques
if 'consultores' not in st.session_state:
    st.session_state.consultores = []
if 'resultado' not in st.session_state:
    st.session_state.resultado = None

st.title("🤖 Agente de Logística: Rotas Reais e Ocupação")

# --- BARRA LATERAL ---
with st.sidebar:
    st.header("👥 Gestão de Consultores")
    with st.form("add_consultor"):
        nome = st.text_input("Nome")
        unidade = st.text_input("Cidade da Unidade (Ex: Bento Gonçalves)")
        ocupacao = st.slider("Ocupação Atual (%)", 0, 100, 20)
        if st.form_submit_button("Adicionar"):
            st.session_state.consultores.append({"Consultor": nome, "Unidade": unidade, "Ocupacao": ocupacao})
            st.rerun()

    if st.button("Limpar Tudo"):
        st.session_state.consultores = []
        st.session_state.resultado = None
        st.rerun()

# --- ÁREA PRINCIPAL ---
if st.session_state.consultores:
    df = pd.DataFrame(st.session_state.consultores)
    st.subheader("📋 Consultores na Base")
    st.dataframe(df, use_container_width=True)

    st.divider()
    st.subheader("📍 Novo Atendimento")
    destino = st.text_input("Cidade de Destino (Ex: Xangri-la):")

    if st.button("CALCULAR MELHOR LOGÍSTICA", type="primary"):
        # Evita Erro 403 Forbidden
        geolocator = Nominatim(user_agent=f"agente_luan_{int(time.time())}", timeout=20)
        loc_dest = geolocator.geocode(f"{destino}, RS, Brasil")

        if loc_dest:
            with st.spinner("Traçando rotas reais pelas rodovias..."):
                def analisar(row):
                    time.sleep(1.2) # Segurança do Geopy
                    l = geolocator.geocode(f"{row['Unidade']}, RS, Brasil")
                    if l:
                        coords_unidade = (l.latitude, l.longitude)
                        coords_destino = (loc_dest.latitude, loc_dest.longitude)
                        
                        # Busca a estrada real
                        caminho, km = buscar_rota_real(coords_unidade, coords_destino)
                        
                        # Se falhar a rota real, usa a linear como backup
                        if not km:
                            km = geodesic(coords_unidade, coords_destino).km
                        
                        return pd.Series([km, coords_unidade, caminho])
                    return pd.Series([9999, None, None])

                df[['Distancia', 'Coords', 'Trajeto']] = df.apply(analisar, axis=1)
                
                # LÓGICA: Prioriza Menor Ocupação e depois Distância
                venc = df.sort_values(by=['Ocupacao', 'Distancia']).iloc[0]
                
                st.session_state.resultado = {
                    'vencedor': venc,
                    'dest_coords': (loc_dest.latitude, loc_dest.longitude)
                }
        else:
            st.error("Cidade não encontrada.")

    # --- EXIBIÇÃO DO MAPA (PERSISTENTE) ---
    if st.session_state.resultado:
        res = st.session_state.resultado
        v = res['vencedor']
        
        st.success(f"🏆 Sugestão: **{v['Consultor']}**")
        col1, col2 = st.columns(2)
        col1.metric("Distância (Estrada)", f"{v['Distancia']:.1f} km")
        col2.metric("Ocupação", f"{v['Ocupacao']}%")

        # Criar Mapa Folium
        m = folium.Map(location=res['dest_coords'], zoom_start=8)
        
        # Marcador Destino
        folium.Marker(res['dest_coords'], tooltip="Cliente", icon=folium.Icon(color='red')).add_to(m)
        
        # Marcador Unidade e Rota
        if v['Coords']:
            folium.Marker(v['Coords'], tooltip=v['Unidade'], icon=folium.Icon(color='green')).add_to(m)
            
            # Se houver trajeto real, desenha a curva da estrada. Se não, linha reta.
            if v['Trajeto']:
                folium.PolyLine(v['Trajeto'], color="blue", weight=5, opacity=0.8).add_to(m)
            else:
                folium.PolyLine([res['dest_coords'], v['Coords']], color="gray", dash_array='5').add_to(m)

        # st_folium com KEY fixa impede o mapa de sumir
        st_folium(m, width=1200, height=500, key="mapa_v2")
        st.balloons()
else:
    st.info("Cadastre consultores na lateral para iniciar.")
