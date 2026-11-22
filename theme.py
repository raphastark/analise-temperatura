"""
Tema visual compartilhado — Viação Novacap
==========================================

CÓPIA de `theme.py` do repositório raphastark/monitoramento-frota, junto com
`assets/novacap_theme.css`, os dois PNG da marca e `.streamlit/config.toml`.
Para os painéis ficarem iguais, mude o tema lá e copie de novo para cá; aqui
só este aviso difere do original. As funções de selo da Jaé e do GPS e a tabela de
detalhamento não são usadas neste app; ficam para a cópia continuar idêntica.

Camada de apresentação única do dashboard: tokens de cor por modo
(claro/escuro), folha de estilos (assets/novacap_theme.css), cabeçalho de
marca com os selos de status das fontes, cards de indicador e o estilo da
tabela de detalhamento. Nenhuma regra de negócio vive aqui: as funções só
traduzem em aparência os dados e as flags de saúde já calculados em
`dados.py` e `app.py`.

Uso:
    import streamlit as st
    from theme import aplicar_tema, renderizar_header

    st.set_page_config(...)
    aplicar_tema()
    renderizar_header(titulo="Monitoramento de Frota",
                      subtitulo="Atualização automática a cada 2 min · Brasília",
                      selos=[...])
"""

from __future__ import annotations

import base64
from functools import lru_cache
from html import escape
from pathlib import Path

import pandas as pd
import streamlit as st

ASSETS_DIR = Path(__file__).parent / "assets"
CSS_PATH = ASSETS_DIR / "novacap_theme.css"
LOGO_BONECO_PATH = ASSETS_DIR / "novacap-boneco-branco.png"
LOGO_LETRAS_PATH = ASSETS_DIR / "novacap-letras-branco.png"

# ============================================
# DESIGN TOKENS
# ============================================
# Cores semânticas, iguais nos dois modos. O laranja é exclusivo da marca
# (logo e fio do cabeçalho): nunca usar para alerta, botão ou dado.
COR_MARCA = "#E87A3E"
COR_CRITICA = "#F05A5A"
COR_ATENCAO = "#E8A33D"
COR_OK = "#58D19B"
COR_INFO = "#7C93C3"
COR_INFO_ZERO = "#56607A"
COR_DESABILITADA = "#8E98A9"

# Superfícies e textos por modo. O cabeçalho é #293046 nos dois modos.
TOKENS_MODO = {
    "dark": {
        "bg": "#0F141C",
        "surface": "#171D28",
        "border": "#2A3446",
        "control-border": "#3A4459",
        "text": "#ECEEF2",
        "text-2": "#C3C9D5",
        "text-3": "#B7BFCC",
        "muted": "#8E98A9",
        "kpi-value": "#ECEEF2",
        "zebra": "rgba(255, 255, 255, 0.025)",
        # Texto colorido (tabelas): as cores semânticas já têm contraste
        # >= 5:1 sobre as superfícies escuras.
        "critical-text": COR_CRITICA,
        "warning-text": COR_ATENCAO,
        "ok-text": COR_OK,
    },
    "light": {
        "bg": "#F3F4F7",
        "surface": "#FFFFFF",
        "border": "#DDE1E8",
        "control-border": "#C9CED8",
        "text": "#1A1D24",
        "text-2": "#3A3E48",
        "text-3": "#4A4F5C",
        "muted": "#6B7385",
        "kpi-value": "#2B3245",
        "zebra": "rgba(26, 29, 36, 0.025)",
        # Sobre branco as cores semânticas ficam abaixo de 4,5:1 (texto
        # pequeno); o texto usa variantes escuras. Pontos e contagens grandes
        # mantêm as cores semânticas.
        "critical-text": "#C2302F",
        "warning-text": "#9A5B00",
        "ok-text": "#1A7F50",
    },
}

TOKENS_FIXOS = {
    "header-bg": "#293046",
    "header-divider": "#46506A",
    "header-text": "#ECEEF2",
    "header-text-2": "#C3C9D5",
    "brand": COR_MARCA,
    "critical": COR_CRITICA,
    "warning": COR_ATENCAO,
    "ok": COR_OK,
    "info": COR_INFO,
    "info-zero": COR_INFO_ZERO,
    "disabled": COR_DESABILITADA,
    "critical-tint": "rgba(240, 90, 90, 0.05)",
    "critical-row": "rgba(240, 90, 90, 0.08)",
}

# Estados exibidos nos selos do cabeçalho.
ESTADO_OPERACIONAL = "operacional"
ESTADO_DEGRADADO = "degradado"
ESTADO_DEFASADO = "defasado"
ESTADO_INDISPONIVEL = "indisponivel"
ESTADO_DESABILITADA = "desabilitada"

_ROTULO_ESTADO = {
    ESTADO_OPERACIONAL: "Operacional",
    ESTADO_DEGRADADO: "Degradado",
    ESTADO_DEFASADO: "Defasado",
    ESTADO_INDISPONIVEL: "Indisponível",
    ESTADO_DESABILITADA: "Desabilitada",
}
_COR_ESTADO = {
    ESTADO_OPERACIONAL: COR_OK,
    ESTADO_DEGRADADO: COR_ATENCAO,
    ESTADO_DEFASADO: COR_ATENCAO,
    ESTADO_INDISPONIVEL: COR_CRITICA,
    ESTADO_DESABILITADA: COR_DESABILITADA,
}


# ============================================
# TEMA
# ============================================

@lru_cache(maxsize=1)
def _carregar_css() -> str:
    """Lê o CSS do disco uma única vez por execução do app."""
    return CSS_PATH.read_text(encoding="utf-8")


@lru_cache(maxsize=4)
def _imagem_base64(caminho: Path) -> str:
    return base64.b64encode(caminho.read_bytes()).decode("ascii")


def modo_tema_atual() -> str:
    """'dark' ou 'light', conforme o tema ativo no navegador do usuário.

    O tipo vem de `st.context.theme` (inferido pelo Streamlit a partir do
    fundo). Em execução sem navegador (testes) ou se a informação ainda não
    chegou, assume o modo escuro, que é o padrão de referência do design.
    """
    try:
        tipo = st.context.theme.type
    except Exception:
        tipo = None
    return "light" if tipo == "light" else "dark"


def _css_variaveis(modo: str) -> str:
    tokens = {**TOKENS_MODO.get(modo, TOKENS_MODO["dark"]), **TOKENS_FIXOS}
    corpo = "".join(f"--nv-{nome}:{valor};" for nome, valor in tokens.items())
    return f":root{{{corpo}}}"


def aplicar_tema() -> None:
    """Injeta tokens do modo ativo e a folha de estilos Novacap.

    Deve ser chamada logo após `st.set_page_config(...)` em cada página.
    """
    st.markdown(
        # O CSS vem primeiro: o @import das fontes só vale antes de qualquer
        # regra, e os tokens :root não dependem da ordem.
        f"<style>{_carregar_css()}\n{_css_variaveis(modo_tema_atual())}</style>",
        unsafe_allow_html=True,
    )


# ============================================
# CABEÇALHO
# ============================================

def formatar_horario_selo(datahora) -> str:
    """Horário curto do selo (dd/mm HH:MM:SS) ou travessão sem dado."""
    if datahora is None:
        return "—"
    try:
        return datahora.strftime("%d/%m %H:%M:%S")
    except (AttributeError, ValueError):
        return "—"


def estado_selo_jae(resposta_api: dict, saude_api: dict | None) -> str:
    """Traduz a saúde já calculada da Jaé em estado de selo."""
    if not resposta_api.get("ok") or not saude_api:
        return ESTADO_INDISPONIVEL
    if saude_api.get("saudavel"):
        return ESTADO_OPERACIONAL
    alerta = saude_api.get("alerta")
    if alerta == "api_fora":
        return ESTADO_INDISPONIVEL
    if alerta == "dados_defasados":
        return ESTADO_DEFASADO
    return ESTADO_DEGRADADO


def estado_selo_gps(operacao_sppo: dict) -> str:
    """Traduz o resultado já calculado do GPS/SMTR em estado de selo.

    Com dados selecionados confiáveis (`ok`), a integração é operacional,
    mesmo com um fornecedor em falha ou posições individuais descartadas:
    essas limitações aparecem em aviso próprio, sem rebaixar a integração
    inteira (regra da v7.8).
    """
    if operacao_sppo.get("desabilitada"):
        return ESTADO_DESABILITADA
    if not operacao_sppo.get("ok"):
        if operacao_sppo.get("alerta") == "dados_defasados":
            return ESTADO_DEFASADO
        return ESTADO_INDISPONIVEL
    if operacao_sppo.get("origem_gps") == "zxbus":
        # SMTR fora e a reserva ZxBus classificando: funciona, com limitações.
        return ESTADO_DEGRADADO
    return ESTADO_OPERACIONAL


def html_selo_status(fonte: str, estado: str, horario: str) -> str:
    cor = _COR_ESTADO.get(estado, COR_DESABILITADA)
    rotulo = _ROTULO_ESTADO.get(estado, estado)
    return (
        '<div class="nv-selo">'
        f'<span class="nv-dot" style="background:{cor}"></span>'
        '<span class="nv-selo-texto">'
        f'<span class="nv-selo-l1">{escape(fonte)} · {escape(rotulo)}</span>'
        f'<span class="nv-selo-l2">{escape(horario)}</span>'
        '</span></div>'
    )


def renderizar_header(
    titulo: str,
    subtitulo: str | None = None,
    selos: list[tuple[str, str, str]] | None = None,
) -> None:
    """Cabeçalho de marca Novacap.

    Args:
        titulo: título da página.
        subtitulo: linha auxiliar (opcional).
        selos: lista de (fonte, estado, horário) exibida à direita; o estado
            é uma das constantes ESTADO_*.
    """
    boneco = _imagem_base64(LOGO_BONECO_PATH)
    letras = _imagem_base64(LOGO_LETRAS_PATH)
    sub_html = f'<span class="nv-sub">{escape(subtitulo)}</span>' if subtitulo else ""
    selos_html = "".join(html_selo_status(*selo) for selo in (selos or []))
    st.markdown(
        '<div class="nv-header">'
        '<div class="nv-brand">'
        f'<img class="nv-boneco" src="data:image/png;base64,{boneco}" alt="">'
        f'<img class="nv-letras" src="data:image/png;base64,{letras}" alt="Novacap">'
        '</div>'
        '<span class="nv-header-divider"></span>'
        '<div class="nv-header-titulos">'
        f'<span class="nv-title">{escape(titulo)}</span>'
        f'{sub_html}'
        '</div>'
        f'<div class="nv-header-status">{selos_html}</div>'
        '</div>',
        unsafe_allow_html=True,
    )


# ============================================
# INDICADORES
# ============================================

def html_indicador(
    rotulo: str,
    valor,
    total=None,
    legenda: str | None = None,
) -> str:
    """Card de indicador neutro: sem seta, sem delta e sem cor de alerta."""
    total_html = (
        f'<span class="nv-kpi-total">/{escape(str(total))}</span>'
        if total is not None else ""
    )
    valor_txt = str(valor)
    classe_valor = "nv-kpi-value nv-kpi-vazio" if valor_txt == "—" else "nv-kpi-value"
    legenda_html = (
        f'<span class="nv-kpi-legend">{escape(legenda)}</span>' if legenda else ""
    )
    return (
        '<div class="nv-kpi">'
        f'<span class="nv-kpi-label">{escape(rotulo)}</span>'
        f'<span class="{classe_valor}">{escape(valor_txt)}{total_html}</span>'
        f'{legenda_html}'
        '</div>'
    )


# ============================================
# TABELA DE DETALHAMENTO
# ============================================

_STATUS_EXIBICAO = {
    "🟢 Online": ("● Online", "ok-text"),
    "🔴 Offline": ("● Offline", "warning-text"),
}


def _cor_texto(token: str, modo: str | None = None) -> str:
    """Cor de texto semântica com contraste adequado ao modo ativo."""
    tokens = TOKENS_MODO.get(modo or modo_tema_atual(), TOKENS_MODO["dark"])
    return tokens.get(token, COR_DESABILITADA)


def preparar_tabela_validadores(
    df: pd.DataFrame,
    colunas: dict,
    mapeamento: dict | None = None,
):
    """Monta a tabela de detalhamento com o visual Novacap.

    Mantém as colunas e a ordem atuais (`colunas`, vindas de
    COLUNAS_DETALHAMENTO_VALIDADORES) e só muda a apresentação: ponto de
    status colorido, temperatura alta em vermelho com a linha tingida e
    sensor sem leitura em âmbar. Usa as colunas já calculadas por
    `processar_dados` (`temp_alta`, `temp_plausivel`, `online`) e o
    mapeamento da planilha para saber qual validador tem sensor.

    Returns:
        (styler, column_config) prontos para `st.dataframe`.
    """
    mapeamento = mapeamento or {}
    modo = modo_tema_atual()
    cor_critica = _cor_texto("critical-text", modo)
    cor_atencao = _cor_texto("warning-text", modo)
    tabela = df[list(colunas)].rename(columns=colunas).reset_index(drop=True)
    base = df.reset_index(drop=True)

    temp_alta = base.get("temp_alta", pd.Series(False, index=base.index)).fillna(False).astype(bool)

    def _validador_com_sensor(row) -> bool:
        mapa = mapeamento.get(str(row.get("id_veiculo")))
        if not mapa:
            return False
        return str(row.get("id_validador")) == str(mapa.get("com_sensor"))

    if not base.empty:
        com_sensor = base.apply(_validador_com_sensor, axis=1).astype(bool)
        plausivel = base.get("temp_plausivel", pd.Series(False, index=base.index)).fillna(False).astype(bool)
        online = base.get("online", pd.Series(False, index=base.index)).fillna(False).astype(bool)
        sem_leitura = com_sensor & online & ~plausivel
    else:
        sem_leitura = pd.Series(False, index=base.index)

    tabela["_nv_temp_alta"] = temp_alta.values
    tabela["_nv_sem_leitura"] = sem_leitura.values

    if "Status" in tabela.columns:
        tabela["_nv_status_cor"] = tabela["Status"].map(
            lambda s: _cor_texto(_STATUS_EXIBICAO[s][1], modo)
            if s in _STATUS_EXIBICAO else COR_DESABILITADA
        )
        tabela["Status"] = tabela["Status"].map(
            lambda s: _STATUS_EXIBICAO.get(s, (f"● {s}" if s else "—", None))[0]
        )
    if "Temp." in tabela.columns:
        tabela["Temp."] = tabela["Temp."].map(
            lambda t: str(t).replace("🌡️", "").strip() if pd.notna(t) else "—"
        )

    # Zebrado discreto por veículo (alterna a cada troca de veículo, como antes).
    grupos = (tabela["Veículo"] != tabela["Veículo"].shift()).cumsum() if "Veículo" in tabela else None

    visiveis = [c for c in tabela.columns if not c.startswith("_nv_") and c != "temperatura_num"]

    def _estilo_linha(row):
        estilos = []
        alta = bool(row.get("_nv_temp_alta", False))
        zebra = grupos is not None and int(grupos.loc[row.name]) % 2 == 0
        fundo = (
            "background-color: rgba(240, 90, 90, 0.08);" if alta
            else ("background-color: rgba(127, 127, 127, 0.05);" if zebra else "")
        )
        for coluna in row.index:
            estilo = fundo
            if coluna == "Temp.":
                if alta:
                    estilo += f" color: {cor_critica}; font-weight: 600;"
                elif bool(row.get("_nv_sem_leitura", False)):
                    estilo += f" color: {cor_atencao};"
            elif coluna == "Status":
                cor = row.get("_nv_status_cor")
                if cor:
                    estilo += f" color: {cor};"
            estilos.append(estilo)
        return estilos

    styler = tabela.style.apply(_estilo_linha, axis=1)
    column_config = {c: None for c in tabela.columns if c not in visiveis}
    return styler, column_config
