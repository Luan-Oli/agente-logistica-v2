import streamlit as st
import pandas as pd
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import folium
from streamlit_folium import st_folium
import requests
import time
from datetime import datetime

st.set_page_config(page_title="Agente Logística V3.6", layout="wide")

# --- FUNÇÃO DE LEITURA BRUTA (Mantida da V3.4 pois funcionou!) ---
def carregar_excel_bruto(arquivo):
    try:
        df_raw = pd.read_excel(arquivo, header=None)
        
        # Procura a linha de cabeçalho
        idx_cabecalho = -1
        for i, row in df_raw.iterrows():
            row_str = row.astype(str).str.lower()
            if row_str.str.contains('consultor').any() and row_str.str.contains('unidade').any():
                idx_cabecalho = i
                break
        
        if idx_cabecalho == -1:
            return None, "Cabeçalho não encontrado."

        # Reconstrói o DataFrame a partir da linha certa
        df_final = df_raw.iloc[idx_cabecalho + 1:].copy()
        df_final.columns = df_raw.iloc[idx_cabecalho]
        df_final.columns = df_final.columns.astype(str).str.strip()
        
        # Remove linhas totalmente vazias
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

st.title("🤖 Agente de Logística V3.6: Ajuste Percentual")

# --- BARRA LATERAL ---
with st.sidebar:
    st.header("📁 Gestão de Dados")
    arquivo = st.file_uploader("Carregar Excel (.xlsx)", type=["xlsx"])
    
    if arquivo:
        df_lido, erro = carregar_excel_bruto(arquivo)
        if df_lido is not None:
            st.session_state.base = df_lido
            st.success(f"Sucesso! {len(df_lido)} consultores carregados.")
        else:
            st.error(erro)

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

# --- LÓGICA PRINCIPAL ---
if not st.session_state.base.empty:
    df = st.session_state.base.copy()

    # 1. Encontrar a coluna do mês
    col_mes = None
    for c in df.columns:
        if str(c).lower() == str(mes_ref).lower():
            col_mes = c
            break
            
    if col_mes:
        # Limpa caracteres e converte para número
        df['Ocupacao'] = (df[col_mes].astype(str)
                          .str.replace('%', '')
                          .str.replace(',', '.')
                          .str.strip())
        df['Ocupacao'] = pd.to_numeric(df['Ocupacao'], errors='coerce').fillna(0)
        
        # --- CORREÇÃO DE ESCALA (0.65 -> 65.0) ---
        # Se o maior valor for pequeno (<= 1.5), assumimos que está em decimal (ex: 0.50)
        # e multiplicamos por 100 para virar porcentagem (ex: 50.0)
        if df['Ocupacao'].max() <= 1.5:
             df['Ocupacao'] = df['Ocupacao'] * 100
             
    else:
        st.warning(f"Coluna {mes_ref} não encontrada.")
        df['Ocupacao'] = 0.0

    # 2. Exibição da Tabela Formatada
    st.subheader(f"📋 Equipa: {mes_ref} (Total: {len(df)})")
    
    cols_mostrar = [c for c in ['Consultor', 'Unidade', 'Ocupacao'] if c in df.columns]
    
    # Usa column_config para mostrar o símbolo "%" na tabela sem estragar a ordenação
    st.dataframe(
        df[cols_mostrar],
        use_container_width=True,
        column_config={
            "Ocupacao": st.column_config.NumberColumn(
                "Ocupação (%)",
                format="%.2f %%"  # Isso faz aparecer "65.48 %"
            )
        }
    )

    st.divider()
    destino = st.text_input("📍 Informe a Cidade do Cliente:")

    if st.button("CALCULAR LOGÍSTICA", type="primary"):
        geolocator = Nominatim(user_agent=f"agente_v36_{int(time.time())}", timeout=20)
        loc_dest = geolocator.geocode(f"{destino}, RS, Brasil")

        if loc_dest:
            with st.spinner("Calculando rotas..."):
                def analisar(row):
                    unidade = str(row.get('Unidade', '')).strip()
                    if not unit or unidade.lower() == 'nan': return pd.Series([9999, None, None])

                    time.sleep(1.1)
                    l = geolocator.geocode(f"{unidade}, RS, Brasil")
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
                    # Ordena: Menor Ocupação -> Menor Distância
                    venc = validos.sort_values(by=['Ocupacao', 'Distancia']).iloc[0]
                    st.session_state.resultado = {'venc': venc, 'dest': (loc_dest.latitude, loc_dest.longitude)}
                else:
                    st.error("Nenhuma rota encontrada.")
        else:
            st.error("Cidade de destino não encontrada.")

    # --- MAPA ---
    if st.session_state.resultado:
        res = st.session_state.resultado
        v = res['venc']
        # Alerta se ocupação > 80%
        cor = "orange" if v['Ocupacao'] > 80 else "green"

        st.info(f"🏆 Sugestão: **{v['Consultor']}** ({v['Unidade']})")
        c1, c2 = st.columns(2)
        c1.metric("Distância", f"{v['Distancia']:.1f} km")
        c2.metric("Ocupação", f"{v['Ocupacao']:.2f}%") # Exibe com %

        m = folium.Map(location=res['dest'], zoom_start=8)
        folium.Marker(res['dest'], tooltip="Cliente", icon=folium.Icon(color='red')).add_to(m)
        if v['Coords']:
            folium.Marker(v['Coords'], tooltip=f"{v['Consultor']} - {v['Ocupacao']:.1f}%", icon=folium.Icon(color=cor, icon='user')).add_to(m)
            if v['Trajeto']:
                folium.PolyLine(v['Trajeto'], color="blue", weight=5, opacity=0.7).add_to(m)
        st_folium(m, width=1200, height=500, key="mapa_final_v36")
else:
    st.info("💡 Carregue o ficheiro Excel.")
