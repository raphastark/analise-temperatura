import streamlit as st

st.set_page_config(
    page_title="Monitoramento de Temperatura",
    page_icon="./favicon.ico",
    layout="wide"
)

st.title("🚌 Monitoramento de Temperatura da Frota")

st.markdown("""
### Bem-vindo ao sistema de monitoramento!

Selecione uma página no menu lateral:

- **Dashboard da Frota**: Visão geral de todos os 140 veículos com status de temperatura em tempo real
- **Validador Individual**: Consulta detalhada de um único validador (busca por data)

---

**Critério SMTR 3857**: Ar condicionado funcionando quando temperatura ≤ 24°C
""")

st.info("💡 O dashboard da frota atualiza automaticamente a cada 1 minuto.", icon="ℹ️")
