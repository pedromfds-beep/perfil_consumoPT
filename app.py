import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# Configuração da página do Streamlit
st.set_page_config(
    page_title="Simulador de Perfil de Consumo - E-REDES",
    page_icon="⚡",
    layout="wide"
)

st.title("⚡ Simulador de Perfil de Consumo Elétrico em Portugal")
st.markdown("""
Esta aplicação simula o perfil horário e de 15 minutos de um ponto de entrega (CPE) em **Baixa Tensão Normal (BTN)**
utilizando as matrizes oficiais de coeficientes da E-REDES para 2026.
""")

st.markdown(""" BTN C (≤ 13.8 kVA, ≤ 7140 kWh/ano) \n\n BTN B (≤ 13.8 kVA, > 7140 kWh/ano) \n\n BTN A (> 13.8 kVA)""")

# --- CACHE PARA CARREGAMENTO DO FICHEIRO ---
@st.cache_data
def carregar_dados_brutos(caminho_ficheiro: str):
    df_raw = pd.read_excel(caminho_ficheiro, sheet_name='2026', header=None)
    return df_raw

# Caminho para o ficheiro Excel no diretório
ficheiro_excel = "Perfil_Consumo_Injeção_E-REDES_2026.xlsx"

try:
    df_raw = carregar_dados_brutos(ficheiro_excel)
except Exception as e:
    st.error(f"Erro ao carregar o ficheiro Excel '{ficheiro_excel}': {e}")
    st.stop()

# --- BARRA LATERAL (CONTROLOS DA SIMULAÇÃO) ---
st.sidebar.header("Parâmetros de Simulação")

perfil_escolhido = st.sidebar.selectbox(
    "Selecione a Classe de Perfil (BTN):",
    options=['BTN_C', 'BTN_B', 'BTN_A'],
    format_func=lambda x: {
        'BTN_C': 'BTN C (Habitações Típicas)',
        'BTN_B': 'BTN B (Alto Consumo Residencial/Comércio)',
        'BTN_A': 'BTN A (Grandes Instalações/Negócios)'
    }[x]
)

consumo_anual = st.sidebar.number_input(
    "Consumo Anual Estimado (kWh):",
    min_value=500.0,
    max_value=100000.0,
    value=4200.0,
    step=100.0
)

st.sidebar.markdown("---")
st.sidebar.markdown("### Visualização Temporal")
modo_visualizacao = st.sidebar.radio(
    "Mostrar período:",
    options=['Primeira Semana do Ano', 'Mês Completo (Janeiro)', 'Ano Inteiro Resumido']
)

# --- PROCESSAMENTO DOS DADOS ---
@st.cache_data
def processar_perfil(df_raw, perfil, consumo_anual):
    mapa_colunas_btn = {'BTN_A': 4, 'BTN_B': 5, 'BTN_C': 6}
    col_idx = mapa_colunas_btn[perfil]

    dados = df_raw.iloc[4:].copy()

    df = pd.DataFrame()
    df['data_base'] = pd.to_datetime(dados[0], errors='coerce')
    df['hora_str'] = dados[2].astype(str).str.strip().str.replace('a', '', case=False).str.replace('b', '', case=False)
    df['coeficiente'] = pd.to_numeric(dados[col_idx], errors='coerce')

    df = df.dropna(subset=['data_base', 'coeficiente']).copy()

    def parse_dt(row):
        d = row['data_base']
        h = row['hora_str']
        if h == '24:00':
            return (d + pd.Timedelta(days=1)).strftime('%Y-%m-%d') + ' 00:00'
        else:
            return d.strftime('%Y-%m-%d') + ' ' + h

    df['datetime_str'] = df.apply(parse_dt, axis=1)
    df['datetime'] = pd.to_datetime(df['datetime_str'])
    df = df.set_index('datetime').sort_index()

    soma_pesos = df['coeficiente'].sum()
    df['fator_normalizado'] = df['coeficiente'] / soma_pesos
    df['energia_kwh'] = df['fator_normalizado'] * consumo_anual
    df['potencia_media_kw'] = df['energia_kwh'] * 4

    return df[['energia_kwh', 'potencia_media_kw']]

df_resultado = processar_perfil(df_raw, perfil_escolhido, consumo_anual)

# --- MÉTRICAS PRINCIPAIS (KPIs) ---
col1, col2, col3, col4 = st.columns(4)
col1.metric("Consumo Anual Total", f"{consumo_anual:.0f} kWh")
col2.metric("Potência Média Global", f"{df_resultado['potencia_media_kw'].mean():.3f} kW")
col3.metric("Potência Máxima (Pico)", f"{df_resultado['potencia_media_kw'].max():.3f} kW")
#col4.metric("Registos Temporais (15m)", f"{len(df_resultado):,} blocos")

st.markdown("---")

# --- GRÁFICO INTERATIVO ---
st.subheader("📈 Perfil de Potência Média (15 min)")

# Filtragem de acordo com a escolha da barra lateral
if modo_visualizacao == 'Primeira Semana do Ano':
    df_plot = df_resultado.loc['2026-01-01':'2026-01-07 23:45']
    titulo_grafico = "Perfil de Consumo - Primeira Semana de Janeiro de 2026"
elif modo_visualizacao == 'Mês Completo (Janeiro)':
    df_plot = df_resultado.loc['2026-01-01':'2026-01-31 23:45']
    titulo_grafico = "Perfil de Consumo - Mês de Janeiro de 2026"
else:
    df_plot = df_resultado
    titulo_grafico = "Perfil de Consumo Anual Completo (2026)"

fig, ax = plt.subplots(figsize=(12, 5))
ax.plot(df_plot.index, df_plot['potencia_media_kw'], color='#1f77b4', linewidth=0.8)
ax.set_title(titulo_grafico, fontsize=12, fontweight='bold')
ax.set_xlabel("Data e Hora", fontsize=10)
ax.set_ylabel("Potência Média (kW)", fontsize=10)
ax.grid(True, linestyle='--', alpha=0.6)
ax.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m %H:%M'))
plt.tight_layout()

st.pyplot(fig)

# --- TABELA DE DADOS E EXPORTAÇÃO ---
with st.expander("🔍 Ver Amostra de Dados Detalhados (15 em 15 minutos)"):
    st.dataframe(df_resultado.head(100))

    # Botão para exportar em CSV
    csv_data = df_resultado.to_csv().encode('utf-8')
    st.download_button(
        label="📥 Descarregar Perfil Completo em CSV",
        data=csv_data,
        file_name=f"perfil_{perfil_escolhido.lower()}_{int(consumo_anual)}kwh.csv",
        mime="text/csv"
    )
