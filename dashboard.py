import streamlit as st
import pandas as pd
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import folium
from streamlit_folium import st_folium
import requests
import time
import io

# Configuração da Página
st.set_page_config(page_title="Agente de Logística V2.2", layout="wide")

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
    st.session_state.consultores = []
if 'resultado' not in st.session_state:
    st.session_state.resultado = None

st.title("🤖 Agente de Logística: Painel de Controle V2.2")

# --- BARRA LATERAL: GESTÃO DE EQUIPE ---
with st.sidebar:
    st.header("👥 Inserção de Consultores")
    
    # OPÇÃO 1: Cadastro Individual
    with st.expander("➕ Adicionar Um por Um"):
        with st.form("add_individual"):
            nome = st.text_input("Nome do Consultor")
            unidade = st.text_input("Cidade da Unidade")
            ocupacao = st.slider("Ocupação Atual (%)", 0, 100, 20)
            if st.form_submit_button("Confirmar"):
                st.session_state.consultores.append({"Consultor": nome, "Unidade": unidade, "Ocupacao": ocupacao})
                st.rerun()

    # OPÇÃO 2: Inserção em Lote (Múltiplos Consultores)
    with st.expander("📂 Inserir em Lote (Excel/Texto)"):
        st.markdown("**Formato:** `Nome;Cidade;Ocupação` (um por linha)")
        dados_lote = st.text_area("Cole aqui os dados:", height=150, placeholder="Exemplo:\nFabio Vargas;Bento Gonçalves;20\nFernanda Machado;Caxias do Sul;50")
        if st.button("Processar Dados"):
            if dados_lote:
                try:
                    # Lê o texto colado usando ponto e vírgula como separador
                    df_lote = pd.read_csv(io.StringIO(dados_lote), sep=';', names=['Consultor', 'Unidade', 'Ocupacao'], header=None)
                    novos_consultores = df_lote.to_dict('records')
                    st.session_state.consultores.extend(novos_consultores)
                    st.success(f"Sucesso! {len(novos_consultores)} consultores adicionados.")
                    st.rerun()
                except Exception as e:
                    st.error("Erro no formato! Use ponto e vírgula (;) para separar os campos.")

    if st.button("Limpar Lista Completa"):
        st.session_state.consultores = []
        st.session_state.resultado = None
        st.rerun()

# --- ÁREA DE ANÁLISE ---
if st.session_state.consultores:
    df = pd.DataFrame(st.session_state.consultores)
    st.subheader("📋 Consultores Cadastrados")
    st.dataframe(df, use_container_width=True)

    st.divider()
    st.subheader("📍 Solicitação de Atendimento")
    destino = st.text_input("Informe a Cidade de Destino (Ex: Xangri-la):")

    if st.button("CALCULAR MELHOR LOGÍSTICA", type="primary"):
        geolocator = Nominatim(user_agent=f"agente_v22_{int(time.time())}", timeout=20)
        loc_dest = geolocator.geocode(f"{destino}, RS, Brasil")

        if loc_dest:
            with st.spinner("Analisando estradas e disponibilidade..."):
                def calcular_logistica(row):
                    time.sleep(1.2) # Segurança do Geopy
                    l = geolocator.geocode(f"{row['Unidade']}, RS, Brasil")
                    if l:
                        origem = (l.latitude, l.longitude)
                        dest = (loc_dest.latitude, loc_dest.longitude)
                        caminho, km = buscar_rota_real(origem, dest)
                        if not km: km = geodesic(origem, dest).km
                        return pd.Series([km, origem, caminho])
                    return pd.Series([9999, None, None])

                df[['Distancia', 'Coords', 'Trajeto']] = df.apply(calcular_logistica, axis=1)
                
                # Regra: Menor Ocupação -> Menor Distância
                venc = df.sort_values(by=['Ocupacao', 'Distancia']).iloc[0]
                st.session_state.resultado = {'vencedor': venc, 'dest_coords': (loc_dest.latitude, loc_dest.longitude)}
        else:
            st.error("Cidade de destino não encontrada.")

    # EXIBIÇÃO DO MAPA PERSISTENTE
    if st.session_state.resultado:
        res = st.session_state.resultado
        v = res['vencedor']
        
        st.success(f"🏆 Melhor Escolha: **{v['Consultor']}**")
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

        st_folium(m, width=1200, height=500, key="mapa_estavel")
else:
    st.info("Utilize a barra lateral para inserir os consultores disponíveis.")
