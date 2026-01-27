import streamlit as st
import pandas as pd
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import folium
from streamlit_folium import st_folium
import requests
import time

# Configuração da Página
st.set_page_config(page_title="Agente Logística V2.4", layout="wide")

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

st.title("🤖 Agente de Logística: Filtros e Rotas Reais")

# --- BARRA LATERAL: IMPORTAÇÃO E FILTROS ---
with st.sidebar:
    st.header("📁 Gestão de Dados")
    arquivo_excel = st.file_uploader("Upload do Excel (.xlsx)", type=["xlsx"])
    
    if arquivo_excel:
        try:
            df_excel = pd.read_excel(arquivo_excel)
            colunas_esperadas = ['Consultor', 'Unidade', 'Ocupacao']
            if all(col in df_excel.columns for col in colunas_esperadas):
                st.session_state.consultores = df_excel[colunas_esperadas]
            else:
                st.error(f"O Excel deve ter: {colunas_esperadas}")
        except Exception as e:
            st.error(f"Erro ao ler: {e}")

    # --- NOVO: FILTRO POR UNIDADE ---
    unidades_selecionadas = []
    if not st.session_state.consultores.empty:
        st.divider()
        st.header("🔍 Filtrar Atendimento")
        todas_unidades = sorted(st.session_state.consultores['Unidade'].unique())
        unidades_selecionadas = st.multiselect(
            "Selecionar Unidades para o Cálculo:",
            options=todas_unidades,
            default=todas_unidades,
            help="Apenas consultores destas cidades serão considerados."
        )

    if st.button("Limpar Tudo"):
        st.session_state.consultores = pd.DataFrame()
        st.session_state.resultado = None
        st.rerun()

# --- ÁREA DE ANÁLISE ---
if not st.session_state.consultores.empty:
    # Filtra a base com base na seleção da barra lateral
    df_filtrado = st.session_state.consultores[st.session_state.consultores['Unidade'].isin(unidades_selecionadas)]
    
    st.subheader(f"📋 Consultores Disponíveis ({len(df_filtrado)})")
    st.dataframe(df_filtrado, use_container_width=True)

    st.divider()
    st.subheader("📍 Definir Destino")
    destino = st.text_input("Cidade de Destino (Ex: Xangri-la):")

    if st.button("CALCULAR MELHOR LOGÍSTICA", type="primary"):
        if df_filtrado.empty:
            st.warning("Nenhum consultor selecionado no filtro lateral.")
        else:
            geolocator = Nominatim(user_agent=f"agente_v24_{int(time.time())}", timeout=20)
            loc_dest = geolocator.geocode(f"{destino}, RS, Brasil")

            if loc_dest:
                with st.spinner("Analisando rotas reais..."):
                    def calcular(row):
                        time.sleep(1.2) #
                        l = geolocator.geocode(f"{row['Unidade']}, RS, Brasil")
                        if l:
                            origem, dest = (l.latitude, l.longitude), (loc_dest.latitude, loc_dest.longitude)
                            caminho, km = buscar_rota_real(origem, dest)
                            if not km: km = geodesic(origem, dest).km
                            return pd.Series([km, origem, caminho])
                        return pd.Series([9999, None, None])

                    # Trabalha apenas com os dados filtrados
                    df_calc = df_filtrado.copy()
                    df_calc[['Distancia', 'Coords', 'Trajeto']] = df_calc.apply(calcular, axis=1)
                    
                    venc = df_calc.sort_values(by=['Ocupacao', 'Distancia']).iloc[0]
                    st.session_state.resultado = {'vencedor': venc, 'dest_coords': (loc_dest.latitude, loc_dest.longitude)}
            else:
                st.error("Cidade de destino não encontrada.")

    # --- MAPA PERSISTENTE ---
    if st.session_state.resultado:
        res = st.session_state.resultado
        v = res['vencedor']
        
        st.info(f"🏆 Consultor Selecionado: **{v['Consultor']}**")
        c1, c2 = st.columns(2)
        c1.metric("Distância (Estrada)", f"{v['Distancia']:.1f} km")
        c2.metric("Ocupação Mensal", f"{v['Ocupacao']}%")

        m = folium.Map(location=res['dest_coords'], zoom_start=8)
        folium.Marker(res['dest_coords'], tooltip="Destino", icon=folium.Icon(color='red')).add_to(m)
        
        if v['Coords']:
            folium.Marker(v['Coords'], tooltip=v['Unidade'], icon=folium.Icon(color='green')).add_to(m)
            if v['Trajeto']:
                folium.PolyLine(v['Trajeto'], color="blue", weight=5, opacity=0.8).add_to(m)

        st_folium(m, width=1200, height=500, key="mapa_v24")
else:
    st.info("💡 Carrega o teu Excel na barra lateral para começar.")
