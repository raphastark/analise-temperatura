import requests
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Optional

# Configuração da página
st.set_page_config(
    page_title="Dashboard da Frota",
    page_icon="../favicon.ico",
    layout="wide"
)

# URL do Google Sheets (CSV público)
FLEET_MAPPING_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vTTVotmQMdtPhZ610EXnwE89MHFdWu31XpQVcU1XEapXiW1F9dUy_b7C4cyJhBTdGj3YdKLzcpIxx0i/pub?output=csv"
API_URL = "https://tracking.mobilidade.rio/api/v1/validador"

# Auto-refresh: 60 segundos (1 minuto)
AUTO_REFRESH_INTERVAL = 60


@st.cache_data(ttl=300)  # Cache de 5 min para o mapeamento da frota
def get_fleet_mapping() -> pd.DataFrame:
    """Busca o mapeamento de ônibus → validador do Google Sheets."""
    try:
        df = pd.read_csv(FLEET_MAPPING_URL)
        # Retorna apenas as colunas relevantes
        return df[['Nº Ordem', 'validador_com_sensor']].dropna(subset=['validador_com_sensor'])
    except Exception as e:
        st.error(f"Erro ao buscar mapeamento da frota: {e}")
        return pd.DataFrame()


def fetch_validator_data(validator_id: str) -> Optional[Dict]:
    """Busca dados de um único validador da API."""
    now = datetime.now(timezone(timedelta(hours=-3)))
    start_time = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end_time = start_time + timedelta(days=1)

    params = {
        "start_time": start_time.strftime("%Y-%m-%d %H:%M:%S"),
        "end_time": end_time.strftime("%Y-%m-%d %H:%M:%S"),
        "id_validador": validator_id,
        "limit": 1440,
    }

    try:
        r = requests.get(API_URL, params=params, timeout=10)
        if r.status_code == 200:
            data = r.json()
            if data and len(data) > 0:
                df = pd.DataFrame(data)
                # Pega a leitura mais recente
                df["timestamp_gps"] = pd.to_datetime(df["timestamp_gps"])
                df["timestamp_gps"] = df["timestamp_gps"].dt.tz_localize("UTC")
                df["timestamp_gps"] = df["timestamp_gps"].dt.tz_convert("America/Sao_Paulo")
                latest = df.iloc[df["timestamp_gps"].argmax()]

                return {
                    "temperatura": latest["temperatura"],
                    "timestamp": latest["timestamp_gps"],
                }
    except Exception as e:
        pass  # Silencioso para não poluir o log com erros esperados

    return None


@st.cache_data(ttl=60)  # Cache de 60 segundos para os dados dos validadores
def fetch_all_validators(validators: list) -> Dict:
    """Busca dados de todos os validadores em paralelo."""
    results = {}

    with ThreadPoolExecutor(max_workers=20) as executor:
        future_to_validator = {
            executor.submit(fetch_validator_data, v): v for v in validators
        }

        for future in as_completed(future_to_validator):
            validator_id = future_to_validator[future]
            try:
                data = future.result(timeout=15)
                results[validator_id] = data
            except Exception:
                results[validator_id] = None

    return results


def get_compliance_status(temp: Optional[float]) -> Dict:
    """Retorna o status de conformidade segundo SMTR 3857 (≤ 24°C)."""
    if temp is None:
        return {
            "status": "Sem sinal",
            "icon": "🔴",
            "color": "#FF4444"
        }
    elif temp <= 24:
        return {
            "status": "Dentro da norma",
            "icon": "✅",
            "color": "#00CC00"
        }
    else:
        return {
            "status": "Acima de 24°C",
            "icon": "⚠️",
            "color": "#FF9900"
        }


def render_kpis(fleet_data: pd.DataFrame):
    """Renderiza os KPIs no topo do dashboard."""
    total = len(fleet_data)
    com_sinal = fleet_data["temperatura"].notna().sum()
    sem_sinal = total - com_sinal
    fora_norma = (fleet_data["temperatura"] > 24).sum()
    conformidade = (com_sinal - fora_norma) / total * 100 if total > 0 else 0

    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric(label="Total de Veículos", value=f"{total}")

    with col2:
        st.metric(label="Com Sinal", value=f"{com_sinal}/{total}")

    with col3:
        st.metric(label="Sem Sinal", value=f"{sem_sinal}", delta=f"{sem_sinal/total*100:.1f}%" if sem_sinal > 0 else "")

    with col4:
        st.metric(label="Fora da Norma", value=fora_norma, delta=f"{fora_norma/total*100:.1f}%" if fora_norma > 0 else "")

    with col5:
        st.metric(label="Conformidade", value=f"{conformidade:.1f}%")


def render_fleet_table(fleet_data: pd.DataFrame, filter_option: str):
    """Renderiza a tabela da frota com formatação condicional."""
    # Aplica filtro
    if filter_option == "Apenas fora da norma":
        filtered = fleet_data[fleet_data["temperatura"] > 24]
    elif filter_option == "Apenas sem sinal":
        filtered = fleet_data[fleet_data["temperatura"].isna()]
    else:
        filtered = fleet_data

    # Prepara DataFrame para exibição
    display_df = filtered.copy()
    display_df = display_df.sort_values("Nº Ordem")

    # Cria coluna de status formatado (ícone + texto)
    display_df["status_display"] = display_df.apply(
        lambda row: f"{row['icon']} {row['status_raw']}", axis=1
    )

    # Formata temperatura
    display_df["temperatura"] = display_df["temperatura"].apply(
        lambda x: f"{x:.1f}°C" if pd.notna(x) else "—"
    )

    # Formata timestamp
    display_df["timestamp"] = display_df["timestamp"].apply(
        lambda x: x.strftime("%H:%M") if pd.notna(x) else "—"
    )

    # Renomeia colunas
    display_df = display_df.rename(columns={
        "Nº Ordem": "Ônibus",
        "validador_id": "Validador",
        "temperatura": "Temperatura",
        "status_display": "Status",
        "timestamp": "Última Leitura"
    })

    # Reordena colunas
    display_df = display_df[["Ônibus", "Validador", "Temperatura", "Status", "Última Leitura"]]

    # Exibe tabela
    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        height=600,
    )


# =============================================================================
# MAIN
# =============================================================================

st.title("🚌 Dashboard da Frota")

# Busca mapeamento da frota
fleet_mapping = get_fleet_mapping()

if fleet_mapping.empty:
    st.error("Não foi possível carregar o mapeamento da frota. Verifique a conexão com o Google Sheets.")
    st.stop()

# Busca dados de todos os validadores
validators = fleet_mapping["validador_com_sensor"].tolist()

with st.spinner("Buscando dados dos validadores..."):
    validator_results = fetch_all_validators(validators)

# Monta DataFrame com os resultados
fleet_data = []
for _, row in fleet_mapping.iterrows():
    bus_number = row["Nº Ordem"]
    validator_id = row["validador_com_sensor"]
    data = validator_results.get(validator_id)

    temp = data["temperatura"] if data else None
    timestamp = data["timestamp"] if data else None
    status_info = get_compliance_status(temp)

    fleet_data.append({
        "Nº Ordem": bus_number,
        "validador_id": validator_id,
        "temperatura": temp,
        "timestamp": timestamp,
        "status_raw": status_info["status"],
        "icon": status_info["icon"],
    })

fleet_df = pd.DataFrame(fleet_data)

# Renderiza KPIs
render_kpis(fleet_df)

st.divider()

# Filtros
col1, col2 = st.columns([3, 1])
with col1:
    filter_option = st.radio(
        "Filtrar:",
        ["Todos", "Apenas fora da norma", "Apenas sem sinal"],
        horizontal=True
    )
with col2:
    last_update = datetime.now(timezone(timedelta(hours=-3))).strftime("%H:%M:%S")
    st.caption(f"Última atualização: {last_update}")

# Renderiza tabela
render_fleet_table(fleet_df, filter_option)

# Auto-refresh usando JavaScript (meta refresh)
# Isso recarrega a página inteira a cada X segundos
refresh_html = f"""
<script>
    setTimeout(function() {{
        location.reload();
    }}, {AUTO_REFRESH_INTERVAL * 1000});
</script>
"""
st.components.v1.html(refresh_html, height=0)
