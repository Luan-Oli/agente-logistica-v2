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

st.set_page_config(page_title="Agente Logística V4.0", layout="wide")

# --- FUNÇÕES DE SUPORTE ---
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

def geocodificar_seguro(geolocator, endereco, tentativas=3):
    for i in range(tentativas):
        try:
            geolocator.user_agent = f"agente_v40_{int(time.time())}_{i}"
            return geolocator.geocode(endereco, timeout=10)
        except (GeocoderUnavailable, GeocoderTimedOut):
            time.sleep(2)
            continue
    return None

def buscar_rota_real(ponto_a, ponto_b):
    url = f"http://router.project-osrm.org/route/v1/driving/{ponto_a[1]},{ponto_a[0]};{ponto_b[1]},{ponto_b[0]}?overview=full&geometries=geojson"
    try:
        response = requests.get(url, timeout=5)
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

st.title("🤖 Agente Logística V4.0: Custos & Rotas")

# --- BARRA LATERAL ---
with st.sidebar:
    st.header("📁 Dados")
    arquivo = st.file_uploader("Carregar Excel (.xlsx)", type=["xlsx"])
    if arquivo:
        df_lido, erro = carregar_excel_bruto(arquivo)
        if df_lido is not None:
            st.session_state.base = df_lido
            st.success(f"Carregado: {len(df_lido)} consultores.")
        else:
            st.error(erro)

    mes_ref = None
    if not st.session_state.base.empty:
        st.divider()
        lista_meses = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho', 
                       'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro']
        mes_atual_idx = datetime.now().month - 1
        mes_ref = st.selectbox("Mês de Referência:", options=lista_meses, index=mes_atual_idx)
        
        st.divider()
        # --- NOVIDADE: CALCULADORA FINANCEIRA (Polo TSI) ---
        st.header("🚗 Custos de Viagem")
        st.caption("Base: Polo TSI 1.0 Turbo")
        
        # Padrões baseados na pesquisa (15 km/l estrada / R$ 6,35 gasolina RS)
        preco_combustivel = st.number_input("Preço Gasolina (R$):", value=6.35, step=0.01, format="%.2f")
        consumo_carro = st.number_input("Consumo Estrada (km/l):", value=15.0, step=0.1, format="%.1f")
        
        st.info(f"Custo por km: R$ {(preco_combustivel/consumo_carro):.2f}")

    if st.button("Limpar"):
        st.session_state.base = pd.DataFrame()
        st.session_state.resultado = None
        st.rerun()

# --- LÓGICA PRINCIPAL ---
if not st.session_state.base.empty:
    df = st.session_state.base.copy()

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

    st.subheader(f"📋 Equipa: {mes_ref}")
    cols_mostrar = [c for c in ['Consultor', 'Unidade', 'Ocupacao'] if c in df.columns]
    st.dataframe(df[cols_mostrar], use_container_width=True, 
                 column_config={"Ocupacao": st.column_config.NumberColumn("Ocupação (%)", format="%.2f %%")})

    st.divider()
    destino = st.text_input("📍 Informe a Cidade do Cliente:")

    if st.button("CALCULAR LOGÍSTICA + CUSTOS", type="primary"):
        with st.status("Processando logística...", expanded=True) as status:
            
            geolocator = Nominatim(user_agent=f"agente_v40_{int(time.time())}", timeout=10)
            
            st.write(f"🔍 Localizando: **{destino}**...")
            loc_dest = geocodificar_seguro(geolocator, f"{destino}, RS, Brasil")

            if loc_dest:
                st.write("✅ Destino confirmado.")
                st.write("🗺️ Mapeando unidades (Cache)...")
                
                unidades_unicas = df['Unidade'].dropna().unique()
                coords_cache = {}
                prog_bar = st.progress(0)
                
                for i, unidade in enumerate(unidades_unicas):
                    uni_str = str(unidade).strip()
                    if uni_str and uni_str.lower() != 'nan':
                        loc_u = geocodificar_seguro(geolocator, f"{uni_str}, RS, Brasil")
                        coords_cache[uni_str] = (loc_u.latitude, loc_u.longitude) if loc_u else None
                        time.sleep(1.1)
                    prog_bar.progress((i + 1) / len(unidades_unicas))
                
                st.write("🚚 Calculando rotas e custos...")
                
                def aplicar_rota(row):
                    uni = str(row.get('Unidade', '')).strip()
                    coords_origem = coords_cache.get(uni)
                    if coords_origem:
                        coords_dest = (loc_dest.latitude, loc_dest.longitude)
                        cam, km = buscar_rota_real(coords_origem, coords_dest)
                        if not km: km = geodesic(coords_origem, coords_dest).km
                        return pd.Series([km, coords_origem, cam])
                    return pd.Series([9999, None, None])

                df[['Distancia', 'Coords', 'Trajeto']] = df.apply(aplicar_rota, axis=1)
                
                validos = df[df['Distancia'] < 9000]
                
                if not validos.empty:
                    venc = validos.sort_values(by=['Ocupacao', 'Distancia']).iloc[0]
                    st.session_state.resultado = {'venc': venc, 'dest': (loc_dest.latitude, loc_dest.longitude)}
                    status.update(label="Cálculo Finalizado!", state="complete", expanded=False)
                else:
                    status.update(label="Sem rotas válidas", state="error")
                    st.error("Nenhuma rota encontrada.")
            else:
                status.update(label="Erro no Destino", state="error")
                st.error("Cidade não encontrada.")

    # --- RESULTADOS COM FINANCEIRO ---
    if st.session_state.resultado:
        res = st.session_state.resultado
        v = res['venc']
        cor = "orange" if v['Ocupacao'] > 80 else "green"

        # Cálculos Financeiros (Ida e Volta)
        dist_total = v['Distancia'] * 2
        litros_necessarios = dist_total / consumo_carro
        custo_total = litros_necessarios * preco_combustivel

        st.success(f"🏆 Melhor Opção: **{v['Consultor']}** ({v['Unidade']})")
        
        # Métricas em 3 colunas
        c1, c2, c3 = st.columns(3)
        c1.metric("Distância (Só Ida)", f"{v['Distancia']:.1f} km")
        c2.metric("Ocupação", f"{v['Ocupacao']:.2f}%")
        c3.metric("Custo Estimado (Ida+Volta)", f"R$ {custo_total:.2f}", help=f"Baseado em {dist_total:.1f}km totais")

        m = folium.Map(location=res['dest'], zoom_start=8)
        folium.Marker(res['dest'], tooltip="Cliente", icon=folium.Icon(color='red')).add_to(m)
        if v['Coords']:
            folium.Marker(v['Coords'], tooltip=f"{v['Consultor']} | R$ {custo_total:.0f}", icon=folium.Icon(color=cor, icon='user')).add_to(m)
            if v['Trajeto']:
                folium.PolyLine(v['Trajeto'], color="blue", weight=5, opacity=0.7).add_to(m)
        st_folium(m, width=1200, height=500, key="mapa_final_v40")
else:
    st.info("💡 Carregue o ficheiro Excel.")
