import requests
import pandas as pd
import streamlit as st
import plotly.express as px

from datetime import datetime, timedelta


def get_tracking():
    date_time = datetime.fromordinal(selected_date.toordinal())
    start_time = date_time + timedelta(hours=3)
    end_time = start_time + timedelta(days=1)
    url = "https://tracking.mobilidade.rio/api/v1/validador"
    headers = {
        "Content-Type": "application/json",
    }
    params = {
        "start_time": start_time.strftime("%Y-%m-%d %H:%M:%S"),
        "end_time": end_time.strftime("%Y-%m-%d %H:%M:%S"),
        "id_validador": valitador,
        "limit": 1440,
    }
    r = requests.get(url, headers=headers, params=params)

    try:
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
        # grid (equivalente ao plt.grid(True))
        fig.update_xaxes(showgrid=True, tickformat="%H:%M")
        fig.update_yaxes(showgrid=True)

        st.session_state["line_chart"] = fig


def get_data_and_plot():
    if valitador:
        st.session_state["validator_informed"] = True
    else:
        st.session_state["validator_informed"] = False
        return

    if selected_date:
        st.session_state["date_informed"] = True
    else:
        st.session_state["date_informed"] = False
        return

    st.session_state["show_datetime"] = True
    st.session_state["button_already_clicked"] = True

    get_tracking()
    plot_histogram()
    plot_line()


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

# validators = pd.read_csv("validadores.csv")["numero_serie_equipamento"].tolist()

# valitador = st.selectbox("Identificação do validador", options=validators)
valitador = st.text_input("Identificação do validador", value="")
if not st.session_state["validator_informed"]:
    st.write("Informe um identificador de validador")

selected_date = st.date_input("Data", value="today", format="DD/MM/YYYY")
if not st.session_state["date_informed"]:
    st.write("Informe uma data de busca")

button = st.button("Buscar", on_click=get_data_and_plot)


if st.session_state["show_datetime"]:
    st.write(f"Hora da busca:")
    st.write(datetime.now().strftime("%d/%m/%Y %H:%M:%S"))

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
