"""
controle.py
=====================================================================
Módulo de rastreabilidade de equipamentos: mapa interativo + cadastro
em lote + histórico completo de vida útil (SLA).

Schema usado: rastreabilidade.*  (isolado do schema "public" do estoque)
Execute schema_rastreabilidade.sql uma vez no Supabase antes de usar.

IMPORTANTE — antes de usar, exponha o schema "rastreabilidade" na API do
Supabase: Project Settings > API > "Exposed schemas" > adicionar
"rastreabilidade" (por padrão só "public" fica exposto; sem isso todas
as chamadas abaixo retornam erro PGRST106/"schema must be one of...").
=====================================================================
"""

import io
from datetime import date, datetime

import pandas as pd
import streamlit as st
from utils.database import get_sb


# ======================================================================
# CONEXÃO — reaproveita o client já configurado em utils/database.py
# ======================================================================
def get_client():
    return get_sb().schema("rastreabilidade")


def usuario_atual() -> dict:
    """Espelha a estrutura real de st.session_state["usuario"]:
    chaves "nick" (login) e "perfil" ('usuario' | 'almoxarife' | 'admin')."""
    u = st.session_state.get("usuario", {})
    return {
        "nome": u.get("nome") or u.get("nick", "desconhecido"),
        "perfil": u.get("perfil", "usuario"),
    }


def pode_cadastrar() -> bool:
    return usuario_atual()["perfil"] in ("almoxarife", "admin")


# ======================================================================
# LAYOUT VISUAL DO MAPA (ajustável sem tocar na lógica)
# ======================================================================
VIEWBOX = "0 0 1200 560"

# Caixas dos setores: x, y, largura, altura
SETORES_BOX = {
    "par":      {"x": 20,  "y": 140, "w": 140, "h": 300, "nome": "PAR."},
    "transfer": {"x": 200, "y": 60,  "w": 430, "h": 60,  "nome": "TRANSFER"},
    "ecom":     {"x": 660, "y": 60,  "w": 430, "h": 60,  "nome": "ECOM."},
    "entrada":  {"x": 200, "y": 460, "w": 280, "h": 60,  "nome": "ENTRADA"},
    "receb":    {"x": 510, "y": 460, "w": 280, "h": 60,  "nome": "RECEB."},
    "plan":     {"x": 820, "y": 460, "w": 280, "h": 60,  "nome": "PLAN."},
}

# Pontos de ancoragem (INVISÍVEIS no render final). "entrada" tem os dois
# pontos citados: branco = chegada física, amarelo = saída da zona de
# entrada rumo ao setor de destino.
ANCORAS = {
    "par":            (160, 290),   # borda direita da caixa PAR
    "transfer":       (415, 140),   # base da caixa TRANSFER
    "ecom":           (875, 140),   # base da caixa ECOM
    "entrada_branco": (325, 460),   # topo da caixa ENTRADA (chegada)
    "entrada_amarelo":(355, 460),   # topo da caixa ENTRADA (saída p/ setor)
    "receb":          (650, 460),   # topo da caixa RECEB
    "plan":           (960, 460),   # topo da caixa PLAN
}

CORES_EVENTO = {
    "recebimento":       "#facc15",  # amarelo
    "alocacao":          "#22c55e",  # verde
    "quebra":            "#ef4444",  # vermelho
    "troca":             "#a1a1aa",  # cinza
    "emprestimo_saida":  "#38bdf8",  # azul
    "emprestimo_retorno":"#38bdf8",
}


def _ancora_setor(setor_id: str, ponto: str = "padrao"):
    if setor_id == "entrada":
        return ANCORAS["entrada_branco"] if ponto == "chegada" else ANCORAS["entrada_amarelo"]
    return ANCORAS[setor_id]


# ======================================================================
# ACESSO A DADOS
# ======================================================================
def carregar_setores() -> list[dict]:
    return get_client().table("setores").select("*").execute().data


def carregar_equipamentos() -> pd.DataFrame:
    data = get_client().table("equipamentos").select("*").execute().data
    return pd.DataFrame(data)


def carregar_movimentacoes(equipamento_id: int) -> pd.DataFrame:
    data = (
        get_client().table("movimentacoes")
        .select("*").eq("equipamento_id", equipamento_id)
        .order("data_evento").execute().data
    )
    return pd.DataFrame(data)


def carregar_emprestimos_ativos() -> pd.DataFrame:
    data = (
        get_client().table("emprestimos")
        .select("*, equipamentos(patrimonio)").eq("status", "ativo").execute().data
    )
    return pd.DataFrame(data)


def buscar_equipamento_por_patrimonio(patrimonio: str) -> dict | None:
    res = (
        get_client().table("equipamentos")
        .select("*").eq("patrimonio", patrimonio.strip()).execute().data
    )
    return res[0] if res else None


# ======================================================================
# REGRAS DE NEGÓCIO
# ======================================================================
def registrar_movimentacao(equipamento_id, evento, setor_origem=None, setor_destino=None,
                            condicao=None, descricao_quebra=None):
    get_client().table("movimentacoes").insert({
        "equipamento_id": equipamento_id,
        "evento": evento,
        "setor_origem": setor_origem,
        "setor_destino": setor_destino,
        "condicao": condicao,
        "descricao_quebra": descricao_quebra,
        "usuario_nome": usuario_atual()["nome"],
    }).execute()


def _atualizar_equipamento(equipamento_id, **campos):
    campos["atualizado_em"] = datetime.utcnow().isoformat()
    get_client().table("equipamentos").update(campos).eq("id", equipamento_id).execute()


def cadastrar_lote(patrimonios: list[str], tipo: str, descricao: str, acesso: str):
    """Cadastro em lote (item 4). Se o patrimônio já existir, NÃO recria
    (item 8) — apenas gera um novo evento 'recebimento' reabrindo o
    histórico do equipamento (reentrada na empresa)."""
    if not pode_cadastrar():
        st.error("Apenas Almoxarife ou Administrador podem cadastrar equipamentos.")
        return

    cliente = get_client()
    lote = cliente.table("lotes_cadastro").insert({
        "tipo": tipo, "descricao": descricao, "acesso": acesso,
        "criado_por": usuario_atual()["nome"],
    }).execute().data[0]

    novos, reentradas = [], []
    for p in patrimonios:
        p = p.strip()
        if not p:
            continue
        existente = buscar_equipamento_por_patrimonio(p)
        if existente:
            _atualizar_equipamento(existente["id"], status_atual="recebido", setor_atual=None)
            registrar_movimentacao(existente["id"], "recebimento", setor_destino="entrada")
            reentradas.append(p)
        else:
            novo = cliente.table("equipamentos").insert({
                "patrimonio": p, "lote_id": lote["id"], "tipo": tipo,
                "descricao": descricao, "acesso": acesso, "status_atual": "recebido",
            }).execute().data[0]
            registrar_movimentacao(novo["id"], "recebimento", setor_destino="entrada")
            novos.append(p)

    st.success(f"{len(novos)} equipamento(s) novo(s) cadastrado(s). "
               f"{len(reentradas)} reentrada(s) (histórico preservado).")


def delegar_para_setor(equipamento_id, setor_destino):
    """Primeira alocação, feita pelo Planejamento após o recebimento.
    Condição nasce sempre 'fixo' (item 7) — nada é perguntado aqui."""
    _atualizar_equipamento(equipamento_id, status_atual="alocado",
                            setor_atual=setor_destino, condicao_atual="fixo")
    registrar_movimentacao(equipamento_id, "alocacao", setor_origem="entrada",
                            setor_destino=setor_destino, condicao="fixo")


def informar_equipamento_em_setor(patrimonio: str, setor_contexto: str,
                                   condicao: str | None = None,
                                   data_devolucao: date | None = None):
    """Ação 'Informar equipamento' dentro de um setor (item 6)."""
    equip = buscar_equipamento_por_patrimonio(patrimonio)
    if not equip:
        st.error("Esse patrimônio não está cadastrado pelo Planejamento/Controladoria.")
        return
    if equip["status_atual"] not in ("alocado",):
        # ainda não teve primeira alocação -> vira a primeira alocação normal
        delegar_para_setor(equip["id"], setor_contexto)
        st.success(f"Equipamento {patrimonio} alocado em {setor_contexto}.")
        return

    setor_anterior = equip["setor_atual"]
    if setor_anterior == setor_contexto:
        st.info("Esse equipamento já está registrado neste setor.")
        return

    # Conflito: equipamento tem registro mais antigo em outro setor
    if condicao is None:
        st.session_state["_conflito_equip"] = {"patrimonio": patrimonio, "setor_contexto": setor_contexto,
                                                  "setor_anterior": setor_anterior}
        return

    if condicao == "fixo":
        _atualizar_equipamento(equip["id"], setor_atual=setor_contexto, condicao_atual="fixo")
        registrar_movimentacao(equip["id"], "alocacao", setor_origem=setor_anterior,
                                setor_destino=setor_contexto, condicao="fixo")
        st.success(f"{patrimonio} movido definitivamente para {setor_contexto}.")
    else:  # emprestimo
        if not data_devolucao:
            st.error("Informe a data de devolução para registrar o empréstimo.")
            return
        _atualizar_equipamento(equip["id"], setor_atual=setor_contexto, condicao_atual="emprestimo")
        mov = get_client().table("movimentacoes").insert({
            "equipamento_id": equip["id"], "evento": "emprestimo_saida",
            "setor_origem": setor_anterior, "setor_destino": setor_contexto,
            "condicao": "emprestimo", "usuario_nome": usuario_atual()["nome"],
        }).execute().data[0]
        get_client().table("emprestimos").insert({
            "equipamento_id": equip["id"], "movimentacao_saida_id": mov["id"],
            "setor_origem": setor_anterior, "setor_destino": setor_contexto,
            "data_devolucao_prevista": data_devolucao.isoformat(),
        }).execute()
        st.success(f"Empréstimo registrado: {patrimonio} de {setor_anterior} para {setor_contexto}, "
                    f"devolução prevista em {data_devolucao.strftime('%d/%m/%Y')}.")


def confirmar_devolucao(emprestimo_id, equipamento_id, setor_origem):
    """Devolução vencida: alerta é automático, mas a confirmação de
    retorno é sempre manual (nunca volta sozinho)."""
    _atualizar_equipamento(equipamento_id, setor_atual=setor_origem, condicao_atual="fixo")
    registrar_movimentacao(equipamento_id, "emprestimo_retorno", setor_destino=setor_origem)
    get_client().table("emprestimos").update({
        "status": "devolvido", "data_devolucao_real": date.today().isoformat(),
    }).eq("id", emprestimo_id).execute()
    st.success("Devolução confirmada.")


def informar_quebra(patrimonio: str, descricao: str):
    equip = buscar_equipamento_por_patrimonio(patrimonio)
    if not equip:
        st.error("Patrimônio não encontrado.")
        return
    if not descricao.strip():
        st.error("Descreva a quebra antes de confirmar.")
        return
    setor_anterior = equip["setor_atual"]
    _atualizar_equipamento(equip["id"], status_atual="quebrado", setor_atual="plan")
    registrar_movimentacao(equip["id"], "quebra", setor_origem=setor_anterior,
                            setor_destino="plan", descricao_quebra=descricao.strip())
    st.warning(f"{patrimonio} marcado como quebrado e movido para o Planejamento.")


def marcar_troca(patrimonio: str):
    equip = buscar_equipamento_por_patrimonio(patrimonio)
    if not equip:
        st.error("Patrimônio não encontrado.")
        return
    _atualizar_equipamento(equip["id"], status_atual="trocado")
    registrar_movimentacao(equip["id"], "troca", setor_origem=equip["setor_atual"])
    st.success(f"{patrimonio} marcado como trocado (saída do ciclo).")


# ======================================================================
# SVG — MAPA
# ======================================================================
def _svg_caixas() -> str:
    partes = []
    for sid, b in SETORES_BOX.items():
        partes.append(f'''
            <rect x="{b['x']}" y="{b['y']}" width="{b['w']}" height="{b['h']}"
                  rx="6" fill="#111113" stroke="#2a2a2e" stroke-width="1.5"/>
            <text x="{b['x'] + b['w']/2}" y="{b['y'] + b['h']/2}"
                  fill="#e4e4e7" font-size="13" font-weight="600"
                  text-anchor="middle" dominant-baseline="middle"
                  font-family="sans-serif">{b['nome']}</text>
        ''')
    return "".join(partes)


def _svg_grade() -> str:
    linhas = []
    for x in range(200, 1101, 60):
        linhas.append(f'<line x1="{x}" y1="140" x2="{x}" y2="460" stroke="#1c1c1f" stroke-width="1"/>')
    for y in range(140, 461, 53):
        linhas.append(f'<line x1="200" y1="{y}" x2="1100" y2="{y}" stroke="#1c1c1f" stroke-width="1"/>')
    return "".join(linhas)


def _rota_ortogonal(p_a, p_b) -> str:
    """Caminho em L (cotovelo único), no estilo da referência: desce/sobe
    e depois segue até o ponto de destino."""
    ax, ay = p_a
    bx, by = p_b
    return f"M {ax},{ay} L {ax},{by} L {bx},{by}"


def _svg_rastro(equipamento_id: int) -> str:
    df = carregar_movimentacoes(equipamento_id)
    if df.empty:
        return ""

    segmentos = []
    for _, ev in df.iterrows():
        origem, destino, evento = ev.get("setor_origem"), ev.get("setor_destino"), ev["evento"]
        if not origem or not destino:
            continue
        ponto_origem = _ancora_setor(origem, "saida" if origem == "entrada" else "padrao")
        ponto_destino = _ancora_setor(destino, "chegada" if destino == "entrada" else "padrao")
        cor = CORES_EVENTO.get(evento, "#888")
        path = _rota_ortogonal(ponto_origem, ponto_destino)
        segmentos.append(
            f'<path d="{path}" fill="none" stroke="{cor}" stroke-width="3" '
            f'stroke-dasharray="6,5" marker-end="url(#seta-{cor.strip("#")})"/>'
        )

    # marcadores de seta (um por cor usada, definidos inline)
    cores_usadas = {CORES_EVENTO.get(e, "#888") for e in df["evento"]}
    defs = "".join(
        f'''<marker id="seta-{c.strip("#")}" markerWidth="8" markerHeight="8"
                refX="6" refY="3" orient="auto">
              <path d="M0,0 L6,3 L0,6 Z" fill="{c}"/>
            </marker>''' for c in cores_usadas
    )
    return f"<defs>{defs}</defs>" + "".join(segmentos)


def render_mapa(equipamento_selecionado: dict | None):
    rastro = _svg_rastro(equipamento_selecionado["id"]) if equipamento_selecionado else ""
    texto_central = "" if equipamento_selecionado else '''
        <text x="650" y="300" fill="#71717a" font-size="15" text-anchor="middle"
              font-family="sans-serif">Selecione um equipamento para ver o rastro</text>
    '''
    svg = f'''
    <svg viewBox="{VIEWBOX}" xmlns="http://www.w3.org/2000/svg"
         style="width:100%; background:#0a0a0b; border-radius:10px;">
        {_svg_grade()}
        {_svg_caixas()}
        {texto_central}
        {rastro}
    </svg>
    '''
    st.markdown(svg, unsafe_allow_html=True)


# ======================================================================
# RESUMO GERAL (horizontal, abaixo do mapa)
# ======================================================================
def render_resumo_horizontal(df: pd.DataFrame):
    total = len(df)
    em_uso = int((df["status_atual"] == "alocado").sum()) if not df.empty else 0
    quebrados = int((df["status_atual"] == "quebrado").sum()) if not df.empty else 0
    trocados = int((df["status_atual"] == "trocado").sum()) if not df.empty else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total", total)
    c2.metric("Em uso", em_uso)
    c3.metric("Quebrados", quebrados)
    c4.metric("Substituídos", trocados)


# ======================================================================
# ABA: MAPA
# ======================================================================
def aba_mapa():
    df = carregar_equipamentos()

    # Alerta de empréstimos vencidos (automático, confirmação manual)
    emprestimos = carregar_emprestimos_ativos()
    if not emprestimos.empty:
        hoje = date.today().isoformat()
        vencidos = emprestimos[emprestimos["data_devolucao_prevista"] <= hoje]
        for _, e in vencidos.iterrows():
            patrimonio = e.get("equipamentos", {}).get("patrimonio", "?") if isinstance(e.get("equipamentos"), dict) else "?"
            with st.container(border=True):
                st.warning(f"Devolução vencida: **{patrimonio}** deveria ter retornado para "
                           f"**{e['setor_origem']}** em {e['data_devolucao_prevista']}.")
                if st.button(f"Confirmar devolução — {patrimonio}", key=f"dev_{e['id']}"):
                    confirmar_devolucao(e["id"], e["equipamento_id"], e["setor_origem"])
                    st.rerun()

    opcoes = ["—"] + (df["patrimonio"].tolist() if not df.empty else [])
    escolha = st.selectbox("Selecione um equipamento para ver o rastro", opcoes, label_visibility="collapsed")
    equip_sel = None
    if escolha != "—":
        equip_sel = df[df["patrimonio"] == escolha].iloc[0].to_dict()

    render_mapa(equip_sel)
    render_resumo_horizontal(df)


# ======================================================================
# ABA: EQUIPAMENTOS (cadastro em lote + ações por setor + histórico)
# ======================================================================
def aba_equipamentos():
    setores = carregar_setores()
    df = carregar_equipamentos()

    with st.expander("Cadastrar equipamentos (lote)", expanded=False):
        if not pode_cadastrar():
            st.info("Apenas Almoxarife ou Administrador podem cadastrar equipamentos.")
        else:
            patrimonios_txt = st.text_area(
                "Patrimônios (um por linha)", height=120,
                placeholder="000123\n000124\n000125")
            col1, col2, col3 = st.columns(3)
            tipo = col1.text_input("Tipo")
            descricao = col2.text_input("Descrição")
            acesso = col3.text_input("Acesso")
            if st.button("Salvar lote", type="primary"):
                lista = [p for p in patrimonios_txt.splitlines() if p.strip()]
                if not lista or not tipo:
                    st.error("Informe ao menos um patrimônio e o tipo.")
                else:
                    cadastrar_lote(lista, tipo, descricao, acesso)
                    st.rerun()

    st.divider()
    st.subheader("Setores")
    tabs = st.tabs([s["nome"] for s in setores])
    for tab, setor in zip(tabs, setores):
        with tab:
            equipes_setor = df[df["setor_atual"] == setor["id"]] if not df.empty else pd.DataFrame()
            st.dataframe(
                equipes_setor[["patrimonio", "tipo", "status_atual", "condicao_atual"]]
                if not equipes_setor.empty else pd.DataFrame(columns=["patrimonio", "tipo", "status_atual", "condicao_atual"]),
                use_container_width=True, hide_index=True,
            )

            st.markdown("**Informar equipamento**")
            patrimonio_in = st.text_input("Patrimônio", key=f"pat_{setor['id']}")
            if st.button("Confirmar", key=f"btn_{setor['id']}"):
                informar_equipamento_em_setor(patrimonio_in, setor["id"])

            conflito = st.session_state.get("_conflito_equip")
            if conflito and conflito["setor_contexto"] == setor["id"]:
                st.warning(f"O equipamento {conflito['patrimonio']} já está registrado em "
                           f"**{conflito['setor_anterior']}**. Deseja confirmar a movimentação?")
                cond = st.radio("Condição", ["fixo", "emprestimo"], key=f"cond_{setor['id']}", horizontal=True)
                data_dev = None
                if cond == "emprestimo":
                    data_dev = st.date_input("Data de devolução", key=f"data_{setor['id']}")
                cc1, cc2 = st.columns(2)
                if cc1.button("Confirmar movimentação", key=f"ok_{setor['id']}"):
                    informar_equipamento_em_setor(conflito["patrimonio"], conflito["setor_contexto"],
                                                   condicao=cond, data_devolucao=data_dev)
                    st.session_state.pop("_conflito_equip", None)
                    st.rerun()
                if cc2.button("Cancelar", key=f"cancel_{setor['id']}"):
                    st.session_state.pop("_conflito_equip", None)
                    st.rerun()

            st.markdown("**Marcar quebrado**")
            pat_quebra = st.text_input("Patrimônio", key=f"pq_{setor['id']}")
            desc_quebra = st.text_input("Descreva a quebra", key=f"dq_{setor['id']}")
            if st.button("Registrar quebra", key=f"bq_{setor['id']}"):
                informar_quebra(pat_quebra, desc_quebra)
                st.rerun()

            if setor["id"] == "plan":
                st.markdown("**Delegar para setor / marcar troca**")
                pat_deleg = st.text_input("Patrimônio", key=f"pd_{setor['id']}")
                destino = st.selectbox("Delegar para", [s["id"] for s in setores if not s["especial"]],
                                        key=f"dest_{setor['id']}")
                cdel1, cdel2 = st.columns(2)
                if cdel1.button("Delegar", key=f"bd_{setor['id']}"):
                    eq = buscar_equipamento_por_patrimonio(pat_deleg)
                    if eq:
                        delegar_para_setor(eq["id"], destino)
                        st.rerun()
                    else:
                        st.error("Patrimônio não encontrado.")
                if cdel2.button("Marcar como trocado (saída definitiva)", key=f"bt_{setor['id']}"):
                    marcar_troca(pat_deleg)
                    st.rerun()

    st.divider()
    st.subheader("Histórico de vida útil")
    if not df.empty:
        pat_hist = st.selectbox("Equipamento", df["patrimonio"].tolist(), key="hist_sel")
        equip = df[df["patrimonio"] == pat_hist].iloc[0]
        hist = carregar_movimentacoes(int(equip["id"]))
        st.dataframe(hist, use_container_width=True, hide_index=True)

        if not hist.empty:
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
                hist.to_excel(writer, index=False, sheet_name="Historico")
            st.download_button(
                "Exportar histórico (Excel)", data=buffer.getvalue(),
                file_name=f"historico_{pat_hist}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )


# ======================================================================
# ABA: DASHBOARD
# ======================================================================
def aba_dashboard():
    df = carregar_equipamentos()
    render_resumo_horizontal(df)
    if not df.empty:
        st.bar_chart(df["status_atual"].value_counts())
        st.bar_chart(df["setor_atual"].value_counts())


# ======================================================================
# ENTRYPOINT
# ======================================================================
def main():
    st.title("Controle — Rastreamento de equipamentos")
    st.caption("Clique em um setor para ver os equipamentos ali alocados.")

    tab_mapa, tab_equip, tab_dash = st.tabs(["🗺️ Mapa", "📦 Equipamentos", "📊 Dashboard"])
    with tab_mapa:
        aba_mapa()
    with tab_equip:
        aba_equipamentos()
    with tab_dash:
        aba_dashboard()


if __name__ == "__main__":
    main()
