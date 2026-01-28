import streamlit as st
import pandas as pd
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import folium
from streamlit_folium import st_folium
import requests
import time
from datetime import datetime

st.set_page_config(page_title="Agente Logística V3.4", layout="wide")

# --- FUNÇÃO DE LEITURA BRUTA (A MAIS SEGURA) ---
def carregar_excel_bruto(arquivo):
    try:
        # 1. Lê o arquivo SEM cabeçalho (traz tudo o que está na planilha)
        df_raw = pd.read_excel(arquivo, header=None)
        
        # 2. Procura em qual linha estão as palavras chaves "Consultor" e "Unidade"
        idx_cabecalho = -1
        for i, row in df_raw.iterrows():
            row_str = row.astype(str).str.lower() # Converte para minusculo para facilitar busca
            # Verifica se na mesma linha aparecem 'consultor' e 'unidade'
            if row_str.str.contains('consultor').any() and row_str.str.contains('unidade').any():
                idx_cabecalho = i
                break
        
        if idx_cabecalho == -1:
            return None, "Não encontrei a linha de cabeçalho com 'Consultor' e 'Unidade'."

        # 3. Define a linha encontrada como cabeçalho
        df_final = df_raw.iloc[idx_cabecalho + 1:].copy()
        df_final.columns = df_raw.iloc[idx_cabecalho]
        
        # 4. Limpeza agressiva nos nomes das colunas
        df_final.columns = df_final.columns.astype(str).str.strip()
        
        # 5. Remove linhas totalmente vazias, mas NÃO remove se faltar apenas o nome
        df_final = df_final.dropna(how='all')
        
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

st.title("🤖 Agente de Logística V3.4: Leitura Profunda")

# --- BARRA LATERAL ---
with st.sidebar:
    st.header("📁 Gestão de Dados")
    arquivo = st.file_uploader("Carregar Excel (.xlsx)", type=["xlsx"])
    
    if arquivo:
        df_lido, erro = carregar_excel_bruto(arquivo)
        
        if df_lido is not None:
            st.session_state.base = df_lido
            st.success(f"Sucesso! {len(df_lido)} linhas carregadas.")
        else:
            st.error(f"Erro: {erro}")

    mes_ref = None
    if not st.session_state.base.empty:
        st.divider()
        # Lista com nomes exatos para o selectbox
        lista_meses = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho', 
                       'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro']
        mes_atual_idx = datetime.now().month - 1
        mes_ref = st.selectbox("Mês de Referência:", options=lista_meses, index=mes_atual_idx)

    if st.button("Limpar Sistema"):
        st.session_state.base = pd.DataFrame()
        st.session_state.resultado = None
        st.rerun()

# --- DIAGNÓSTICO E TABELA ---
if not st.session_state.base.empty:
    df = st.session_state.base.copy()

    # --- DIAGNÓSTICO (Para você ver o que o Python vê) ---
    with st.expander("🔍 Ver Dados Brutos (Diagnóstico)", expanded=False):
        st.write("Colunas encontradas:", df.columns.tolist())
        st.dataframe(df.head())

    # --- TRATAMENTO DE OCUPAÇÃO ---
    # Verifica se a coluna do mês existe (ignorando maiúsculas/minusculas)
    coluna_mes_encontrada = None
    for col in df.columns:
        if mes_ref.lower() == col.lower():
            coluna_mes_encontrada = col
            break
    
    if coluna_mes_encontrada:
        # Limpeza forçada de caracteres estranhos
        df['Ocupacao'] = (df[coluna_mes_encontrada].astype(str)
                          .str.replace('%', '')
                          .str.replace(',', '.')
                          .str.strip())
        df['Ocupacao'] = pd.to_numeric(df['Ocupacao'], errors='coerce').fillna(0)
    else:
        st.warning(f"⚠️ Coluna '{mes_ref}' não encontrada. Verifique se o nome no Excel está correto (sem espaços extras).")
        df['Ocupacao'] = 0.0

    # --- TABELA FINAL ---
    st.subheader(f"📋 Equipa: {mes_ref} (Total: {len(df)})")
    
    # Tenta mostrar as colunas principais, se existirem
    cols_mostrar = [c for c in ['Consultor', 'Unidade', 'Ocupacao'] if c in df.columns]
    st.dataframe(df[cols_mostrar], use_container_width=True)

    st.divider()
    destino = st.text_input("📍 Informe a Cidade do Cliente:")

    if st.button("CALCULAR LOGÍSTICA", type="primary"):
        geolocator = Nominatim(user_agent=f"agente_v34_{int(time.time())}", timeout=20)
        loc_dest = geolocator.geocode(f"{destino}, RS, Brasil")

        if loc_dest:
            with st.spinner("Calculando rotas..."):
                def analisar(row):
                    time.sleep(1.1)
                    # Verifica se Unidade é válida
                    if pd.isna(row.get('Unidade')) or str(row.get('Unidade')).strip() == '':
                        return pd.Series([9999, None, None])
                        
                    l = geolocator.geocode(f"{row['Unidade']}, RS, Brasil")
                    if l:
                        origem = (l.latitude, l.longitude)
                        dest_c = (loc_dest.latitude, loc_dest.longitude)
                        cam, km = buscar_rota_real(origem, dest_c)
                        if not km: km = geodesic(origem, dest_c).km
                        return pd.Series([km, origem, cam])
                    return pd.Series([9999, None, None])

                df[['Distancia', 'Coords', 'Trajeto']] = df.apply(analisar, axis=1)
                
                # Filtra apenas quem tem rota válida
                validos = df[df['Distancia'] < 9000]
                
                if not validos.empty:
                    venc = validos.sort_values(by=['Ocupacao', 'Distancia']).iloc[0]
                    st.session_state.resultado = {'venc': venc, 'dest': (loc_dest.latitude, loc_dest.longitude)}
                else:
                    st.error("Nenhuma rota válida encontrada. Verifique as cidades das unidades.")
        else:
            st.error("Cidade de destino não encontrada.")

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
        st_folium(m, width=1200, height=500, key="mapa_final_v34")

else:
    st.info("💡 Carregue o ficheiro Excel. O sistema fará uma varredura profunda para encontrar os dados.")
