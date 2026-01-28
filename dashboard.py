import streamlit as st
import pandas as pd
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
from geopy.exc import GeocoderUnavailable, GeocoderTimedOut
import folium
from streamlit_folium import st_folium
import requests
import time
from datetime import datetime

st.set_page_config(page_title="Agente Logística V3.7", layout="wide")

# --- FUNÇÃO DE LEITURA (MANTIDA DA V3.6) ---
def carregar_excel_bruto(arquivo):
    try:
        df_raw = pd.read_excel(arquivo, header=None)
        idx_cabecalho = -1
        for i, row in df_raw.iterrows():
            row_str = row.astype(str).str.lower()
            if row_str.str.contains('consultor').any() and row_str.str.contains('unidade').any():
                idx_cabecalho = i
                break
        
        if idx_cabecalho == -1: return None, "Cabeçalho não encontrado."

        df_final = df_raw.iloc[idx_cabecalho + 1:].copy()
        df_final.columns = df_raw.iloc[idx_cabecalho]
        df_final.columns = df_final.columns.astype(str).str.strip()
        df_final = df_final.dropna(how='all')
        return df_final, None
    except Exception as e:
        return None, str(e)

# --- NOVA FUNÇÃO: GEOCODIFICAÇÃO SEGURA (BLINDAGEM) ---
def geocodificar_seguro(geolocator, endereco, tentativas=3):
    """Tenta buscar o endereço até 3 vezes se a internet falhar."""
    for i in range(tentativas):
        try:
            # Tenta buscar
            location = geolocator.geocode(endereco)
            return location
        except (GeocoderUnavailable, GeocoderTimedOut):
            # Se der erro, espera 2 segundos e tenta de novo
            time.sleep(2)
            continue
    return None

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
if 'base' not in st.session_state: st.session_state.base = pd.DataFrame()
if 'resultado' not in st.session_state: st.session_state.resultado = None

st.title("🤖 Agente Logística V3.7: Conexão Blindada")

# --- BARRA LATERAL ---
with st.sidebar:
    st.header("📁 Dados")
    arquivo = st.file_uploader("Carregar Excel (.xlsx)", type=["xlsx"])
    if arquivo:
        df_lido, erro = carregar_excel_bruto(arquivo)
        if df_lido is not None:
            st.session_state.base = df_lido
            st.success(f"Carregado: {len(df_lido)} linhas.")
        else:
            st.error(erro)

    mes_ref = None
    if not st.session_state.base.empty:
        st.divider()
        lista_meses = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho', 
                       'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro']
        mes_atual_idx = datetime.now().month - 1
        mes_ref = st.selectbox("Mês de Referência:", options=lista_meses, index=mes_atual_idx)

    if st.button("Limpar"):
        st.session_state.base = pd.DataFrame()
        st.session_state.resultado = None
        st.rerun()

# --- LÓGICA PRINCIPAL ---
if not st.session_state.base.empty:
    df = st.session_state.base.copy()

    # Tratamento da Ocupação
    col_mes = None
    for c in df.columns:
        if str(c).lower() == str(mes_ref).lower():
            col_mes = c
            break
            
    if col_mes:
        df['Ocupacao'] = (df[col_mes].astype(str).str.replace('%', '').str.replace(',', '.').str.strip())
        df['Ocupacao'] = pd.to_numeric(df['Ocupacao'], errors='coerce').fillna(0)
        if df['Ocupacao'].max() <= 1.5: df['Ocupacao'] = df['Ocupacao'] * 100
    else:
        st.warning(f"Mês {mes_ref} não encontrado.")
        df['Ocupacao'] = 0.0

    # Tabela
    st.subheader(f"📋 Equipa: {mes_ref}")
    cols_mostrar = [c for c in ['Consultor', 'Unidade', 'Ocupacao'] if c in df.columns]
    st.dataframe(df[cols_mostrar], use_container_width=True, 
                 column_config={"Ocupacao": st.column_config.NumberColumn("Ocupação (%)", format="%.2f %%")})

    st.divider()
    destino = st.text_input("📍 Informe a Cidade do Cliente:")

    if st.button("CALCULAR LOGÍSTICA", type="primary"):
        # User agent único a cada clique para evitar bloqueio
        user_agent_unico = f"agente_logistica_v37_{int(time.time())}"
        geolocator = Nominatim(user_agent=user_agent_unico, timeout=10)
        
        # 1. Busca Segura do Destino (Aqui é onde estava dando erro!)
        loc_dest = geocodificar_seguro(geolocator, f"{destino}, RS, Brasil")

        if loc_dest:
            with st.spinner("Calculando rotas (isso pode levar alguns segundos)..."):
                def analisar(row):
                    unidade = str(row.get('Unidade', '')).strip()
                    if not unidade or unidade.lower() == 'nan': return pd.Series([9999, None, None])

                    # 2. Busca Segura da Origem
                    l = geocodificar_seguro(geolocator, f"{unidade}, RS, Brasil")
                    
                    if l:
                        origem = (l.latitude, l.longitude)
                        dest_c = (loc_dest.latitude, loc_dest.longitude)
                        cam, km = buscar_rota_real(origem, dest_c)
                        if not km: km = geodesic(origem, dest_c).km
                        return pd.Series([km, origem, cam])
                    return pd.Series([9999, None, None])

                df[['Distancia', 'Coords', 'Trajeto']] = df.apply(analisar, axis=1)
                
                validos = df[df['Distancia'] < 9000]
                
                if not validos.empty:
                    venc = validos.sort_values(by=['Ocupacao', 'Distancia']).iloc[0]
                    st.session_state.resultado = {'venc': venc, 'dest': (loc_dest.latitude, loc_dest.longitude)}
                else:
                    st.error("Nenhuma rota encontrada.")
        else:
            st.error(f"Erro: Não conseguimos localizar a cidade '{destino}'. O servidor de mapas pode estar instável. Tente novamente em 10 segundos.")

    # --- MAPA ---
    if st.session_state.resultado:
        res = st.session_state.resultado
        v = res['venc']
        cor = "orange" if v['Ocupacao'] > 80 else "green"

        st.info(f"🏆 Sugestão: **{v['Consultor']}** ({v['Unidade']})")
        c1, c2 = st.columns(2)
        c1.metric("Distância", f"{v['Distancia']:.1f} km")
        c2.metric("Ocupação", f"{v['Ocupacao']:.2f}%")

        m = folium.Map(location=res['dest'], zoom_start=8)
        folium.Marker(res['dest'], tooltip="Cliente", icon=folium.Icon(color='red')).add_to(m)
        if v['Coords']:
            folium.Marker(v['Coords'], tooltip=f"{v['Consultor']} - {v['Ocupacao']:.1f}%", icon=folium.Icon(color=cor, icon='user')).add_to(m)
            if v['Trajeto']:
                folium.PolyLine(v['Trajeto'], color="blue", weight=5, opacity=0.7).add_to(m)
        st_folium(m, width=1200, height=500, key="mapa_final_v37")
else:
    st.info("💡 Carregue o ficheiro Excel.")
