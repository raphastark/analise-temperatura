import re

import requests
import pandas as pd
import streamlit as st
import plotly.express as px

from datetime import date, datetime, timedelta, timezone

FUSO_BRASILIA = timezone(timedelta(hours=-3))
# Número de série do validador (ex.: B35T020D00206579). Qualquer outro texto
# vindo da URL é ignorado, e a página abre vazia como antes.
PADRAO_VALIDADOR = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def hoje_brasilia() -> date:
    """Dia atual em Brasília (o servidor roda em UTC)."""
    return datetime.now(FUSO_BRASILIA).date()


def ler_parametros_url():
    """(validador, data) de ?validador=...&data=AAAA-MM-DD, ou None.

    Usado pelo link "ver curva" do painel de monitoramento da frota. Sem data
    válida, vale o dia atual em Brasília.
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


def plot_histogram():
    if not st.session_state["dataframe"].empty:
        df = st.session_state["dataframe"]
        fig = px.histogram(
            df,
            x="temperatura",
            title="Distribuição da Temperatura",
            nbins=20,
        )
        fig.update_layout(xaxis_title="Temperatura (ºC)", yaxis_title="Frequência")
        fig.update_layout(width=1200, height=600)
        fig.update_traces(marker_line_color="black", marker_line_width=1.5)
        st.session_state["histogram"] = fig


def plot_line():
    if not st.session_state["dataframe"].empty:
        df = st.session_state["dataframe"]
        fig = px.line(
            df,
            x="timestamp_gps",
            y="temperatura",
            title="Temperatura ao Longo do Tempo",
        )

        fig.update_layout(width=1200, height=600)
        fig.update_layout(xaxis_title="Tempo (HH:MM)", yaxis_title="Temperatura (ºC)")
        fig.update_xaxes(showgrid=True, tickformat="%H:%M")
        fig.update_yaxes(showgrid=True)

        st.session_state["line_chart"] = fig


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

    st.session_state["show_datetime"] = True
    st.session_state["button_already_clicked"] = True

    get_tracking(validador, data)
    plot_histogram()
    plot_line()

    # A URL passa a refletir a busca: dá para compartilhar o link desta curva.
    st.session_state["parametros_processados"] = (validador, data)
    st.query_params["validador"] = validador
    st.query_params["data"] = data.isoformat()


def buscar():
    get_data_and_plot(
        st.session_state.get("campo_validador"),
        st.session_state.get("campo_data"),
    )


st.set_page_config("Análise de temperatura dos veículos", page_icon="./favicon.ico")
st.title("Análise de temperatura dos veículos")

if "show_datetime" not in st.session_state:
    st.session_state["show_datetime"] = False

if "date_informed" not in st.session_state:
    st.session_state["date_informed"] = True

if "validator_informed" not in st.session_state:
    st.session_state["validator_informed"] = True

if "button_already_clicked" not in st.session_state:
    st.session_state["button_already_clicked"] = False

if "dataframe" not in st.session_state:
    st.session_state["dataframe"] = pd.DataFrame()

if "histogram" not in st.session_state:
    st.session_state["histogram"] = None

if "line_chart" not in st.session_state:
    st.session_state["line_chart"] = None

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

# validators = pd.read_csv("validadores.csv")["numero_serie_equipamento"].tolist()

# valitador = st.selectbox("Identificação do validador", options=validators)
st.text_input("Identificação do validador", key="campo_validador")
if not st.session_state["validator_informed"]:
    st.write("Informe um identificador de validador")

st.date_input("Data", key="campo_data", format="DD/MM/YYYY")
if not st.session_state["date_informed"]:
    st.write("Informe uma data de busca")

button = st.button("Buscar", on_click=buscar)

if buscar_pela_url:
    get_data_and_plot(*parametros_url)


if st.session_state["show_datetime"]:
    st.write("Hora da busca:")
    st.write(datetime.now(FUSO_BRASILIA).strftime("%d/%m/%Y %H:%M:%S"))

if not st.session_state["dataframe"].empty:
    st.dataframe(st.session_state["dataframe"])
else:
    st.session_state["histogram"] = None
    st.session_state["line_chart"] = None
    if st.session_state["button_already_clicked"]:
        st.write("Nenhum resultado encontrado")

if st.session_state["histogram"]:
    st.plotly_chart(st.session_state["histogram"])

if st.session_state["line_chart"]:
    st.plotly_chart(st.session_state["line_chart"])
