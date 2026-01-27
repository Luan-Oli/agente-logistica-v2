import streamlit as st
import pandas as pd
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import folium
from streamlit_folium import st_folium
import time

# Configuração da página para ocupar a tela inteira
st.set_page_config(page_title="Agente de Logística V2", layout="wide")

st.title("🤖 Agente de Logística: Gestão Manual e Trajetos")
st.markdown("Cadastre os consultores e defina o destino para encontrar a melhor opção logística.")

# --- BARRA LATERAL: CADASTRO ---
with st.sidebar:
    st.header("👥 Gestão de Equipe")
    with st.form("cadastro_consultor"):
        nome = st.text_input("Nome do Consultor")
        unidade = st.text_input("Cidade da Unidade (Ex: Bento Gonçalves)")
        ocupacao = st.slider("Ocupação Atual (%)", 0, 100, 20)
        btn_add = st.form_submit_button("Adicionar Consultor")

# Inicializa a lista na memória da sessão do navegador
if 'lista_consultores' not in st.session_state:
    st.session_state.lista_consultores = []

if btn_add and nome and unidade:
    st.session_state.lista_consultores.append({
        "Consultor": nome, 
        "Unidade": unidade, 
        "Ocupação": ocupacao
    })
    st.success(f"{nome} adicionado!")

# --- VISUALIZAÇÃO E CÁLCULOS ---
if st.session_state.lista_consultores:
    df = pd.DataFrame(st.session_state.lista_consultores)
    
    col_tab, col_btn = st.columns([4, 1])
    with col_tab:
        st.subheader("📋 Consultores Disponíveis")
        st.dataframe(df, use_container_width=True)
    with col_btn:
        if st.button("Limpar Tudo"):
            st.session_state.lista_consultores = []
            st.rerun()

    st.divider()

    # --- DEFINIÇÃO DO ATENDIMENTO ---
    st.subheader("📍 Novo Atendimento")
    cidade_destino = st.text_input("Informe a Cidade de Destino (Ex: Xangri-la):")

    if st.button("CALCULAR MELHOR ROTA", type="primary"):
        # Identificador único para evitar erro 403 Forbidden
        user_agent_unico = f"agente_logistica_luan_{int(time.time())}"
        geolocator = Nominatim(user_agent=user_agent_unico, timeout=20)
        
        # Busca coordenadas do destino
        loc_dest = geolocator.geocode(f"{cidade_destino}, RS, Brasil")

        if loc_dest:
            with st.spinner("Calculando distâncias e mapeando unidades..."):
                def processar_logistica(row):
                    time.sleep(1.2) # Pausa de segurança para o Geopy
                    l = geolocator.geocode(f"{row['Unidade']}, RS, Brasil")
                    if l:
                        dist = geodesic((loc_dest.latitude, loc_dest.longitude), (l.latitude, l.longitude)).km
                        return dist, (l.latitude, l.longitude)
                    return 9999, None

                # Aplica o cálculo em cada linha
                resultados = df.apply(processar_logistica, axis=1)
                df['Distancia'] = [r[0] for r in resultados]
                df['Coords'] = [r[1] for r in resultados]

                # LÓGICA: Prioriza Menor Ocupação e depois Menor Distância
                vencedor = df.sort_values(by=['Ocupação', 'Distancia']).iloc[0]

                # Exibição do Resultado
                st.success(f"🏆 Melhor Opção: **{vencedor['Consultor']}**")
                c1, c2 = st.columns(2)
                c1.metric("Distância", f"{vencedor['Distancia']:.1f} km")
                c2.metric("Ocupação", f"{vencedor['Ocupação']}%")
                
                # --- RENDERIZAÇÃO DO MAPA ---
                st.subheader("🗺️ Visualização do Trajeto")
                
                # Cria o mapa centralizado no destino
                m = folium.Map(location=[loc_dest.latitude, loc_dest.longitude], zoom_start=8)
                
                # Marcador do Cliente (Destino)
                folium.Marker(
                    [loc_dest.latitude, loc_dest.longitude], 
                    tooltip="Destino do Atendimento", 
                    icon=folium.Icon(color='red', icon='info-sign')
                ).add_to(m)

                # Marcador da Unidade do Vencedor e Linha de Trajeto
                if vencedor['Coords']:
                    folium.Marker(
                        vencedor['Coords'], 
                        tooltip=f"Unidade: {vencedor['Unidade']}", 
                        icon=folium.Icon(color='green', icon='user')
                    ).add_to(m)
                    
                    # Desenha a linha azul entre os pontos
                    folium.PolyLine(
                        locations=[[loc_dest.latitude, loc_dest.longitude], vencedor['Coords']],
                        color="blue", weight=4, opacity=0.8, dash_array='10'
                    ).add_to(m)

                # Exibe o mapa no Streamlit
                st_folium(m, width=1200, height=500)
                st.balloons()
        else:
            st.error("Não foi possível localizar a cidade de destino no mapa. Verifique a ortografia.")
else:
    st.info("💡 Comece adicionando os consultores e suas unidades na barra lateral.")
