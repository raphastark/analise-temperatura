import requests
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Optional
from urllib.parse import urlencode

from theme import (
    COR_ATENCAO,
    COR_DESABILITADA,
    COR_OK,
    ESTADO_INDISPONIVEL,
    ESTADO_OPERACIONAL,
    html_indicador,
    renderizar_header,
)
from ui import (
    LIMITE_TEMPERATURA,
    agora_brasilia,
    configurar_pagina,
    cor_texto,
    formatar_percentual,
    formatar_temperatura,
)

configurar_pagina("Frota agora · Temperatura · Novacap")

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


# Situação da última leitura: (rótulo, cor do ponto, token da cor do texto).
SITUACOES = {
    "ok": ("Até 24 °C", COR_OK, "ok-text"),
    "acima": ("Acima de 24 °C", COR_ATENCAO, "warning-text"),
    "sem_sinal": ("Sem sinal", COR_DESABILITADA, "muted"),
}
FILTROS = ["Todos", "Acima de 24 °C", "Sem sinal"]


def situacao(temp: Optional[float]) -> str:
    """Situação segundo o limite de 24 °C da Resolução SMTR 3857."""
    if temp is None or pd.isna(temp):
        return "sem_sinal"
    return "ok" if temp <= LIMITE_TEMPERATURA else "acima"


def link_historico(validador: str, dia) -> str:
    """Página do histórico deste app, já com o validador e o dia."""
    return "./Validador_Individual?" + urlencode(
        {"validador": validador, "data": dia.isoformat()}
    )


def render_kpis(fleet_data: pd.DataFrame):
    """Três indicadores neutros: a cor fica na tabela, não no card."""
    total = len(fleet_data)
    com_sinal = int(fleet_data["temperatura"].notna().sum())
    sem_sinal = total - com_sinal
    fora_norma = int((fleet_data["situacao"] == "acima").sum())
    conformidade = (com_sinal - fora_norma) / total * 100 if total > 0 else 0

    col1, col2, col3 = st.columns(3, gap="small")
    with col1:
        st.markdown(
            html_indicador(
                "Acima de 24 °C", fora_norma, com_sinal,
                "entre os veículos com sinal",
            ),
            unsafe_allow_html=True,
        )
    with col2:
        st.markdown(
            html_indicador(
                "Com sinal", com_sinal, total,
                f"{sem_sinal} sem leitura hoje",
            ),
            unsafe_allow_html=True,
        )
    with col3:
        st.markdown(
            html_indicador(
                "Conformidade", formatar_percentual(conformidade), None,
                "veículos até 24 °C, sobre a frota toda",
            ),
            unsafe_allow_html=True,
        )


def render_fleet_table(fleet_data: pd.DataFrame, filter_option: str):
    """Tabela da frota: ponto + rótulo na situação, cor só no dado."""
    if filter_option == "Acima de 24 °C":
        filtered = fleet_data[fleet_data["situacao"] == "acima"]
    elif filter_option == "Sem sinal":
        filtered = fleet_data[fleet_data["situacao"] == "sem_sinal"]
    else:
        filtered = fleet_data

    display_df = filtered.sort_values("Nº Ordem").reset_index(drop=True)
    hoje = agora_brasilia().date()
    tabela = pd.DataFrame({
        "Ônibus": display_df["Nº Ordem"].astype(str),
        "Validador": display_df["validador_id"],
        # Número, para a coluna ordenar como número; "30,2 °C" só na exibição.
        "Temperatura": pd.to_numeric(display_df["temperatura"], errors="coerce"),
        "Situação": display_df["situacao"].map(lambda s: f"● {SITUACOES[s][0]}"),
        "Última leitura": display_df["timestamp"].map(
            lambda x: x.strftime("%H:%M") if pd.notna(x) else "—"
        ),
        "Histórico": display_df["validador_id"].map(lambda v: link_historico(v, hoje)),
    })
    cores = display_df["situacao"].map(lambda s: cor_texto(SITUACOES[s][2]))

    def _estilo(coluna):
        if coluna.name == "Situação":
            return [f"color: {cor};" for cor in cores]
        if coluna.name == "Temperatura":
            return [
                f"color: {cor}; font-weight: 600;" if s == "acima" else ""
                for cor, s in zip(cores, display_df["situacao"])
            ]
        if coluna.name == "Última leitura":
            return [f"color: {cor_texto('muted')};" if t == "—" else "" for t in coluna]
        return [""] * len(coluna)

    st.dataframe(
        tabela.style.apply(_estilo, axis=0).format(
            formatar_temperatura, subset=["Temperatura"]
        ),
        width="stretch",
        hide_index=True,
        height=600,
        column_config={
            "Histórico": st.column_config.LinkColumn(
                "Histórico",
                display_text="Ver histórico",
                help="Leituras de hoje deste validador",
            ),
        },
    )


# =============================================================================
# MAIN
# =============================================================================

@st.fragment(run_every=AUTO_REFRESH_INTERVAL)
def painel_frota():
    """Página inteira; o fragmento se refaz sozinho a cada AUTO_REFRESH_INTERVAL s."""
    fleet_mapping = get_fleet_mapping()

    if fleet_mapping.empty:
        renderizar_header(titulo="Frota agora", subtitulo="Temperatura nos validadores com sensor")
        st.error(
            "**Mapeamento da frota indisponível.** A planilha de validadores "
            "não respondeu; tente de novo em alguns minutos."
        )
        return

    validators = fleet_mapping["validador_com_sensor"].tolist()

    with st.spinner("Buscando dados dos validadores..."):
        validator_results = fetch_all_validators(validators)

    fleet_data = []
    for _, row in fleet_mapping.iterrows():
        validator_id = row["validador_com_sensor"]
        data = validator_results.get(validator_id)
        temp = data["temperatura"] if data else None
        fleet_data.append({
            "Nº Ordem": row["Nº Ordem"],
            "validador_id": validator_id,
            "temperatura": temp,
            "timestamp": data["timestamp"] if data else None,
            "situacao": situacao(temp),
        })
    fleet_df = pd.DataFrame(fleet_data)

    agora = agora_brasilia()
    com_sinal = int(fleet_df["temperatura"].notna().sum())
    renderizar_header(
        titulo="Frota agora",
        subtitulo=f"Atualização automática a cada {AUTO_REFRESH_INTERVAL // 60} min · Brasília",
        selos=[(
            "Rastreamento SMTR",
            ESTADO_OPERACIONAL if com_sinal else ESTADO_INDISPONIVEL,
            agora.strftime("%d/%m %H:%M:%S"),
        )],
    )

    render_kpis(fleet_df)

    contagens = {
        "Todos": len(fleet_df),
        "Acima de 24 °C": int((fleet_df["situacao"] == "acima").sum()),
        "Sem sinal": int((fleet_df["situacao"] == "sem_sinal").sum()),
    }
    filter_option = st.segmented_control(
        "Mostrar",
        FILTROS,
        default="Todos",
        format_func=lambda opcao: f"{opcao} · {contagens[opcao]}",
        key="filtro_frota",
        label_visibility="collapsed",
    ) or "Todos"

    render_fleet_table(fleet_df, filter_option)
    st.caption(
        "Limite de 24 °C da Resolução SMTR 3857, sem a tolerância pela "
        "temperatura externa do INMET."
    )


painel_frota()
