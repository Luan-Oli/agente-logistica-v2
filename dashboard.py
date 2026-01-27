import streamlit as st
import pandas as pd
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import folium
from streamlit_folium import st_folium
import time

st.set_page_config(page_title="Agente Logística Manual", layout="wide")

# --- ESTILIZAÇÃO E TÍTULO ---
st.title("🤖 Agente de Logística: Painel de Atendimento")
st.markdown("Insira os dados dos consultores e o destino para visualizar a melhor rota.")

# --- BARRA LATERAL (CADASTRO MANUAL) ---
with st.sidebar:
    st.header("👥 Cadastro de Consultores")
    with st.form("novo_consultor"):
        nome = st.text_input("Nome do Consultor")
        unidade = st.text_input("Unidade/Cidade (Ex: Bento Gonçalves)")
        ocupacao = st.slider("Ocupação Mensal (%)", 0, 100, 30)
        btn_add = st.form_submit_button("Adicionar Consultor")

# Inicialização da lista na memória da sessão
if 'consultores' not in st.session_state:
    st.session_state.consultores = []

if btn_add and nome and unidade:
    st.session_state.consultores.append({"Consultor": nome, "Unidade": unidade, "Ocupação": ocupacao})

# --- EXIBIÇÃO E CÁLCULO ---
if st.session_state.consultores:
    df = pd.DataFrame(st.session_state.consultores)
    st.subheader("📋 Consultores Disponíveis")
    st.dataframe(df, use_container_width=True)

    if st.button("Limpar Lista"):
        st.session_state.consultores = []
        st.rerun()

    st.divider()

    # --- INPUT DE DESTINO ---
    col1, col2 = st.columns([2, 1])
    with col1:
        destino = st.text_input("📍 Informe a Cidade do Cliente (Destino):")
    
    if st.button("CALCULAR MELHOR LOGÍSTICA", type="primary"):
        geolocator = Nominatim(user_agent=f"agente_luan_manual_{int(time.time())}", timeout=20)
        loc_dest = geolocator.geocode(f"{destino}, RS, Brasil")

        if loc_dest:
            with st.spinner("Gerando trajeto no mapa..."):
                def processar_distancia(row):
                    time.sleep(1.2) # Evita bloqueio 403
                    l = geolocator.geocode(f"{row['Unidade']}, RS, Brasil")
                    return geodesic((loc_dest.latitude, loc_dest.longitude), (l.latitude, l.longitude)).km if l else 9999, (l.latitude, l.longitude) if l else None

                results = df.apply(processar_distancia, axis=1)
                df['Distancia'] = [r[0] for r in results]
                df['Coords'] = [r[1] for r in results]

                # Lógica: Menor Ocupação -> Menor Distância
                vencedor = df.sort_values(by=['Ocupação', 'Distancia']).iloc[0]

                st.success(f"🏆 Sugestão: **{vencedor['Consultor']}** percorrendo {vencedor['Distancia']:.1f} km.")

                # --- MAPA INTERATIVO ---
                m = folium.Map(location=[loc_dest.latitude, loc_dest.longitude], zoom_start=8)
                
                # Marcador Destino (Vermelho)
                folium.Marker([loc_dest.latitude, loc_dest.longitude], tooltip="Cliente", icon=folium.Icon(color='red')).add_to(m)
                
                # Marcador Consultor (Verde)
                if vencedor['Coords']:
                    folium.Marker(vencedor['Coords'], tooltip=f"Unidade: {vencedor['Unidade']}", icon=folium.Icon(color='green')).add_to(m)
                    
                    # Linha do Trajeto
                    folium.PolyLine(locations=[[loc_dest.latitude, loc_dest.longitude], vencedor['Coords']], color="blue", weight=4, opacity=0.7).add_to(m)

                st_folium(m, width=1200, height=500)
        else:
            st.error("Não foi possível localizar essa cidade de destino.")
else:
    st.info("Utilize a barra lateral para inserir os consultores disponíveis no momento.")
