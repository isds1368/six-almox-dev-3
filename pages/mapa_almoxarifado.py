"""
Mapa 2D dinâmico do Almoxarifado — com rastreabilidade de equipamentos
----------------------------------------------------------------------
Extensão do mapa original: além de desenhar as zonas físicas, este módulo
mantém um cadastro de EQUIPAMENTOS e registra automaticamente o "caminho"
de cada um pelo almoxarifado, conforme o ciclo de vida:

    1) RECEBIMENTO   -> equipamento entra no sistema (zona "Recebimento")
    2) ALOCADO       -> destinado a um setor (conforme relação já programada)
    3) QUEBRADO      -> marcado como quebrado -> vai automaticamente para
                        o setor "Planejamento" (não é escolhido manualmente)
    4) TROCADO        -> saída definitiva (baixa). O equipamento some do mapa
                        ativo, mas o histórico completo permanece salvo.

Cada transição de status gera um evento no histórico do equipamento
(status, setor, data/hora). O mapa desenha esse histórico como um caminho
(linha + marcadores numerados) ligando os setores por onde o equipamento
passou — essa é a base da rastreabilidade de vida útil pedida.

Como integrar no projeto:
    - Copie este arquivo para o seu repositório (ex: pages/mapa.py).
    - Ajuste ZONAS_PADRAO conforme os setores reais do seu almoxarifado
      (as zonas "recebimento" e "planejamento" são obrigatórias para o
      fluxo funcionar — pode renomear "nome", mas mantenha os "id").
    - Troque carregar_equipamentos()/salvar_equipamentos() pelas chamadas
      reais ao Supabase — os pontos de extensão estão marcados com TODO.
      Sugestão de tabela: equipamentos (id, nome, status, setor_atual)
      e equipamentos_historico (id, equipamento_id, status, setor, data).
"""

from datetime import datetime

import streamlit as st

st.set_page_config(page_title="Mapa do Almoxarifado", layout="wide")

# ============================================================
# 1. ESTRUTURA DE DADOS — fonte única de verdade do mapa
# ============================================================
# Cada zona é um retângulo no mapa principal.
# x, y, w, h estão em uma grade normalizada (0-500 largura x 0-380 altura),
# então não dependem do tamanho da tela.
#
# IMPORTANTE: os ids "recebimento" e "planejamento" são zonas especiais
# usadas pelo fluxo de rastreabilidade (ver seção 3). Não remova os ids,
# apenas ajuste posição/cor/nome se quiser.
ZONAS_PADRAO = [
    {"id": "setor_a",      "nome": "Setor A",          "x": 20,  "y": 20,  "w": 220, "h": 70,  "cor": "#e8192c"},
    {"id": "setor_b",      "nome": "Setor B",          "x": 250, "y": 20,  "w": 220, "h": 70,  "cor": "#e8192c"},
    {"id": "recebimento",  "nome": "Recebimento",      "x": 100, "y": 100, "w": 150, "h": 32,  "cor": "#3b3bc7"},
    {"id": "corredor",     "nome": "Corredor Central", "x": 40,  "y": 150, "w": 55,  "h": 90,  "cor": "#e8192c"},
    {"id": "planejamento", "nome": "Planejamento",     "x": 260, "y": 150, "w": 150, "h": 70,  "cor": "#e69b00"},
    {"id": "setor_c",      "nome": "Setor C",          "x": 20,  "y": 300, "w": 340, "h": 60,  "cor": "#e8192c"},
    {"id": "setor_d",      "nome": "Setor D",          "x": 370, "y": 300, "w": 60,  "h": 60,  "cor": "#a97155"},
]

# Linha de referência dentro do mapa (ex.: eixo de corredor, rota de acesso)
LINHA_GUIA_PADRAO = {"x1": 30, "y1": 185, "x2": 430, "y2": 185}

# Legenda lateral (categorias/cores de apoio, fora do contorno principal)
LEGENDA_PADRAO = [
    {"id": "leg1", "nome": "Ativo em setor", "cor": "#2ba84a"},
    {"id": "leg2", "nome": "Quebrado / Planejamento", "cor": "#e69b00"},
    {"id": "leg3", "nome": "Recebido (aguardando)", "cor": "#3b3bc7"},
]

# Cor de cada status — usada nos marcadores dos equipamentos e no caminho
COR_STATUS = {
    "recebido": "#3b3bc7",
    "alocado": "#2ba84a",
    "quebrado": "#e69b00",
    "trocado": "#7a7a7a",
}
LABEL_STATUS = {
    "recebido": "Recebido",
    "alocado": "Alocado",
    "quebrado": "Quebrado",
    "trocado": "Trocado (saída)",
}

# Setores "reais" que podem receber um equipamento alocado (exclui as zonas
# especiais recebimento/planejamento, que são preenchidas automaticamente
# pelo próprio fluxo).
def setores_alocaveis(zonas):
    return [z for z in zonas if z["id"] not in ("recebimento", "planejamento")]


# TODO: se quiser persistência entre sessões/usuários, substitua estas
# funções por leitura/escrita no Supabase.
#   carregar_equipamentos()  -> SELECT * FROM equipamentos (+ histórico)
#   salvar_equipamento(equip) -> UPSERT equipamentos + INSERT equipamentos_historico
def carregar_estado():
    if "zonas" not in st.session_state:
        st.session_state["zonas"] = [z.copy() for z in ZONAS_PADRAO]
    if "linha_guia" not in st.session_state:
        st.session_state["linha_guia"] = LINHA_GUIA_PADRAO.copy()
    if "legenda" not in st.session_state:
        st.session_state["legenda"] = [l.copy() for l in LEGENDA_PADRAO]
    if "equipamentos" not in st.session_state:
        st.session_state["equipamentos"] = []
    if "proximo_id" not in st.session_state:
        st.session_state["proximo_id"] = 1


def _agora():
    return datetime.now().strftime("%d/%m/%Y %H:%M")


def registrar_evento(equip, novo_status, setor_id):
    """Aplica uma transição de status/setor e grava o evento no histórico.
    Essa função é o único lugar que deveria, no futuro, também disparar o
    INSERT na tabela de histórico do Supabase."""
    equip["status"] = novo_status
    equip["setor_atual"] = setor_id
    equip["historico"].append({
        "status": novo_status,
        "setor": setor_id,
        "data": _agora(),
    })
    # TODO: persistir no Supabase aqui (UPDATE equipamentos + INSERT histórico)


def criar_equipamento(nome, tipo):
    novo_id = f"EQ{st.session_state['proximo_id']:04d}"
    st.session_state["proximo_id"] += 1
    equip = {
        "id": novo_id,
        "nome": nome,
        "tipo": tipo,
        "status": None,
        "setor_atual": None,
        "historico": [],
    }
    registrar_evento(equip, "recebido", "recebimento")
    st.session_state["equipamentos"].append(equip)
    return equip


def equipamentos_ativos():
    return [e for e in st.session_state["equipamentos"] if e["status"] != "trocado"]


def equipamentos_baixados():
    return [e for e in st.session_state["equipamentos"] if e["status"] == "trocado"]


# ============================================================
# 2. RENDERIZAÇÃO — gera o SVG a partir dos dados acima
# ============================================================
def _centro_zona(zonas_por_id, zona_id):
    z = zonas_por_id.get(zona_id)
    if not z:
        return None
    return z["x"] + z["w"] / 2, z["y"] + z["h"] / 2


def gerar_svg(zonas, linha_guia, legenda, equipamentos=None, caminho_de=None):
    """Desenha o mapa. Se `equipamentos` for passado, mostra um selo com a
    quantidade de itens ativos em cada zona. Se `caminho_de` for passado
    (um equipamento específico), desenha por cima o caminho percorrido por
    ele: linha ligando os centros das zonas do histórico, com marcadores
    numerados na ordem cronológica."""
    equipamentos = equipamentos or []
    largura_total, altura_total = 620, 380
    zonas_por_id = {z["id"]: z for z in zonas}

    partes = [
        f'<svg viewBox="0 0 {largura_total} {altura_total}" xmlns="http://www.w3.org/2000/svg" '
        f'style="background:#ffffff">'
    ]

    # Contorno principal do mapa
    partes.append(
        '<rect x="10" y="10" width="440" height="360" fill="none" stroke="black" stroke-width="4"/>'
    )

    # Zonas
    for z in zonas:
        partes.append(
            f'<rect x="{z["x"]}" y="{z["y"]}" width="{z["w"]}" height="{z["h"]}" '
            f'fill="{z["cor"]}" stroke="none"/>'
        )
        cx, cy = z["x"] + z["w"] / 2, z["y"] + z["h"] / 2
        partes.append(
            f'<text x="{cx}" y="{cy}" font-size="12" text-anchor="middle" '
            f'dominant-baseline="middle" fill="white" font-family="sans-serif">{z["nome"]}</text>'
        )

    # Selo com contagem de equipamentos ativos por zona
    if equipamentos:
        contagem = {}
        for eq in equipamentos:
            if eq["status"] == "trocado":
                continue
            contagem[eq["setor_atual"]] = contagem.get(eq["setor_atual"], 0) + 1
        for zona_id, qtd in contagem.items():
            z = zonas_por_id.get(zona_id)
            if not z:
                continue
            bx, by = z["x"] + z["w"] - 12, z["y"] - 2
            partes.append(f'<circle cx="{bx}" cy="{by}" r="11" fill="#111111" stroke="white" stroke-width="2"/>')
            partes.append(
                f'<text x="{bx}" y="{by}" font-size="11" text-anchor="middle" '
                f'dominant-baseline="middle" fill="white" font-family="sans-serif">{qtd}</text>'
            )

    # Linha guia
    lg = linha_guia
    partes.append(
        f'<line x1="{lg["x1"]}" y1="{lg["y1"]}" x2="{lg["x2"]}" y2="{lg["y2"]}" '
        f'stroke="black" stroke-width="3"/>'
    )

    # Painel de legenda (à direita, fora do contorno principal)
    painel_x = 480
    partes.append(
        f'<rect x="{painel_x}" y="90" width="110" height="220" fill="none" stroke="black" stroke-width="3"/>'
    )
    y_cursor = 110
    for item in legenda:
        partes.append(
            f'<rect x="{painel_x + 15}" y="{y_cursor}" width="24" height="24" fill="{item["cor"]}"/>'
        )
        partes.append(
            f'<text x="{painel_x + 45}" y="{y_cursor + 12}" font-size="10" '
            f'dominant-baseline="middle" font-family="sans-serif">{item["nome"]}</text>'
        )
        y_cursor += 60

    # Caminho de rastreabilidade de um equipamento específico
    if caminho_de is not None:
        historico = caminho_de["historico"]
        pontos = []
        for evento in historico:
            c = _centro_zona(zonas_por_id, evento["setor"])
            if c:
                pontos.append((c, evento))

        # Linha tracejada ligando os pontos em ordem
        for i in range(len(pontos) - 1):
            (x1, y1), _ = pontos[i]
            (x2, y2), _ = pontos[i + 1]
            partes.append(
                f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
                f'stroke="#111111" stroke-width="2.5" stroke-dasharray="6,4"/>'
            )

        # Marcadores numerados em cada parada
        for i, ((x, y), evento) in enumerate(pontos, start=1):
            cor = COR_STATUS.get(evento["status"], "#111111")
            partes.append(f'<circle cx="{x}" cy="{y}" r="13" fill="{cor}" stroke="black" stroke-width="1.5"/>')
            partes.append(
                f'<text x="{x}" y="{y}" font-size="12" text-anchor="middle" '
                f'dominant-baseline="middle" fill="white" font-family="sans-serif">{i}</text>'
            )

    partes.append("</svg>")
    return "".join(partes)


# ============================================================
# 3. INTERFACE — cadastro, transição de status e histórico
# ============================================================
def painel_recebimento():
    st.subheader("1. Registrar recebimento de equipamento")
    with st.form("form_recebimento", clear_on_submit=True):
        col1, col2 = st.columns(2)
        nome = col1.text_input("Nome / identificação do equipamento")
        tipo = col2.text_input("Tipo (opcional)")
        enviado = st.form_submit_button("Registrar recebimento")
        if enviado:
            if nome.strip():
                criar_equipamento(nome.strip(), tipo.strip())
                st.success(f"Equipamento '{nome}' recebido e registrado no mapa.")
            else:
                st.warning("Informe o nome do equipamento.")


def painel_transicoes():
    st.subheader("2. Avançar etapa de um equipamento")
    ativos = equipamentos_ativos()
    if not ativos:
        st.info("Nenhum equipamento ativo no momento. Registre um recebimento acima.")
        return

    opcoes = {f"{e['id']} — {e['nome']} ({LABEL_STATUS[e['status']]})": e["id"] for e in ativos}
    escolha = st.selectbox("Selecione o equipamento", list(opcoes.keys()))
    equip = next(e for e in ativos if e["id"] == opcoes[escolha])

    zonas = st.session_state["zonas"]
    zonas_por_id = {z["id"]: z for z in zonas}

    if equip["status"] == "recebido":
        destinos = setores_alocaveis(zonas)
        setor_escolhido = st.selectbox(
            "Destinar ao setor", [z["id"] for z in destinos],
            format_func=lambda zid: zonas_por_id[zid]["nome"],
        )
        if st.button("Confirmar alocação"):
            registrar_evento(equip, "alocado", setor_escolhido)
            st.success(f"{equip['nome']} alocado em {zonas_por_id[setor_escolhido]['nome']}.")
            st.rerun()

    elif equip["status"] == "alocado":
        st.caption(f"Setor atual: **{zonas_por_id[equip['setor_atual']]['nome']}**")
        if st.button("Marcar como quebrado"):
            # Regra do fluxo: ao quebrar, vai direto para o setor de Planejamento
            registrar_evento(equip, "quebrado", "planejamento")
            st.warning(f"{equip['nome']} marcado como quebrado e movido para Planejamento.")
            st.rerun()

    elif equip["status"] == "quebrado":
        st.caption("Setor atual: **Planejamento**")
        if st.button("Marcar como troca (saída definitiva)"):
            registrar_evento(equip, "trocado", equip["setor_atual"])
            st.error(f"{equip['nome']} baixado do almoxarifado (troca registrada).")
            st.rerun()


def painel_historico():
    st.subheader("3. Histórico / caminho de um equipamento")
    todos = st.session_state["equipamentos"]
    if not todos:
        st.info("Ainda não há equipamentos cadastrados.")
        return None

    opcoes = {f"{e['id']} — {e['nome']} ({LABEL_STATUS[e['status']]})": e["id"] for e in todos}
    escolha = st.selectbox("Ver caminho de", list(opcoes.keys()), key="select_historico")
    equip = next(e for e in todos if e["id"] == opcoes[escolha])

    zonas_por_id = {z["id"]: z for z in st.session_state["zonas"]}
    linhas = [
        {
            "Etapa": i + 1,
            "Status": LABEL_STATUS[ev["status"]],
            "Setor": zonas_por_id.get(ev["setor"], {}).get("nome", ev["setor"]),
            "Data/Hora": ev["data"],
        }
        for i, ev in enumerate(equip["historico"])
    ]
    st.table(linhas)
    return equip


def painel_baixados():
    baixados = equipamentos_baixados()
    if baixados:
        with st.expander(f"Equipamentos baixados / trocados ({len(baixados)})"):
            for e in baixados:
                st.markdown(f"**{e['id']} — {e['nome']}**")
                st.caption(" → ".join(f"{LABEL_STATUS[ev['status']]} ({ev['data']})" for ev in e["historico"]))


def editor_lateral():
    st.sidebar.header("Editar mapa (layout)")
    with st.sidebar.expander("Zonas do mapa", expanded=False):
        for z in st.session_state["zonas"]:
            st.markdown(f"**{z['id']}**")
            z["nome"] = st.text_input("Nome", value=z["nome"], key=f"nome_{z['id']}")
            z["cor"] = st.color_picker("Cor", value=z["cor"], key=f"cor_{z['id']}")
            col1, col2, col3, col4 = st.columns(4)
            z["x"] = col1.number_input("x", value=z["x"], key=f"x_{z['id']}")
            z["y"] = col2.number_input("y", value=z["y"], key=f"y_{z['id']}")
            z["w"] = col3.number_input("largura", value=z["w"], key=f"w_{z['id']}")
            z["h"] = col4.number_input("altura", value=z["h"], key=f"h_{z['id']}")
            st.divider()

    if st.sidebar.button("Restaurar padrão (layout)"):
        st.session_state["zonas"] = [z.copy() for z in ZONAS_PADRAO]
        st.session_state["linha_guia"] = LINHA_GUIA_PADRAO.copy()
        st.session_state["legenda"] = [l.copy() for l in LEGENDA_PADRAO]
        st.rerun()


# ============================================================
# 4. PÁGINA
# ============================================================
def main():
    carregar_estado()
    st.title("Mapa do Almoxarifado — Rastreabilidade de Equipamentos")

    editor_lateral()

    col_mapa, col_form = st.columns([2, 1])

    with col_form:
        painel_recebimento()
        st.divider()
        painel_transicoes()
        st.divider()
        equip_selecionado = painel_historico()
        st.divider()
        painel_baixados()

    with col_mapa:
        svg = gerar_svg(
            st.session_state["zonas"],
            st.session_state["linha_guia"],
            st.session_state["legenda"],
            equipamentos=st.session_state["equipamentos"],
            caminho_de=equip_selecionado,
        )
        st.markdown(svg, unsafe_allow_html=True)
        st.caption(
            "Os círculos numerados mostram o caminho do equipamento selecionado à esquerda: "
            "azul = recebido, verde = alocado, laranja = quebrado/planejamento, cinza = trocado (saída)."
        )


if __name__ == "__main__":
    main()
