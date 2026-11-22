import re

import requests
import pandas as pd
import streamlit as st
import plotly.express as px

from datetime import date, datetime, timedelta

from theme import html_indicador, renderizar_header
from ui import (
    LIMITE_TEMPERATURA,
    TEMP_MAX_PLAUSIVEL,
    TEMP_MIN_PLAUSIVEL,
    agora_brasilia,
    configurar_pagina,
    cor_dado,
    cor_texto,
    estilizar_grafico,
    formatar_percentual,
    formatar_temperatura,
)

# Número de série do validador (ex.: B35T020D00206579). Qualquer outro texto
# vindo da URL é ignorado, e a página abre vazia como antes.
PADRAO_VALIDADOR = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def hoje_brasilia() -> date:
    """Dia atual em Brasília (o servidor roda em UTC)."""
    return agora_brasilia().date()


def ler_parametros_url():
    """(validador, data) de ?validador=...&data=AAAA-MM-DD, ou None.

    Usado pelo link "Ver histórico" do painel de monitoramento da frota. Sem
    data válida, vale o dia atual em Brasília.
    """
    validador = str(st.query_params.get("validador", "")).strip()
    if not PADRAO_VALIDADOR.match(validador):
        return None
    try:
        data = date.fromisoformat(str(st.query_params.get("data", "")).strip())
    except ValueError:
        data = hoje_brasilia()
    return validador, data


def get_tracking(validador, data):
    date_time = datetime.fromordinal(data.toordinal())
    start_time = date_time + timedelta(hours=3)
    end_time = start_time + timedelta(days=1)
    url = "https://tracking.mobilidade.rio/api/v1/validador"
    headers = {
        "Content-Type": "application/json",
    }
    params = {
        "start_time": start_time.strftime("%Y-%m-%d %H:%M:%S"),
        "end_time": end_time.strftime("%Y-%m-%d %H:%M:%S"),
        "id_validador": validador,
        "limit": 1440,
    }

    try:
        r = requests.get(url, headers=headers, params=params, timeout=60)
        df = pd.DataFrame(r.json())
        df["timestamp_gps"] = pd.to_datetime(df["timestamp_gps"])
        df["timestamp_gps"] = df["timestamp_gps"].dt.tz_localize("UTC")
        df["timestamp_gps"] = df["timestamp_gps"].dt.tz_convert("America/Sao_Paulo")
        st.session_state["dataframe"] = pd.DataFrame(df)
    except Exception:
        st.session_state["dataframe"] = pd.DataFrame()


def get_data_and_plot(validador, data):
    validador = str(validador or "").strip()
    if validador:
        st.session_state["validator_informed"] = True
    else:
        st.session_state["validator_informed"] = False
        return

    if data:
        st.session_state["date_informed"] = True
    else:
        st.session_state["date_informed"] = False
        return

    st.session_state["consultado_em"] = agora_brasilia()
    st.session_state["button_already_clicked"] = True

    get_tracking(validador, data)

    # A URL passa a refletir a busca: dá para compartilhar o link deste histórico.
    st.session_state["parametros_processados"] = (validador, data)
    st.query_params["validador"] = validador
    st.query_params["data"] = data.isoformat()


def buscar():
    get_data_and_plot(
        st.session_state.get("campo_validador"),
        st.session_state.get("campo_data"),
    )


def leituras_plausiveis(df: pd.DataFrame) -> pd.DataFrame:
    temperatura = pd.to_numeric(df["temperatura"], errors="coerce")
    return df[temperatura.between(TEMP_MIN_PLAUSIVEL, TEMP_MAX_PLAUSIVEL)]


def render_kpis(df: pd.DataFrame):
    """Última leitura, máxima do dia e leituras acima de 24 °C, neutros."""
    ordenado = df.sort_values("timestamp_gps")
    ultima = ordenado.iloc[-1]
    validas = leituras_plausiveis(ordenado)
    estado = ultima.get("estado_equipamento")
    estado_txt = f" · {estado}" if isinstance(estado, str) and estado else ""

    col1, col2, col3 = st.columns(3, gap="small")
    with col1:
        st.markdown(
            html_indicador(
                "Última leitura",
                formatar_temperatura(ultima["temperatura"]),
                None,
                f"às {ultima['timestamp_gps'].strftime('%H:%M')}{estado_txt}",
            ),
            unsafe_allow_html=True,
        )
    with col2:
        if validas.empty:
            st.markdown(
                html_indicador("Máxima do dia", "—", None, "nenhuma leitura entre 8 e 45 °C"),
                unsafe_allow_html=True,
            )
        else:
            pico = validas.loc[pd.to_numeric(validas["temperatura"]).idxmax()]
            st.markdown(
                html_indicador(
                    "Máxima do dia",
                    formatar_temperatura(pico["temperatura"]),
                    None,
                    f"às {pico['timestamp_gps'].strftime('%H:%M')}",
                ),
                unsafe_allow_html=True,
            )
    with col3:
        acima = int((pd.to_numeric(validas["temperatura"]) > LIMITE_TEMPERATURA).sum())
        total_validas = len(validas)
        invalidas = len(ordenado) - total_validas
        legenda = (
            f"{formatar_percentual(acima / total_validas * 100)} das leituras válidas"
            if total_validas else "sem leituras válidas"
        )
        if invalidas:
            legenda += f" · {invalidas} fora de 8–45 °C"
        st.markdown(
            html_indicador("Acima de 24 °C", acima, total_validas or None, legenda),
            unsafe_allow_html=True,
        )


def render_graficos(df: pd.DataFrame):
    ordenado = df.sort_values("timestamp_gps")
    linha = px.line(
        ordenado,
        x="timestamp_gps",
        y="temperatura",
        title="Temperatura ao longo do dia",
    )
    linha.update_traces(
        line=dict(color=cor_dado(), width=2),
        hovertemplate="%{x|%H:%M:%S}<br>%{y:.1f} °C<extra></extra>",
    )
    linha.add_hline(
        y=LIMITE_TEMPERATURA,
        line=dict(color=cor_texto("muted"), width=1, dash="dash"),
        annotation_text="24 °C",
        annotation_position="bottom right",
        annotation_font=dict(family="IBM Plex Mono, monospace", size=11, color=cor_texto("muted")),
    )
    linha.update_xaxes(title_text="Horário", tickformat="%H:%M")
    linha.update_yaxes(title_text="Temperatura (°C)")
    st.plotly_chart(estilizar_grafico(linha, altura=420), width="stretch")

    histograma = px.histogram(
        ordenado,
        x="temperatura",
        nbins=20,
        title="Distribuição das leituras",
    )
    histograma.update_traces(
        marker=dict(color=cor_dado(), line=dict(width=0)),
        hovertemplate="%{x} °C<br>%{y} leituras<extra></extra>",
    )
    histograma.update_xaxes(title_text="Temperatura (°C)")
    histograma.update_yaxes(title_text="Leituras")
    st.plotly_chart(estilizar_grafico(histograma, altura=320), width="stretch")


def render_tabela(df: pd.DataFrame):
    tabela = pd.DataFrame({
        "Validador": df["id_validador"] if "id_validador" in df else "—",
        "Horário": df["timestamp_gps"].dt.strftime("%d/%m/%Y %H:%M:%S"),
        "Temperatura": df["temperatura"].map(formatar_temperatura),
    })
    if "estado_equipamento" in df:
        tabela["Estado"] = df["estado_equipamento"].fillna("—")
    temperatura = pd.to_numeric(df["temperatura"], errors="coerce")
    plausivel = temperatura.between(TEMP_MIN_PLAUSIVEL, TEMP_MAX_PLAUSIVEL)
    acima = plausivel & (temperatura > LIMITE_TEMPERATURA)

    def _estilo(coluna):
        if coluna.name != "Temperatura":
            return [""] * len(coluna)
        return [
            f"color: {cor_texto('warning-text')}; font-weight: 600;" if a
            else ("" if p else f"color: {cor_texto('muted')};")
            for a, p in zip(acima, plausivel)
        ]

    st.markdown("**Leituras**")
    st.dataframe(
        tabela.reset_index(drop=True).style.apply(_estilo, axis=0),
        width="stretch",
        hide_index=True,
        height=420,
    )


configurar_pagina("Histórico do validador · Temperatura · Novacap")

if "date_informed" not in st.session_state:
    st.session_state["date_informed"] = True

if "validator_informed" not in st.session_state:
    st.session_state["validator_informed"] = True

if "button_already_clicked" not in st.session_state:
    st.session_state["button_already_clicked"] = False

if "dataframe" not in st.session_state:
    st.session_state["dataframe"] = pd.DataFrame()

if "campo_validador" not in st.session_state:
    st.session_state["campo_validador"] = ""

if "campo_data" not in st.session_state:
    st.session_state["campo_data"] = hoje_brasilia()

# Link vindo do painel da frota (?validador=...&data=...): preenche os campos
# e busca sozinho, uma vez por combinação. Sem parâmetros, nada muda.
parametros_url = ler_parametros_url()
buscar_pela_url = (
    parametros_url is not None
    and parametros_url != st.session_state.get("parametros_processados")
)
if buscar_pela_url:
    st.session_state["campo_validador"], st.session_state["campo_data"] = parametros_url

renderizar_header(
    titulo="Histórico do validador",
    subtitulo="Todas as leituras de um dia · horário de Brasília",
)

# Formulário: o Enter no campo do validador envia a busca, como o botão.
# Fora de um formulário, o Enter só confirmava o texto e recarregava a página.
with st.form("busca_validador", border=False, enter_to_submit=True):
    col_validador, col_data, col_botao = st.columns(
        [3, 2, 1], gap="small", vertical_alignment="bottom"
    )
    with col_validador:
        st.text_input(
            "Número de série do validador",
            key="campo_validador",
            placeholder="B35T020D00206579",
        )
    with col_data:
        st.date_input("Data", key="campo_data", format="DD/MM/YYYY")
    with col_botao:
        st.form_submit_button("Buscar", on_click=buscar, width="stretch")

if not st.session_state["validator_informed"]:
    st.warning("Informe o número de série do validador.")
if not st.session_state["date_informed"]:
    st.warning("Informe a data da busca.")

if buscar_pela_url:
    get_data_and_plot(*parametros_url)

df_leituras = st.session_state["dataframe"]
if not df_leituras.empty:
    consultado = st.session_state.get("consultado_em")
    if consultado:
        st.caption(f"Consultado em {consultado.strftime('%d/%m/%Y %H:%M:%S')}")
    render_kpis(df_leituras)
    render_graficos(df_leituras)
    render_tabela(df_leituras)
elif st.session_state["button_already_clicked"]:
    st.info(
        "**Nenhuma leitura encontrada.** Confira o número de série e a data; "
        "a API de rastreamento pode estar fora do ar."
    )
