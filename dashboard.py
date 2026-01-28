import streamlit as st
import pandas as pd
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import folium
from streamlit_folium import st_folium
import requests
import time
from datetime import datetime

st.set_page_config(page_title="Agente Logística V3.3", layout="wide")

# --- FUNÇÃO ROBUSTA DE LEITURA DO EXCEL ---
def carregar_excel_inteligente(arquivo):
    """
    Lê o Excel sem assumir que o cabeçalho é a primeira linha.
    Procura a linha que contém a palavra 'Consultor' e define-a como cabeçalho.
    """
    try:
        # 1. Lê as primeiras 10 linhas sem cabeçalho para inspecionar
        df_preview = pd.read_excel(arquivo, header=None, nrows=10)
        
        idx_cabecalho = -1
        # 2. Procura em qual linha está a palavra "Consultor"
        for i, row in df_preview.iterrows():
            linha_texto = row.astype(str).str.strip()
            if linha_texto.str.contains('Consultor', case=False).any():
                idx_cabecalho = i
                break
        
        if idx_cabecalho == -1:
            return None, "Não foi possível encontrar a coluna 'Consultor'. Verifique o Excel."

        # 3. Recarrega o Excel usando a linha correta como cabeçalho
        df_final = pd.read_excel(arquivo, header=idx_cabecalho)
        
        # 4. Limpeza final dos nomes das colunas
        df_final.columns = df_final.columns.astype(str).str.strip()
        
        return df_final, None
    except Exception as e:
        return None, str(e)

# --- FUNÇÃO DE ROTA ---
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

# --- STATE ---
if 'base' not in st.session_state:
    st.session_state.base = pd.DataFrame()
if 'resultado' not in st.session_state:
    st.session_state.resultado = None

st.title("🤖 Agente de Logística: Correção Automática V3.3")

# --- BARRA LATERAL ---
with st.sidebar:
    st.header("📁 Gestão de Dados")
    arquivo = st.file_uploader("Carregar Excel (.xlsx)", type=["xlsx"])
    
    if arquivo:
        # Usa a nova função inteligente
        df_lido, erro = carregar_excel_inteligente(arquivo)
        
        if df_lido is not None:
            st.session_state.base = df_lido
            st.success("Tabela localizada e carregada!")
        else:
            st.error(f"Erro Crítico: {erro}")

    mes_ref = None
    if not st.session_state.base.empty:
        st.divider()
        lista_meses = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho', 
                       'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro']
        mes_atual_idx = datetime.now().month - 1
        mes_ref = st.selectbox("Mês de Referência:", options=lista_meses, index=mes_atual_idx)

    if st.button("Limpar Sistema"):
        st.session_state.base = pd.DataFrame()
        st.session_state.resultado = None
        st.rerun()

# --- TABELA E CÁLCULOS ---
if not st.session_state.base.empty:
    df_temp = st.session_state.base.copy()
    
    # Tratamento de Ocupação (Limpeza de %, vírgula e espaços)
    if mes_ref in df_temp.columns:
        df_temp['Ocupacao'] = (df_temp[mes_ref].astype(str)
                               .str.replace('%', '')
                               .str.replace(',', '.')
                               .str.strip())
        df_temp['Ocupacao'] = pd.to_numeric(df_temp['Ocupacao'], errors='coerce').fillna(0)
    else:
        st.warning(f"Coluna {mes_ref} não encontrada. Usando 0%.")
        df_temp['Ocupacao'] = 0.0

    # TABELA FILTRADA
    st.subheader(f"📋 Equipa: {mes_ref}")
    cols_desejadas = ['Consultor', 'Unidade', 'Ocupacao']
    cols_existentes = [c for c in cols_desejadas if c in df_temp.columns]
    st.dataframe(df_temp[cols_existentes], use_container_width=True)

    st.divider()
    destino = st.text_input("📍 Informe a Cidade do Cliente:")

    if st.button("CALCULAR LOGÍSTICA", type="primary"):
        geolocator = Nominatim(user_agent=f"agente_v33_{int(time.time())}", timeout=20)
        loc_dest = geolocator.geocode(f"{destino}, RS, Brasil")

        if loc_dest:
            with st.spinner("Calculando rotas..."):
                def analisar(row):
                    # Pequena pausa para evitar bloqueio
                    time.sleep(1.1)
                    l = geolocator.geocode(f"{row['Unidade']}, RS, Brasil")
                    if l:
                        origem = (l.latitude, l.longitude)
                        dest_c = (loc_dest.latitude, loc_dest.longitude)
                        # Tenta rota real, falha para linear se necessário
                        cam, km = buscar_rota_real(origem, dest_c)
                        if not km: km = geodesic(origem, dest_c).km
                        return pd.Series([km, origem, cam])
                    return pd.Series([9999, None, None])

                df_temp[['Distancia', 'Coords', 'Trajeto']] = df_temp.apply(analisar, axis=1)
                
                # Ordena: Menor Ocupação primeiro, depois Menor Distância
                venc = df_temp.sort_values(by=['Ocupacao', 'Distancia']).iloc[0]
                st.session_state.resultado = {'venc': venc, 'dest': (loc_dest.latitude, loc_dest.longitude)}
        else:
            st.error("Cidade não encontrada.")

    # --- MAPA ---
    if st.session_state.resultado:
        res = st.session_state.resultado
        v = res['venc']
        cor = "orange" if v['Ocupacao'] > 80 else "green"

        st.info(f"🏆 Sugestão: **{v['Consultor']}** ({v['Unidade']})")
        c1, c2 = st.columns(2)
        c1.metric("Distância", f"{v['Distancia']:.1f} km")
        c2.metric("Ocupação", f"{v['Ocupacao']:.1f}%")

        m = folium.Map(location=res['dest'], zoom_start=8)
        folium.Marker(res['dest'], tooltip="Cliente", icon=folium.Icon(color='red')).add_to(m)
        if v['Coords']:
            folium.Marker(v['Coords'], tooltip=v['Unidade'], icon=folium.Icon(color=cor, icon='user')).add_to(m)
            if v['Trajeto']:
                folium.PolyLine(v['Trajeto'], color="blue", weight=5, opacity=0.7).add_to(m)
        st_folium(m, width=1200, height=500, key="mapa_final_v33")

else:
    st.info("💡 Carregue o ficheiro Excel. O sistema detectará o cabeçalho automaticamente.")
