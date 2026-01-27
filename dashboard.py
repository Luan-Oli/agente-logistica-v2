import streamlit as st
import pandas as pd
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import folium
from streamlit_folium import st_folium
import time

# Configuração da página para ocupar a tela inteira
st.set_page_config(page_title="Agente Logística V2", layout="wide")

# --- MEMÓRIA DO SITE (Session State) ---
# Isso impede que o mapa suma após o clique
if 'lista_consultores' not in st.session_state:
    st.session_state.lista_consultores = []
if 'resultado_vencedor' not in st.session_state:
    st.session_state.resultado_vencedor = None
if 'mapa_data' not in st.session_state:
    st.session_state.mapa_data = None

st.title("🤖 Agente de Logística: Painel de Atendimento")

# --- BARRA LATERAL: CADASTRO ---
with st.sidebar:
    st.header("👥 Gestão de Equipe")
    with st.form("cadastro_consultor"):
        nome = st.text_input("Nome do Consultor")
        unidade = st.text_input("Cidade da Unidade (Ex: Bento Gonçalves)")
        ocupacao = st.slider("Ocupação Atual (%)", 0, 100, 20)
        btn_add = st.form_submit_button("Adicionar Consultor")

    if btn_add and nome and unidade:
        st.session_state.lista_consultores.append({
            "Consultor": nome, "Unidade": unidade, "Ocupação": ocupacao
        })
        st.success(f"{nome} adicionado!")

    if st.button("Limpar Lista de Consultores"):
        st.session_state.lista_consultores = []
        st.session_state.resultado_vencedor = None
        st.session_state.mapa_data = None
        st.rerun()

# --- ÁREA DE CÁLCULO ---
if st.session_state.lista_consultores:
    df = pd.DataFrame(st.session_state.lista_consultores)
    st.subheader("📋 Consultores Disponíveis")
    st.dataframe(df, use_container_width=True)

    st.divider()
    st.subheader("📍 Novo Atendimento")
    cidade_destino = st.text_input("Informe a Cidade de Destino (Ex: Xangri-la):")

    if st.button("CALCULAR MELHOR ROTA", type="primary"):
        # Evita o erro 403 Forbidden usando um nome único
        user_agent_unico = f"agente_logistica_luan_{int(time.time())}"
        geolocator = Nominatim(user_agent=user_agent_unico, timeout=20)
        
        loc_dest = geolocator.geocode(f"{cidade_destino}, RS, Brasil")

        if loc_dest:
            with st.spinner("Analisando logística..."):
                def processar(row):
                    time.sleep(1.2) # Pausa de segurança para o serviço de mapas
                    l = geolocator.geocode(f"{row['Unidade']}, RS, Brasil")
                    if l:
                        dist = geodesic((loc_dest.latitude, loc_dest.longitude), (l.latitude, l.longitude)).km
                        return dist, (l.latitude, l.longitude)
                    return 9999, None

                res = df.apply(processar, axis=1)
                df['Distancia'] = [r[0] for r in res]
                df['Coords'] = [r[1] for r in res]

                # LÓGICA: Menor Ocupação -> Menor Distância
                vencedor = df.sort_values(by=['Ocupação', 'Distancia']).iloc[0]
                
                # Salvando na memória para o mapa não sumir
                st.session_state.resultado_vencedor = vencedor
                st.session_state.mapa_data = {
                    'dest_lat': loc_dest.latitude,
                    'dest_lon': loc_dest.longitude,
                    'venc_coords': vencedor['Coords']
                }
        else:
            st.error("Cidade de destino não encontrada.")

    # --- EXIBIÇÃO PERSISTENTE DO MAPA ---
    # Esta parte fica fora do botão para o mapa não sumir
    if st.session_state.resultado_vencedor is not None:
        v = st.session_state.resultado_vencedor
        d = st.session_state.mapa_data

        st.success(f"🏆 Melhor Opção: **{v['Consultor']}**")
        c1, c2 = st.columns(2)
        c1.metric("Distância", f"{v['Distancia']:.1f} km")
        c2.metric("Ocupação", f"{v['Ocupação']}%")

        # Renderização do Mapa Folium
        m = folium.Map(location=[d['dest_lat'], d['dest_lon']], zoom_start=8)
        
        # Marcador Destino
        folium.Marker([d['dest_lat'], d['dest_lon']], tooltip="Destino", icon=folium.Icon(color='red')).add_to(m)
        
        # Marcador Unidade e Trajeto
        if d['venc_coords']:
            folium.Marker(d['venc_coords'], tooltip=v['Unidade'], icon=folium.Icon(color='green')).add_to(m)
            folium.PolyLine(
                locations=[[d['dest_lat'], d['dest_lon']], d['venc_coords']], 
                color="blue", weight=4, opacity=0.7
            ).add_to(m)

        # O segredo: st_folium com uma KEY fixa
        st_folium(m, width=1200, height=500, key="mapa_persistente")
        st.balloons()
else:
    st.info("💡 Adicione os consultores na barra lateral para começar.")
