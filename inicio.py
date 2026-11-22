import streamlit as st

from theme import renderizar_header
from ui import configurar_pagina

configurar_pagina("Temperatura da frota · Novacap")

renderizar_header(
    titulo="Temperatura da frota",
    subtitulo="Sensores dos validadores · horário de Brasília",
)

col_frota, col_validador = st.columns(2, gap="small")

with col_frota:
    with st.container(border=True):
        st.markdown("**Frota agora**")
        st.caption(
            "Última leitura do validador com sensor de cada veículo, "
            "atualizada a cada 1 min."
        )
        st.page_link("paginas/1_Dashboard_Frota.py", label="Abrir a frota")

with col_validador:
    with st.container(border=True):
        st.markdown("**Histórico do validador**")
        st.caption(
            "Todas as leituras de um validador num dia: gráfico ao longo do "
            "tempo, distribuição e tabela."
        )
        st.page_link("paginas/2_Validador_Individual.py", label="Abrir o histórico")

st.caption(
    "Critério usado aqui: até 24 °C. A Resolução SMTR 3857 também considera "
    "regular a leitura 8 °C ou mais abaixo da temperatura externa do INMET, "
    "que este app não consulta."
)
