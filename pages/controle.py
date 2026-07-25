"""pages/controle.py — Módulo de Rastreamento Inteligente de Equipamentos.

Arquivo único (sem subpastas) para simplificar deploy manual via GitHub.
Camadas dentro do mesmo arquivo: modelos, repository, service, UI.
Ponto de entrada usado pelo app.py: tela_controle()
"""
from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime
import io

import streamlit as st

# ============================================================
# 1. MODELOS
# ============================================================
# ── Setores fixos do mapa (ver ui.py para a geometria/posições) ─────────
SETOR_NOMES = {
    "transfer": "TRANSFER",
    "ecom": "ECOM.",
    "par": "PAR.",
    "entrada": "ENTRADA",
    "receb": "RECEB.",
    "plan": "PLAN.",
}
SETOR_IDS = list(SETOR_NOMES.keys())

# ── Status possíveis e cor associada (usada nos badges e no rastro) ─────
STATUS_CORES = {
    "Recebido": "#22c55e",
    "Em uso": "#3b82f6",
    "Em traslado": "#f59e0b",
    "Quebrado": "#ef4444",
    "Em manutenção": "#eab308",
    "Substituído": "#e5e7eb",
    "Disponível": "#38bdf8",
    "Descartado": "#6b7280",
}
STATUS_LIST = list(STATUS_CORES.keys())
# Subconjunto mostrado na legenda enxuta do mapa (igual à referência visual)
STATUS_LEGENDA = ["Recebido", "Em uso", "Em traslado", "Quebrado", "Substituído"]

SITUACOES = ["Ativo", "Inativo", "Baixado"]


@dataclass
class EventoHistorico:
    data_hora: str
    status_anterior: Optional[str]
    status_novo: str
    setor_anterior: Optional[str]
    setor_novo: str
    usuario: str
    observacao: str = ""


@dataclass
class Equipamento:
    id: str
    numero_serie: str
    descricao: str
    fabricante: str = ""
    modelo: str = ""
    tipo: str = ""
    categoria: str = ""
    patrimonio: str = ""
    proprio_ou_alugado: str = "Próprio"
    fornecedor: str = ""
    data_aquisicao: str = ""
    garantia_ate: str = ""
    observacoes: str = ""
    situacao: str = "Ativo"
    status: str = "Recebido"
    setor: str = "entrada"
    historico: List[EventoHistorico] = field(default_factory=list)


# ============================================================
# 2. REPOSITORY
# ============================================================
class EquipamentoRepository:
    def __init__(self):
        if "ct_equipamentos" not in st.session_state:
            st.session_state["ct_equipamentos"] = {}   # id -> Equipamento
        if "ct_seq" not in st.session_state:
            st.session_state["ct_seq"] = 1

    # ── LEITURA ──────────────────────────────────────────────────────
    def listar(self) -> List[Equipamento]:
        # TODO Supabase:
        # rows = get_sb().schema("equipment_tracking").table("equipment") \
        #     .select("*").is_("deleted_at","null").execute().data or []
        # + join com equipment_status_logs para montar o histórico
        return list(st.session_state["ct_equipamentos"].values())

    def buscar(self, equipamento_id: str) -> Optional[Equipamento]:
        return st.session_state["ct_equipamentos"].get(equipamento_id)

    # ── ESCRITA ──────────────────────────────────────────────────────
    def proximo_id(self) -> str:
        n = st.session_state["ct_seq"]
        st.session_state["ct_seq"] += 1
        return f"EQ{n:04d}"

    def salvar(self, equip: Equipamento):
        # TODO Supabase: upsert em equipment_tracking.equipment (sem tocar historico)
        st.session_state["ct_equipamentos"][equip.id] = equip

    def registrar_evento(self, equip: Equipamento, evento: EventoHistorico):
        """Append-only: nunca sobrescreve, sempre adiciona um novo evento."""
        # TODO Supabase: INSERT em equipment_tracking.equipment_status_logs
        # (o histórico nunca é editado/apagado, só cresce)
        equip.historico.append(evento)
        self.salvar(equip)

    @staticmethod
    def agora() -> str:
        return datetime.now().strftime("%d/%m/%Y %H:%M")


# ============================================================
# 3. SERVICE
# ============================================================
class EquipamentoService:
    def __init__(self, repo: Optional[EquipamentoRepository] = None):
        self.repo = repo or EquipamentoRepository()

    # ── CONSULTAS ────────────────────────────────────────────────────
    def listar(self):
        return self.repo.listar()

    def buscar(self, equipamento_id: str):
        return self.repo.buscar(equipamento_id)

    def por_setor(self, setor_id: str):
        return [e for e in self.listar() if e.setor == setor_id and e.situacao != "Baixado"]

    # ── CRIAÇÃO (equivale ao "Recebimento") ─────────────────────────
    def criar_equipamento(self, dados: dict, usuario: str) -> Equipamento:
        equip = Equipamento(
            id=self.repo.proximo_id(),
            numero_serie=dados["numero_serie"],
            descricao=dados["descricao"],
            fabricante=dados.get("fabricante", ""),
            modelo=dados.get("modelo", ""),
            tipo=dados.get("tipo", ""),
            categoria=dados.get("categoria", ""),
            patrimonio=dados.get("patrimonio", ""),
            proprio_ou_alugado=dados.get("proprio_ou_alugado", "Próprio"),
            fornecedor=dados.get("fornecedor", ""),
            data_aquisicao=dados.get("data_aquisicao", ""),
            garantia_ate=dados.get("garantia_ate", ""),
            observacoes=dados.get("observacoes", ""),
            situacao="Ativo",
            status="Recebido",
            setor="entrada",
        )
        evento = EventoHistorico(
            data_hora=self.repo.agora(),
            status_anterior=None,
            status_novo="Recebido",
            setor_anterior=None,
            setor_novo="entrada",
            usuario=usuario,
            observacao="Equipamento recebido no almoxarifado.",
        )
        self.repo.registrar_evento(equip, evento)
        return equip

    # ── TRANSIÇÃO DE STATUS/SETOR/SITUAÇÃO ──────────────────────────
    def alterar_status(self, equip: Equipamento, novo_status: str, novo_setor: str,
                        usuario: str, observacao: str = "", nova_situacao: Optional[str] = None):
        status_anterior = equip.status
        setor_anterior = equip.setor

        evento = EventoHistorico(
            data_hora=self.repo.agora(),
            status_anterior=status_anterior,
            status_novo=novo_status,
            setor_anterior=setor_anterior,
            setor_novo=novo_setor,
            usuario=usuario,
            observacao=observacao,
        )

        equip.status = novo_status
        equip.setor = novo_setor
        if nova_situacao:
            equip.situacao = nova_situacao
        if novo_status == "Descartado":
            equip.situacao = "Baixado"

        self.repo.registrar_evento(equip, evento)
        return equip


# ============================================================
# 4. UI
# ============================================================
_service = EquipamentoService()

# ============================================================
# CSS — tema premium (fundo preto, neon vermelho, glass, glow)
# Classes com prefixo "ct-" para não colidir com o CSS do resto do sistema.
# ============================================================
_CSS = """<style>
.ct-wrap{--ct-red:#ef4444;--ct-red-d:#b91c1c;--ct-bg:#050506;--ct-glass:rgba(18,8,8,.55);
--ct-bdr:rgba(239,68,68,.5);font-family:'Plus Jakarta Sans',sans-serif;}
.ct-wrap .ct-title{font-size:1.15rem;font-weight:800;letter-spacing:.08em;text-transform:uppercase;
color:#fff;text-shadow:0 0 12px rgba(239,68,68,.65);margin-bottom:.15rem;}
.ct-wrap .ct-sub{font-size:.72rem;color:#9a9a9a;margin-bottom:1rem;}
.ct-wrap .ct-card{background:var(--ct-glass);border:1.5px solid var(--ct-bdr);border-radius:12px;
padding:1rem 1.1rem;margin-bottom:.9rem;backdrop-filter:blur(6px);box-shadow:0 0 16px rgba(239,68,68,.14);}
.ct-wrap .ct-card-h{font-size:.72rem;font-weight:800;letter-spacing:.1em;text-transform:uppercase;
color:var(--ct-red);margin-bottom:.7rem;padding-bottom:.45rem;border-bottom:1px solid var(--ct-bdr);
display:flex;align-items:center;justify-content:space-between;}
.ct-wrap .ct-card-sub{font-size:.68rem;color:#888;margin-top:-.5rem;margin-bottom:.7rem;}

/* setores do mapa — contorno neon, transparente por dentro */
.ct-wrap .setor-btn{background:rgba(20,4,4,.35);border:1.5px solid var(--ct-bdr);border-radius:8px;
margin-bottom:.55rem;transition:box-shadow .25s,border-color .25s,background .25s;
box-shadow:0 0 10px rgba(239,68,68,.18) inset;}
.ct-wrap .setor-btn:hover{box-shadow:0 0 22px rgba(239,68,68,.55) inset,0 0 14px rgba(239,68,68,.4);
border-color:#ff5b5b;background:rgba(239,68,68,.1);}
.ct-wrap .setor-btn.setor-ativo{border-color:#fff;box-shadow:0 0 18px rgba(255,255,255,.35) inset;}
.ct-wrap .setor-btn [data-testid="stButton"] button{background:transparent!important;border:none!important;
color:#fff!important;font-weight:700!important;letter-spacing:.1em!important;text-transform:uppercase!important;
font-size:.76rem!important;height:64px!important;width:100%!important;}
.ct-wrap .setor-tall [data-testid="stButton"] button{height:290px!important;}

/* KPIs do resumo geral */
.ct-wrap .ct-kpi-row{display:flex;gap:.7rem;flex-wrap:wrap;}
.ct-wrap .ct-kpi{flex:1;min-width:90px;text-align:center;}
.ct-wrap .ct-kpi-ico{font-size:1.1rem;}
.ct-wrap .ct-kpi-val{font-size:1.4rem;font-weight:800;color:#fff;text-shadow:0 0 8px rgba(239,68,68,.5);}
.ct-wrap .ct-kpi-label{font-size:.6rem;color:#9a9a9a;text-transform:uppercase;letter-spacing:.05em;}

/* legenda de status */
.ct-wrap .ct-leg-item{display:flex;align-items:center;gap:.4rem;font-size:.74rem;color:#ddd;margin-bottom:.4rem;}
.ct-wrap .ct-dot{width:9px;height:9px;border-radius:50%;box-shadow:0 0 6px currentColor;flex-shrink:0;}

.ct-wrap .ct-badge{display:inline-flex;align-items:center;gap:.3rem;padding:.15rem .55rem;border-radius:20px;
font-size:.62rem;font-weight:700;text-transform:uppercase;letter-spacing:.05em;border:1px solid currentColor;}

/* histórico */
.ct-wrap .ct-hist-item{border-left:2px solid var(--ct-bdr);padding:.1rem 0 .85rem 1rem;margin-left:.3rem;position:relative;}
.ct-wrap .ct-hist-dot{position:absolute;left:-6.5px;top:2px;width:11px;height:11px;border-radius:50%;box-shadow:0 0 8px currentColor;}
.ct-wrap .ct-hist-date{font-size:.66rem;color:#9a9a9a;}
.ct-wrap .ct-hist-status{font-weight:700;color:#fff;font-size:.82rem;}
.ct-wrap .ct-hist-obs{font-size:.7rem;color:#b5b5b5;}
.ct-wrap .ct-empty{color:#777;font-size:.78rem;text-align:center;padding:1.2rem 0;}
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
    largura, altura = 900, 230
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
    for gx in range(0, largura, 45):
        partes.append(f'<line x1="{gx}" y1="0" x2="{gx}" y2="{altura}" stroke="#161616" stroke-width="1"/>')
    for gy in range(0, altura, 45):
        partes.append(f'<line x1="0" y1="{gy}" x2="{largura}" y2="{gy}" stroke="#161616" stroke-width="1"/>')

    if mostrar_rastro and equip and equip.historico:
        n = len(equip.historico)
        step = largura / (n + 1)
        pontos = [(step * (i + 1), altura / 2 + (35 if i % 2 else -35)) for i in range(n)]
        for i in range(n - 1):
            x1, y1 = pontos[i]
            x2, y2 = pontos[i + 1]
            cor = STATUS_CORES.get(equip.historico[i + 1].status_novo, "#ef4444")
            partes.append(
                f'<path d="M{x1},{y1} L{x1},{(y1+y2)/2} L{x2},{(y1+y2)/2} L{x2},{y2}" '
                f'fill="none" stroke="{cor}" stroke-width="2.5" class="ctdash" filter="url(#ctglow)" marker-end="url(#arrow)"/>'
            )
        partes.insert(2, '<marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" '
                          'orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#fff"/></marker>')
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


def _setor_button(setor_id: str, tall: bool = False):
    nome = SETOR_NOMES[setor_id]
    qtd = len(_service.por_setor(setor_id))
    ativo = st.session_state.get("ct_setor_foco") == setor_id
    classe = f'setor-btn{" setor-tall" if tall else ""}{" setor-ativo" if ativo else ""}'
    st.markdown(f'<div class="{classe}">', unsafe_allow_html=True)
    clicado = st.button(f"{nome} ({qtd})", key=f"setor_{setor_id}", use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)
    if clicado:
        st.session_state["ct_setor_foco"] = setor_id
        equipamentos = _service.por_setor(setor_id)
        st.session_state["ct_equip_sel"] = equipamentos[0].id if equipamentos else None
        st.rerun()


def _render_mapa():
    equip = _service.buscar(st.session_state.get("ct_equip_sel")) if st.session_state.get("ct_equip_sel") else None
    col_par, col_main = st.columns([1, 4])
    with col_par:
        _setor_button("par", tall=True)
    with col_main:
        c1, c2 = st.columns(2)
        with c1:
            _setor_button("transfer")
        with c2:
            _setor_button("ecom")
        _render_canvas(equip, mostrar_rastro=bool(equip))
        c3, c4, c5 = st.columns([2, 2, 1])
        with c3:
            _setor_button("entrada")
        with c4:
            _setor_button("receb")
        with c5:
            _setor_button("plan")


def _render_legenda():
    st.markdown('<div class="ct-card"><div class="ct-card-h">Legenda de status</div>', unsafe_allow_html=True)
    cols = st.columns(2)
    for i, status in enumerate(STATUS_LEGENDA):
        cor = STATUS_CORES[status]
        with cols[i % 2]:
            st.markdown(
                f'<div class="ct-leg-item"><span class="ct-dot" style="background:{cor};color:{cor}"></span>{status}</div>',
                unsafe_allow_html=True,
            )
    st.markdown("</div>", unsafe_allow_html=True)


def _render_resumo():
    todos = _service.listar()
    total = len(todos)
    em_uso = sum(1 for e in todos if e.status == "Em uso")
    quebrados = sum(1 for e in todos if e.status == "Quebrado")
    substituidos = sum(1 for e in todos if e.status == "Substituído")
    st.markdown('<div class="ct-card"><div class="ct-card-h">Resumo geral</div>', unsafe_allow_html=True)
    itens = [("📦", total, "Total"), ("🟢", em_uso, "Em uso"), ("⚠️", quebrados, "Quebrados"), ("🔁", substituidos, "Substituídos")]
    st.markdown(
        '<div class="ct-kpi-row">' + "".join(
            f'<div class="ct-kpi"><div class="ct-kpi-ico">{ico}</div>'
            f'<div class="ct-kpi-val">{val}</div><div class="ct-kpi-label">{label}</div></div>'
            for ico, val, label in itens
        ) + "</div>",
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)


def _render_rastro_explicacao():
    st.markdown(
        '<div class="ct-card"><div class="ct-card-h">🛡️ Rastro de movimentação</div>'
        '<div class="ct-card-sub">Cada mudança de status é registrada e confirmada, deixando um rastro '
        'visual no mapa e no histórico do equipamento.</div>',
        unsafe_allow_html=True,
    )
    cols = st.columns(len(STATUS_LEGENDA))
    for col, status in zip(cols, STATUS_LEGENDA):
        cor = STATUS_CORES[status]
        col.markdown(
            f'<div class="ct-leg-item"><span class="ct-dot" style="background:{cor};color:{cor}"></span>{status}</div>',
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)


# ============================================================
# CONFIRMAÇÃO DE ALTERAÇÃO (obrigatória antes de gravar setor/status)
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
    if c1.button("Cancelar", use_container_width=True, key="ct_dlg_cancelar"):
        st.session_state.pop("ct_pendente", None)
        st.rerun()
    if c2.button("Sim, confirmar", type="primary", use_container_width=True, key="ct_dlg_confirmar"):
        _service.alterar_status(
            equip, p["novo_status"], p["novo_setor"],
            usuario=_usuario_atual(), observacao=p.get("observacao", ""),
        )
        st.session_state.pop("ct_pendente", None)
        st.success("Status atualizado com sucesso.")
        st.rerun()


# ============================================================
# PAINEL LATERAL — Cadastrar/Editar
# ============================================================
def _painel_cadastro_editar(ctx="a"):
    equip = _service.buscar(st.session_state.get("ct_equip_sel")) if st.session_state.get("ct_equip_sel") else None
    titulo = "Editar equipamento" if equip else "Cadastrar equipamento"

    st.markdown(f'<div class="ct-card"><div class="ct-card-h">{titulo.upper()}', unsafe_allow_html=True)
    if equip:
        st.markdown('<span style="cursor:pointer" title="Cancelar seleção">✕</span></div>', unsafe_allow_html=True)
        if st.button("✕ Limpar seleção", key=f"ct_limpar_sel_{ctx}", use_container_width=True):
            st.session_state["ct_equip_sel"] = None
            st.session_state["ct_setor_foco"] = None
            st.rerun()
    else:
        st.markdown("</div>", unsafe_allow_html=True)

    numero_serie = st.text_input("Numeração", value=equip.numero_serie if equip else "", key=f"ct_f_num_{ctx}",
                                  disabled=bool(equip), placeholder="Ex.: 000123")
    tipo = st.text_input("Tipo", value=equip.tipo if equip else "", key=f"ct_f_tipo_{ctx}")
    descricao = st.text_input("Descrição", value=equip.descricao if equip else "", key=f"ct_f_desc_{ctx}")

    if equip:
        st.selectbox("Status", STATUS_LIST, index=STATUS_LIST.index(equip.status), key=f"ct_f_status_{ctx}", disabled=True)
        st.selectbox("Localização atual", SETOR_IDS, index=SETOR_IDS.index(equip.setor),
                     format_func=lambda s: SETOR_NOMES[s], key=f"ct_f_setor_{ctx}", disabled=True)
        st.caption('Para mudar status/localização, use "Atualizar status" no painel de Detalhes — assim fica registrado no histórico.')
        acesso = st.selectbox("Acesso", ["Próprio", "Alugado"],
                               index=["Próprio", "Alugado"].index(equip.proprio_ou_alugado), key=f"ct_f_acesso_{ctx}")
    else:
        status_inicial = st.selectbox("Status", STATUS_LIST, key=f"ct_f_status_novo_{ctx}")
        setor_inicial = st.selectbox("Localização atual", SETOR_IDS, format_func=lambda s: SETOR_NOMES[s], key=f"ct_f_setor_novo_{ctx}")
        acesso = st.selectbox("Acesso", ["Próprio", "Alugado"], key=f"ct_f_acesso_novo_{ctx}")

    cA, cB = st.columns(2)
    if cA.button("Cancelar", use_container_width=True, key=f"ct_f_cancelar_{ctx}"):
        st.session_state["ct_equip_sel"] = None
        st.rerun()
    if cB.button("Salvar", type="primary", use_container_width=True, key=f"ct_f_salvar_{ctx}"):
        if equip:
            equip.tipo, equip.descricao, equip.proprio_ou_alugado = tipo, descricao, acesso
            _service.repo.salvar(equip)
            st.success("Dados atualizados.")
            st.rerun()
        else:
            if not numero_serie.strip() or not descricao.strip():
                st.warning("Preencha ao menos Numeração e Descrição.")
            else:
                novo = _service.criar_equipamento({
                    "numero_serie": numero_serie.strip(), "descricao": descricao.strip(),
                    "tipo": tipo, "proprio_ou_alugado": acesso,
                }, usuario=_usuario_atual())
                if status_inicial != "Recebido" or setor_inicial != "entrada":
                    _service.alterar_status(novo, status_inicial, setor_inicial, usuario=_usuario_atual(),
                                             observacao="Definido no cadastro.")
                st.session_state["ct_equip_sel"] = novo.id
                st.success(f"Equipamento {numero_serie} cadastrado.")
                st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)


# ============================================================
# PAINEL LATERAL — Detalhes do equipamento
# ============================================================
def _painel_detalhes(ctx="a"):
    equip = _service.buscar(st.session_state.get("ct_equip_sel")) if st.session_state.get("ct_equip_sel") else None
    st.markdown('<div class="ct-card"><div class="ct-card-h">Detalhes do equipamento</div>', unsafe_allow_html=True)
    if not equip:
        st.markdown('<div class="ct-empty">📦<br/>Selecione um setor no mapa ou um item na lista para ver os detalhes.</div>', unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
        return

    st.markdown(
        f"**Numeração:** {equip.numero_serie}  \n**Tipo:** {equip.tipo or '-'}  \n"
        f"**Status atual:** {_badge_status(equip.status)}  \n"
        f"**Localização atual:** {SETOR_NOMES.get(equip.setor, equip.setor)}  \n"
        f"**Acesso:** {equip.proprio_ou_alugado}",
        unsafe_allow_html=True,
    )

    with st.expander("🔄 Atualizar status"):
        novo_status = st.radio("Novo status", STATUS_LIST, horizontal=True, key=f"ct_novo_status_{ctx}")
        novo_setor = st.selectbox("Setor", SETOR_IDS, format_func=lambda s: SETOR_NOMES[s], key=f"ct_novo_setor_{ctx}")
        observacao = st.text_area("Observação (opcional)", max_chars=200, key=f"ct_obs_{ctx}")
        if st.button("Confirmar alteração", type="primary", use_container_width=True, key=f"ct_confirmar_alt_{ctx}"):
            st.session_state["ct_pendente"] = {
                "equip_id": equip.id, "novo_status": novo_status,
                "novo_setor": novo_setor, "observacao": observacao,
            }
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)


# ============================================================
# PAINEL LATERAL — Histórico de movimentações
# ============================================================
def _exportar_historico(equip, ctx):
    import pandas as pd
    linhas = [{
        "Data/Hora": ev.data_hora, "Status anterior": ev.status_anterior or "-",
        "Status novo": ev.status_novo, "Localização anterior": SETOR_NOMES.get(ev.setor_anterior, ev.setor_anterior or "-"),
        "Localização nova": SETOR_NOMES.get(ev.setor_novo, ev.setor_novo), "Usuário": ev.usuario,
        "Observação": ev.observacao,
    } for ev in equip.historico]
    df = pd.DataFrame(linhas)
    c1, c2 = st.columns(2)
    c1.download_button("⬇ CSV", df.to_csv(index=False).encode("utf-8"),
                        file_name=f"historico_{equip.numero_serie}.csv", mime="text/csv",
                        use_container_width=True, key=f"ct_exp_csv_{ctx}")
    buf = io.BytesIO()
    df.to_excel(buf, index=False, engine="openpyxl")
    c2.download_button("⬇ Excel", buf.getvalue(), file_name=f"historico_{equip.numero_serie}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True, key=f"ct_exp_xlsx_{ctx}")


def _painel_historico(ctx="a"):
    equip = _service.buscar(st.session_state.get("ct_equip_sel")) if st.session_state.get("ct_equip_sel") else None
    st.markdown('<div class="ct-card"><div class="ct-card-h">Histórico de movimentações</div>', unsafe_allow_html=True)
    if not equip or not equip.historico:
        st.markdown('<div class="ct-empty">Nenhuma movimentação para exibir ainda.</div>', unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
        return

    for ev in reversed(equip.historico):
        cor = STATUS_CORES.get(ev.status_novo, "#9a9a9a")
        st.markdown(
            f'<div class="ct-hist-item" style="color:{cor}">'
            f'<div class="ct-hist-dot" style="background:{cor}"></div>'
            f'<div class="ct-hist-date">{ev.data_hora}</div>'
            f'<div class="ct-hist-status">{ev.status_novo}</div>'
            f'<div class="ct-hist-obs">{SETOR_NOMES.get(ev.setor_novo, ev.setor_novo)} · Usuário: {ev.usuario}</div>'
            f'<div class="ct-hist-obs">{ev.observacao}</div></div>',
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown('<div class="ct-card"><div class="ct-card-h">Exportar histórico</div>', unsafe_allow_html=True)
    _exportar_historico(equip, ctx)
    st.markdown("</div>", unsafe_allow_html=True)


# ============================================================
# ABA "EQUIPAMENTOS" — filtros e listagem (seleção alimenta a coluna lateral)
# ============================================================
def _painel_lista():
    todos = _service.listar()
    if not todos:
        st.info('Nenhum equipamento cadastrado ainda. Use o painel "Cadastrar equipamento" ao lado.')
        return
    with st.expander("🔎 Filtros", expanded=False):
        c1, c2, c3, c4 = st.columns(4)
        f_serie = c1.text_input("Nº contém")
        f_status = c2.selectbox("Status", ["(todos)"] + STATUS_LIST)
        f_setor = c3.selectbox("Localização", ["(todos)"] + SETOR_IDS, format_func=lambda s: s if s == "(todos)" else SETOR_NOMES[s])
        f_acesso = c4.selectbox("Acesso", ["(todos)", "Próprio", "Alugado"])

    filtrados = todos
    if f_serie:
        filtrados = [e for e in filtrados if f_serie.lower() in e.numero_serie.lower()]
    if f_status != "(todos)":
        filtrados = [e for e in filtrados if e.status == f_status]
    if f_setor != "(todos)":
        filtrados = [e for e in filtrados if e.setor == f_setor]
    if f_acesso != "(todos)":
        filtrados = [e for e in filtrados if e.proprio_ou_alugado == f_acesso]

    st.caption(f"{len(filtrados)} equipamento(s)")
    for e in filtrados:
        col1, col2, col3 = st.columns([3, 2, 1])
        col1.markdown(f"**{e.descricao}**  \n`{e.numero_serie}`")
        col2.markdown(f"{_badge_status(e.status)} &nbsp; {SETOR_NOMES.get(e.setor,e.setor)}", unsafe_allow_html=True)
        if col3.button("Abrir", key=f"lst_open_{e.id}"):
            st.session_state["ct_equip_sel"] = e.id
            st.session_state["ct_setor_foco"] = e.setor
            st.rerun()


# ============================================================
# ABA "DASHBOARD"
# ============================================================
def _tempo_medio_por_setor(equipamentos):
    acumulado, contagem = {}, {}
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

    if st.session_state.get("ct_pendente"):
        _dialog_confirmar()

    st.markdown(
        '<div class="ct-title">CONTROLE — RASTREAMENTO DE EQUIPAMENTOS</div>'
        '<div class="ct-sub">Clique em um setor para ver os equipamentos ali alocados.</div>',
        unsafe_allow_html=True,
    )

    aba_mapa, aba_lista, aba_dash = st.tabs(["🗺️ Mapa", "📋 Equipamentos", "📊 Dashboard"])

    with aba_mapa:
        col_map, col_side = st.columns([2.1, 1])
        with col_map:
            st.markdown('<div class="ct-card"><div class="ct-card-h">Mapa de equipamentos</div>'
                        '<div class="ct-card-sub">Visão geral em tempo real da distribuição e movimentação dos equipamentos.</div>',
                        unsafe_allow_html=True)
            _render_mapa()
            st.markdown("</div>", unsafe_allow_html=True)
            c1, c2 = st.columns(2)
            with c1:
                _render_legenda()
            with c2:
                _render_resumo()
            _render_rastro_explicacao()
        with col_side:
            _painel_cadastro_editar(ctx="mapa")
            _painel_detalhes(ctx="mapa")
            _painel_historico(ctx="mapa")

    with aba_lista:
        col_l, col_side2 = st.columns([2.1, 1])
        with col_l:
            _painel_lista()
        with col_side2:
            _painel_cadastro_editar(ctx="lista")
            _painel_detalhes(ctx="lista")
            _painel_historico(ctx="lista")

    with aba_dash:
        _painel_dashboard()

    st.markdown("</div>", unsafe_allow_html=True)
