"""Peças de interface comuns às páginas deste app, sobre o tema Novacap (theme.py)."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import streamlit as st

from theme import COR_INFO, TOKENS_MODO, aplicar_tema, modo_tema_atual

FAVICON = str(Path(__file__).parent / "assets" / "novacap-favicon.png")
FUSO_BRASILIA = timezone(timedelta(hours=-3))
LIMITE_TEMPERATURA = 24.0  # Resolução SMTR 3857: regular até 24 °C (sem a tolerância externa)
# Faixa em que a leitura do sensor é tratada como temperatura real (a mesma do
# painel de monitoramento da frota). Fora dela, como 0, é falha do sensor.
TEMP_MIN_PLAUSIVEL = 8.0
TEMP_MAX_PLAUSIVEL = 45.0

# O novacap_theme.css reduz o respiro do topo para 1,5rem. No painel da frota,
# o componente invisível do st_autorefresh, primeiro elemento da página,
# empurra o cabeçalho 40px para baixo da barra fixa do Streamlit (60px). Aqui
# a atualização é por fragmento, sem esse componente, e o cabeçalho ficava sob
# a barra. 50px (1,5rem + 40px, menos os 14px de espaçamento que este próprio
# bloco de estilo ocupa) põem o cabeçalho na mesma altura do painel: 78px.
_CSS_TOPO = "<style>.block-container{padding-top:50px !important;}</style>"


def configurar_pagina(titulo_aba: str, layout: str = "wide") -> None:
    """set_page_config com o favicon da Novacap e o tema; primeira chamada da página."""
    st.set_page_config(page_title=titulo_aba, page_icon=FAVICON, layout=layout)
    aplicar_tema()
    st.markdown(_CSS_TOPO, unsafe_allow_html=True)


def agora_brasilia() -> datetime:
    return datetime.now(FUSO_BRASILIA)


def formatar_temperatura(valor) -> str:
    """30,2 °C; vazio vira travessão."""
    if valor is None or pd.isna(valor):
        return "—"
    return f"{float(valor):.1f} °C".replace(".", ",")


def formatar_percentual(valor: float) -> str:
    return f"{valor:.1f}%".replace(".", ",")


def estilizar_grafico(fig, altura: int = 380):
    """Gráfico no padrão Novacap: fundo transparente, grade em borda, ticks em mono."""
    tokens = TOKENS_MODO[modo_tema_atual()]
    fig.update_layout(
        height=altura,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Barlow, system-ui, sans-serif", size=13, color=tokens["text-2"]),
        title=dict(font=dict(size=18, color=tokens["text"]), x=0, xanchor="left"),
        margin=dict(l=8, r=8, t=48, b=8),
        hoverlabel=dict(font_family="IBM Plex Mono, monospace"),
        showlegend=False,
        bargap=0.08,
    )
    eixo = dict(
        gridcolor=tokens["border"],
        zeroline=False,
        linecolor=tokens["border"],
        tickfont=dict(family="IBM Plex Mono, monospace", size=11, color=tokens["muted"]),
        title_font=dict(size=13, color=tokens["text-3"]),
    )
    fig.update_xaxes(**eixo)
    fig.update_yaxes(**eixo)
    return fig


def cor_dado() -> str:
    """Cor neutra das séries (azul de informação; o laranja é só da marca)."""
    return COR_INFO if modo_tema_atual() == "dark" else "#5B74A8"


def cor_texto(token: str) -> str:
    return TOKENS_MODO[modo_tema_atual()][token]
