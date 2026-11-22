"""Entrada do app: navegação com os nomes das páginas, mantendo os endereços.

Os caminhos /Dashboard_Frota e /Validador_Individual são os de antes: o link
"Ver histórico" do painel de monitoramento da frota abre
/Validador_Individual?validador=...&data=....
"""
import streamlit as st

from ui import FAVICON

st.set_page_config(page_title="Temperatura da frota · Novacap", page_icon=FAVICON, layout="wide")

pagina = st.navigation([
    st.Page("inicio.py", title="Início", default=True),
    st.Page("pages/1_Dashboard_Frota.py", title="Frota agora", url_path="Dashboard_Frota"),
    st.Page("pages/2_Validador_Individual.py", title="Histórico do validador", url_path="Validador_Individual"),
])
pagina.run()
