"""pages/controle/ui.py — Interface do módulo de rastreamento de equipamentos.

Nenhuma regra de negócio aqui — tudo delega para EquipamentoService.
Ponto de entrada: tela_controle().
"""
import io
from datetime import datetime

import streamlit as st

from .models import SETOR_NOMES, SETOR_IDS, STATUS_CORES, STATUS_LIST, SITUACOES
from .service import EquipamentoService

_service = EquipamentoService()

# ============================================================
# CSS — tema premium (fundo preto, neon vermelho, glass, glow)
# Classes com prefixo "ct-" para não colidir com o CSS do resto do sistema.
# ============================================================
_CSS = """<style>
.ct-wrap{--ct-red:#ef4444;--ct-red-d:#b91c1c;--ct-bg:#050506;--ct-glass:rgba(20,8,8,.55);
--ct-bdr:rgba(239,68,68,.45);font-family:'Plus Jakarta Sans',sans-serif;}
.ct-wrap .ct-title{font-size:1.15rem;font-weight:800;letter-spacing:.08em;text-transform:uppercase;
color:#fff;text-shadow:0 0 12px rgba(239,68,68,.65);margin-bottom:.15rem;}
.ct-wrap .ct-sub{font-size:.72rem;color:#9a9a9a;margin-bottom:1rem;}
.ct-wrap .setor-btn{background:linear-gradient(180deg,rgba(30,4,4,.85),rgba(10,2,2,.9));
border:1.5px solid var(--ct-bdr);border-radius:10px;box-shadow:0 0 16px rgba(239,68,68,.18) inset,0 0 10px rgba(239,68,68,.18);
margin-bottom:.6rem;transition:box-shadow .25s,border-color .25s;}
.ct-wrap .setor-btn:hover{box-shadow:0 0 26px rgba(239,68,68,.5) inset,0 0 18px rgba(239,68,68,.4);border-color:#ef4444;}
.ct-wrap .setor-btn [data-testid="stButton"] button{background:transparent!important;border:none!important;
color:#fff!important;font-weight:800!important;letter-spacing:.12em!important;text-transform:uppercase!important;
font-size:.78rem!important;height:78px!important;width:100%!important;text-shadow:0 0 8px rgba(239,68,68,.5);}
.ct-wrap .setor-tall [data-testid="stButton"] button{height:340px!important;writing-mode:vertical-rl;}
.ct-wrap .ct-card{background:var(--ct-glass);border:1.5px solid var(--ct-bdr);border-radius:10px;
padding:1rem 1.1rem;margin-bottom:.9rem;backdrop-filter:blur(6px);box-shadow:0 0 14px rgba(239,68,68,.12);}
.ct-wrap .ct-card-h{font-size:.72rem;font-weight:800;letter-spacing:.1em;text-transform:uppercase;
color:var(--ct-red);margin-bottom:.7rem;padding-bottom:.45rem;border-bottom:1px solid var(--ct-bdr);}
.ct-wrap .ct-kpi{background:var(--ct-glass);border:1.5px solid var(--ct-bdr);border-radius:10px;
padding:.8rem 1rem;box-shadow:0 0 12px rgba(239,68,68,.15);}
.ct-wrap .ct-kpi-label{font-size:.6rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:#9a9a9a;}
.ct-wrap .ct-kpi-val{font-size:1.7rem;font-weight:800;color:#fff;text-shadow:0 0 10px rgba(239,68,68,.6);}
.ct-wrap .ct-badge{display:inline-flex;align-items:center;gap:.3rem;padding:.15rem .55rem;border-radius:20px;
font-size:.62rem;font-weight:700;text-transform:uppercase;letter-spacing:.05em;border:1px solid currentColor;}
.ct-wrap .ct-hist-item{border-left:2px solid var(--ct-bdr);padding:.15rem 0 .9rem 1rem;margin-left:.3rem;position:relative;}
.ct-wrap .ct-hist-dot{position:absolute;left:-6.5px;top:2px;width:11px;height:11px;border-radius:50%;
box-shadow:0 0 8px currentColor;}
.ct-wrap .ct-hist-date{font-size:.68rem;color:#9a9a9a;}
.ct-wrap .ct-hist-status{font-weight:700;color:#fff;font-size:.85rem;}
.ct-wrap .ct-hist-obs{font-size:.72rem;color:#b5b5b5;}
</style>"""


def _usuario_atual() -> str:
    try:
        from utils.auth import sessao
        u = sessao()
        return (u or {}).get("nick", "usuário")
    except Exception:
        return "usuário"


def _badge_status(status: str) -> str:
    cor = STATUS_CORES.get(status, "#9a9a9a")
    return f'<span class="ct-badge" style="color:{cor}">{status}</span>'


# ============================================================
# RASTRO VISUAL (SVG com glow + animação, no "canvas" central)
# ============================================================
def _render_canvas(equip=None, mostrar_rastro=False):
    largura, altura = 760, 230
    partes = [
        f'<svg viewBox="0 0 {largura} {altura}" xmlns="http://www.w3.org/2000/svg">',
        '<defs><filter id="ctglow" x="-60%" y="-60%" width="220%" height="220%">'
        '<feGaussianBlur stdDeviation="4" result="b"/>'
        '<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>'
        '</filter></defs>',
        '<style>.ctdash{stroke-dasharray:8,7;animation:ctd 1.1s linear infinite}'
        '@keyframes ctd{to{stroke-dashoffset:-30}}</style>',
        f'<rect x="0" y="0" width="{largura}" height="{altura}" fill="#050506"/>',
    ]
    # grade sutil de fundo
    for gx in range(0, largura, 40):
        partes.append(f'<line x1="{gx}" y1="0" x2="{gx}" y2="{altura}" stroke="#1a1a1a" stroke-width="1"/>')
    for gy in range(0, altura, 40):
        partes.append(f'<line x1="0" y1="{gy}" x2="{largura}" y2="{gy}" stroke="#1a1a1a" stroke-width="1"/>')

    if mostrar_rastro and equip and equip.historico:
        n = len(equip.historico)
        step = largura / (n + 1)
        pontos = [(step * (i + 1), altura / 2 + (30 if i % 2 else -30)) for i in range(n)]
        for i in range(n - 1):
            x1, y1 = pontos[i]
            x2, y2 = pontos[i + 1]
            cor = STATUS_CORES.get(equip.historico[i + 1].status_novo, "#ef4444")
            partes.append(
                f'<path d="M{x1},{y1} L{x1},{(y1+y2)/2} L{x2},{(y1+y2)/2} L{x2},{y2}" '
                f'fill="none" stroke="{cor}" stroke-width="2.5" class="ctdash" filter="url(#ctglow)"/>'
            )
        for i, (x, y) in enumerate(pontos):
            ev = equip.historico[i]
            cor = STATUS_CORES.get(ev.status_novo, "#ef4444")
            partes.append(f'<circle cx="{x}" cy="{y}" r="8" fill="{cor}" filter="url(#ctglow)"/>')
            partes.append(
                f'<text x="{x}" y="{y-14}" font-size="10" text-anchor="middle" fill="#fff" '
                f'font-family="sans-serif">{SETOR_NOMES.get(ev.setor_novo, ev.setor_novo)}</text>'
            )
    else:
        partes.append(
            f'<text x="{largura/2}" y="{altura/2}" font-size="13" text-anchor="middle" '
            'fill="#555" font-family="sans-serif">Selecione um equipamento para ver o rastro</text>'
        )
    partes.append("</svg>")
    st.markdown("".join(partes), unsafe_allow_html=True)


# ============================================================
# MODAL — equipamentos de um setor (clique no retângulo do mapa)
# ============================================================
@st.dialog("Equipamentos do setor")
def _dialog_setor(setor_id: str):
    st.markdown(f"#### {SETOR_NOMES[setor_id]}")
    equipamentos = _service.por_setor(setor_id)
    if not equipamentos:
        st.caption("Nenhum equipamento ativo neste setor.")
    for e in equipamentos:
        col1, col2 = st.columns([4, 1])
        col1.markdown(
            f"**{e.descricao}**  \n`{e.numero_serie}` &nbsp; {_badge_status(e.status)}",
            unsafe_allow_html=True,
        )
        if col2.button("Abrir", key=f"open_{e.id}"):
            st.session_state["ct_equip_sel"] = e.id
            st.session_state["ct_view"] = "detalhe"
            st.rerun()


def _setor_button(setor_id: str, tall: bool = False):
    nome = SETOR_NOMES[setor_id]
    qtd = len(_service.por_setor(setor_id))
    st.markdown(f'<div class="setor-btn{" setor-tall" if tall else ""}">', unsafe_allow_html=True)
    clicado = st.button(f"{nome}\n({qtd})", key=f"setor_{setor_id}", use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)
    if clicado:
        _dialog_setor(setor_id)


def _render_mapa(equip_destaque=None, mostrar_rastro=False):
    col_par, col_main = st.columns([1, 4])
    with col_par:
        _setor_button("par", tall=True)
    with col_main:
        c1, c2 = st.columns(2)
        with c1:
            _setor_button("transfer")
        with c2:
            _setor_button("ecom")
        _render_canvas(equip_destaque, mostrar_rastro)
        c3, c4, c5 = st.columns([2, 2, 1])
        with c3:
            _setor_button("entrada")
        with c4:
            _setor_button("receb")
        with c5:
            _setor_button("plan")


# ============================================================
# CONFIRMAÇÃO DE ALTERAÇÃO (obrigatória antes de gravar qualquer mudança)
# ============================================================
@st.dialog("Confirmar alteração")
def _dialog_confirmar():
    p = st.session_state.get("ct_pendente")
    if not p:
        st.stop()
    equip = _service.buscar(p["equip_id"])
    st.write(
        f"De **{equip.status}** ({SETOR_NOMES.get(equip.setor, equip.setor)}) "
        f"para **{p['novo_status']}** ({SETOR_NOMES.get(p['novo_setor'], p['novo_setor'])})"
    )
    if p.get("observacao"):
        st.caption(f"Observação: {p['observacao']}")
    c1, c2 = st.columns(2)
    if c1.button("Cancelar", use_container_width=True):
        st.session_state.pop("ct_pendente", None)
        st.rerun()
    if c2.button("Sim, confirmar", type="primary", use_container_width=True):
        _service.alterar_status(
            equip, p["novo_status"], p["novo_setor"],
            usuario=_usuario_atual(), observacao=p.get("observacao", ""),
        )
        st.session_state.pop("ct_pendente", None)
        st.success("Status atualizado com sucesso.")
        st.rerun()


# ============================================================
# TELA DE DETALHE DO EQUIPAMENTO
# ============================================================
def _exportar_historico(equip):
    import pandas as pd
    linhas = [{
        "Data/Hora": ev.data_hora, "Status anterior": ev.status_anterior or "-",
        "Status novo": ev.status_novo, "Setor anterior": SETOR_NOMES.get(ev.setor_anterior, ev.setor_anterior or "-"),
        "Setor novo": SETOR_NOMES.get(ev.setor_novo, ev.setor_novo), "Usuário": ev.usuario,
        "Observação": ev.observacao,
    } for ev in equip.historico]
    df = pd.DataFrame(linhas)
    c1, c2 = st.columns(2)
    c1.download_button("⬇ CSV", df.to_csv(index=False).encode("utf-8"),
                        file_name=f"historico_{equip.numero_serie}.csv", mime="text/csv", use_container_width=True)
    buf = io.BytesIO()
    df.to_excel(buf, index=False, engine="openpyxl")
    c2.download_button("⬇ Excel", buf.getvalue(), file_name=f"historico_{equip.numero_serie}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True)


def _render_detalhe(equip):
    if st.button("← VOLTAR PARA O MAPA"):
        st.session_state["ct_view"] = "mapa"
        st.rerun()

    st.markdown(
        f'<div class="ct-title">EQUIPAMENTO: {equip.descricao.upper()}</div>'
        f'<div class="ct-sub">Nº SÉRIE: {equip.numero_serie} &nbsp; {_badge_status(equip.status)} '
        f'&nbsp; <span class="ct-badge" style="color:#9a9a9a">{equip.situacao}</span></div>',
        unsafe_allow_html=True,
    )

    col_esq, col_dir = st.columns([2, 1])

    with col_esq:
        mostrar = st.toggle("Ver rastro no mapa", value=True, key="ct_toggle_rastro")
        _render_mapa(equip, mostrar)

        st.markdown('<div class="ct-card"><div class="ct-card-h">Dados do equipamento</div>', unsafe_allow_html=True)
        cA, cB = st.columns(2)
        cA.text_input("Número de série", equip.numero_serie, disabled=True, key="ct_ns")
        cA.text_input("Fabricante", equip.fabricante, disabled=True, key="ct_fab")
        cA.text_input("Modelo", equip.modelo, disabled=True, key="ct_mod")
        cB.text_input("Tipo", equip.tipo, disabled=True, key="ct_tipo")
        cB.text_input("Categoria", equip.categoria, disabled=True, key="ct_cat")
        cB.text_input("Patrimônio", equip.patrimonio, disabled=True, key="ct_patr")
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown('<div class="ct-card"><div class="ct-card-h">Alterar status do equipamento</div>', unsafe_allow_html=True)
        novo_status = st.radio("Novo status", STATUS_LIST, horizontal=True, key="ct_novo_status")
        novo_setor = st.selectbox("Setor", SETOR_IDS, format_func=lambda s: SETOR_NOMES[s], key="ct_novo_setor")
        observacao = st.text_area("Observação (opcional)", max_chars=200, key="ct_obs")
        cbt1, cbt2 = st.columns(2)
        if cbt1.button("Cancelar", use_container_width=True, key="ct_cancelar_alt"):
            st.rerun()
        if cbt2.button("Confirmar alteração", type="primary", use_container_width=True, key="ct_confirmar_alt"):
            st.session_state["ct_pendente"] = {
                "equip_id": equip.id, "novo_status": novo_status,
                "novo_setor": novo_setor, "observacao": observacao,
            }
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    with col_dir:
        st.markdown('<div class="ct-card"><div class="ct-card-h">Histórico de movimentações</div>', unsafe_allow_html=True)
        for ev in reversed(equip.historico):
            cor = STATUS_CORES.get(ev.status_novo, "#9a9a9a")
            st.markdown(
                f'<div class="ct-hist-item" style="color:{cor}">'
                f'<div class="ct-hist-dot" style="background:{cor}"></div>'
                f'<div class="ct-hist-date">{ev.data_hora}</div>'
                f'<div class="ct-hist-status">{ev.status_novo}</div>'
                f'<div class="ct-hist-obs">{SETOR_NOMES.get(ev.setor_novo, ev.setor_novo)} · '
                f'Usuário: {ev.usuario}</div>'
                f'<div class="ct-hist-obs">{ev.observacao}</div></div>',
                unsafe_allow_html=True,
            )
        st.markdown("</div>", unsafe_allow_html=True)
        st.markdown('<div class="ct-card"><div class="ct-card-h">Exportar histórico</div>', unsafe_allow_html=True)
        _exportar_historico(equip)
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown(
            '<div class="ct-card"><div class="ct-card-h">Informações adicionais</div>'
            f'<p>Fornecedor: {equip.fornecedor or "-"}</p>'
            f'<p>Próprio/Alugado: {equip.proprio_ou_alugado}</p>'
            f'<p>Data de aquisição: {equip.data_aquisicao or "-"}</p>'
            f'<p>Garantia até: {equip.garantia_ate or "-"}</p>'
            f'<p>Observações: {equip.observacoes or "-"}</p></div>',
            unsafe_allow_html=True,
        )


# ============================================================
# ABA "EQUIPAMENTOS" — cadastro, filtros e listagem
# ============================================================
def _painel_cadastro():
    with st.expander("➕ Novo equipamento (recebimento)"):
        with st.form("ct_form_cadastro", clear_on_submit=True):
            c1, c2 = st.columns(2)
            numero_serie = c1.text_input("Número de série *")
            descricao = c2.text_input("Descrição *")
            fabricante = c1.text_input("Fabricante")
            modelo = c2.text_input("Modelo")
            tipo = c1.text_input("Tipo")
            categoria = c2.text_input("Categoria")
            patrimonio = c1.text_input("Patrimônio")
            proprio_ou_alugado = c2.radio("Classificação", ["Próprio", "Alugado"], horizontal=True)
            fornecedor = c1.text_input("Fornecedor")
            data_aquisicao = c2.text_input("Data de aquisição (dd/mm/aaaa)")
            garantia_ate = c1.text_input("Garantia até (dd/mm/aaaa)")
            observacoes = st.text_area("Observações")
            enviado = st.form_submit_button("Registrar recebimento")
            if enviado:
                if not numero_serie.strip() or not descricao.strip():
                    st.warning("Preencha ao menos número de série e descrição.")
                else:
                    _service.criar_equipamento({
                        "numero_serie": numero_serie.strip(), "descricao": descricao.strip(),
                        "fabricante": fabricante, "modelo": modelo, "tipo": tipo, "categoria": categoria,
                        "patrimonio": patrimonio, "proprio_ou_alugado": proprio_ou_alugado,
                        "fornecedor": fornecedor, "data_aquisicao": data_aquisicao,
                        "garantia_ate": garantia_ate, "observacoes": observacoes,
                    }, usuario=_usuario_atual())
                    st.success(f"Equipamento {numero_serie} recebido.")
                    st.rerun()


def _painel_lista():
    todos = _service.listar()
    if not todos:
        st.info("Nenhum equipamento cadastrado ainda.")
        return

    with st.expander("🔎 Filtros", expanded=False):
        c1, c2, c3, c4 = st.columns(4)
        f_serie = c1.text_input("Nº de série contém")
        f_status = c2.selectbox("Status", ["(todos)"] + STATUS_LIST)
        f_setor = c3.selectbox("Setor", ["(todos)"] + SETOR_IDS, format_func=lambda s: s if s == "(todos)" else SETOR_NOMES[s])
        f_prop = c4.selectbox("Próprio/Alugado", ["(todos)", "Próprio", "Alugado"])
        c5, c6 = st.columns(2)
        f_tipo = c5.text_input("Tipo contém")
        f_fornecedor = c6.text_input("Fornecedor contém")

    filtrados = todos
    if f_serie:
        filtrados = [e for e in filtrados if f_serie.lower() in e.numero_serie.lower()]
    if f_status != "(todos)":
        filtrados = [e for e in filtrados if e.status == f_status]
    if f_setor != "(todos)":
        filtrados = [e for e in filtrados if e.setor == f_setor]
    if f_prop != "(todos)":
        filtrados = [e for e in filtrados if e.proprio_ou_alugado == f_prop]
    if f_tipo:
        filtrados = [e for e in filtrados if f_tipo.lower() in (e.tipo or "").lower()]
    if f_fornecedor:
        filtrados = [e for e in filtrados if f_fornecedor.lower() in (e.fornecedor or "").lower()]

    st.caption(f"{len(filtrados)} equipamento(s)")
    for e in filtrados:
        col1, col2, col3 = st.columns([3, 2, 1])
        col1.markdown(f"**{e.descricao}**  \n`{e.numero_serie}`")
        col2.markdown(f"{_badge_status(e.status)} &nbsp; {SETOR_NOMES.get(e.setor,e.setor)}", unsafe_allow_html=True)
        if col3.button("Abrir", key=f"lst_open_{e.id}"):
            st.session_state["ct_equip_sel"] = e.id
            st.session_state["ct_view"] = "detalhe"
            st.rerun()


# ============================================================
# ABA "DASHBOARD"
# ============================================================
def _tempo_medio_por_setor(equipamentos):
    acumulado = {}
    contagem = {}
    fmt = "%d/%m/%Y %H:%M"
    for e in equipamentos:
        hist = e.historico
        for i in range(len(hist) - 1):
            try:
                t1 = datetime.strptime(hist[i].data_hora, fmt)
                t2 = datetime.strptime(hist[i + 1].data_hora, fmt)
            except ValueError:
                continue
            setor = hist[i].setor_novo
            horas = max(0.0, (t2 - t1).total_seconds() / 3600)
            acumulado[setor] = acumulado.get(setor, 0) + horas
            contagem[setor] = contagem.get(setor, 0) + 1
    return {s: acumulado[s] / contagem[s] for s in acumulado if contagem[s]}


def _painel_dashboard():
    todos = _service.listar()
    total = len(todos)
    por_status = {s: sum(1 for e in todos if e.status == s) for s in STATUS_LIST}
    proprios = sum(1 for e in todos if e.proprio_ou_alugado == "Próprio")
    alugados = total - proprios

    cols = st.columns(4)
    kpis = [
        ("Total de equipamentos", total, "#fff"),
        ("Em uso", por_status.get("Em uso", 0), STATUS_CORES["Em uso"]),
        ("Quebrados", por_status.get("Quebrado", 0), STATUS_CORES["Quebrado"]),
        ("Em manutenção", por_status.get("Em manutenção", 0), STATUS_CORES["Em manutenção"]),
    ]
    for col, (label, val, cor) in zip(cols, kpis):
        col.markdown(
            f'<div class="ct-kpi"><div class="ct-kpi-label">{label}</div>'
            f'<div class="ct-kpi-val" style="color:{cor}">{val}</div></div>',
            unsafe_allow_html=True,
        )

    st.markdown("<br/>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        st.markdown('<div class="ct-card"><div class="ct-card-h">Por status</div>', unsafe_allow_html=True)
        st.bar_chart(por_status)
        st.markdown("</div>", unsafe_allow_html=True)
    with c2:
        st.markdown('<div class="ct-card"><div class="ct-card-h">Próprio vs. Alugado</div>', unsafe_allow_html=True)
        st.bar_chart({"Próprio": proprios, "Alugado": alugados})
        st.markdown("</div>", unsafe_allow_html=True)

    tempos = _tempo_medio_por_setor(todos)
    if tempos:
        st.markdown('<div class="ct-card"><div class="ct-card-h">Tempo médio em cada setor (horas)</div>', unsafe_allow_html=True)
        st.bar_chart({SETOR_NOMES.get(s, s): round(h, 1) for s, h in tempos.items()})
        st.markdown("</div>", unsafe_allow_html=True)


# ============================================================
# PONTO DE ENTRADA DA PÁGINA
# ============================================================
def tela_controle():
    st.markdown(_CSS, unsafe_allow_html=True)
    st.markdown('<div class="ct-wrap">', unsafe_allow_html=True)

    # Se há uma alteração pendente de confirmação, o diálogo precisa reabrir
    # em TODA execução do script (não só na que originou o clique) — do
    # contrário ele desaparece no próximo rerun antes do usuário confirmar.
    if st.session_state.get("ct_pendente"):
        _dialog_confirmar()

    if st.session_state.get("ct_view") == "detalhe" and st.session_state.get("ct_equip_sel"):
        equip = _service.buscar(st.session_state["ct_equip_sel"])
        if equip:
            _render_detalhe(equip)
        else:
            st.session_state["ct_view"] = "mapa"
            st.rerun()
    else:
        st.markdown(
            '<div class="ct-title">CONTROLE — RASTREAMENTO DE EQUIPAMENTOS</div>'
            '<div class="ct-sub">Clique em um setor para ver os equipamentos ali alocados.</div>',
            unsafe_allow_html=True,
        )
        aba_mapa, aba_lista, aba_dash = st.tabs(["🗺️ Mapa", "📋 Equipamentos", "📊 Dashboard"])
        with aba_mapa:
            _render_mapa()
        with aba_lista:
            _painel_cadastro()
            _painel_lista()
        with aba_dash:
            _painel_dashboard()

    st.markdown("</div>", unsafe_allow_html=True)
