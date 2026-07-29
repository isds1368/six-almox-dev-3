"""pages/controle.py — Módulo de Rastreamento Inteligente de Equipamentos.

Arquivo único (sem subpastas) para simplificar deploy manual via GitHub.
Camadas dentro do mesmo arquivo: modelos, repository (Supabase), service, UI.
Ponto de entrada usado pelo app.py: tela_controle()

Requer utils/database.py com get_sb() e as tabelas do arquivo
/schema/equipamentos_controle_schema.sql já criadas no Supabase.
"""
import logging
from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime, date
import io

import streamlit as st
from utils.database import get_sb

_log = logging.getLogger("sfc.controle")

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

# Setor especial para onde equipamentos quebrados são movidos automaticamente
SETOR_PLANEJAMENTO = "plan"

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

# Status que força setor = Planejamento e exige motivo em texto livre
STATUS_QUEBRA = "Quebrado"

SITUACOES = ["Ativo", "Inativo", "Baixado"]

# ── Condição de uso do equipamento no setor onde está ───────────────────
CONDICAO_FIXO = "Fixo"
CONDICAO_EMPRESTIMO = "Empréstimo"
CONDICOES = [CONDICAO_FIXO, CONDICAO_EMPRESTIMO]

# Perfis com permissão para registrar entrada/saída/movimentação de equipamentos
PERFIS_COM_EDICAO = ("almoxarife", "admin", "administrador")


@dataclass
class EventoHistorico:
    data_hora: str
    status_anterior: Optional[str]
    status_novo: str
    setor_anterior: Optional[str]
    setor_novo: str
    usuario: str
    observacao: str = ""
    condicao: Optional[str] = None            # "Fixo" | "Empréstimo" | None
    devolucao_prevista: Optional[str] = None  # só relevante quando condicao == Empréstimo


@dataclass
class Equipamento:
    id: str
    numero_serie: str
    descricao: str = ""
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
    setor_fixo: Optional[str] = None          # setor "dono" do equipamento (definido pelo Planejamento)
    condicao: str = CONDICAO_FIXO             # condição de uso no setor atual
    devolucao_prevista: Optional[str] = None  # data prevista de devolução ao setor_fixo (se emprestado)
    historico: List[EventoHistorico] = field(default_factory=list)


# ============================================================
# 2. REPOSITORY
# ============================================================
_log = logging.getLogger("sfc.controle")

_TB_EQUIP = "equipamentos_controle"
_TB_HIST = "equipamentos_controle_historico"


# ── conversão de datas: telas usam "DD/MM/AAAA", banco usa "YYYY-MM-DD" ──
def _data_iso(v: Optional[str]) -> Optional[str]:
    if not v:
        return None
    try:
        return datetime.strptime(v, "%d/%m/%Y").strftime("%Y-%m-%d")
    except ValueError:
        return None


def _data_br(v: Optional[str]) -> Optional[str]:
    if not v:
        return None
    try:
        return datetime.strptime(str(v)[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
    except ValueError:
        return v


def _datahora_br(v: Optional[str]) -> str:
    if not v:
        return ""
    try:
        return datetime.fromisoformat(str(v).replace("Z", "+00:00")).strftime("%d/%m/%Y %H:%M")
    except ValueError:
        return str(v)


def _row_to_equip(row: dict) -> Equipamento:
    return Equipamento(
        id=row["id"], numero_serie=row.get("numero_serie", ""), descricao=row.get("descricao") or "",
        fabricante=row.get("fabricante") or "", modelo=row.get("modelo") or "",
        tipo=row.get("tipo") or "", categoria=row.get("categoria") or "",
        patrimonio=row.get("patrimonio") or "", proprio_ou_alugado=row.get("proprio_ou_alugado") or "Próprio",
        fornecedor=row.get("fornecedor") or "", data_aquisicao=row.get("data_aquisicao") or "",
        garantia_ate=row.get("garantia_ate") or "", observacoes=row.get("observacoes") or "",
        situacao=row.get("situacao") or "Ativo", status=row.get("status_atual") or "Recebido",
        setor=row.get("setor_atual") or "entrada", setor_fixo=row.get("setor_fixo"),
        condicao=row.get("condicao") or "Fixo", devolucao_prevista=_data_br(row.get("devolucao_prevista")),
        historico=[],
    )


def _row_to_evento(row: dict) -> EventoHistorico:
    return EventoHistorico(
        data_hora=_datahora_br(row.get("criado_em")), status_anterior=row.get("status_anterior"),
        status_novo=row.get("status_novo", ""), setor_anterior=row.get("setor_anterior"),
        setor_novo=row.get("setor_novo", ""), usuario=row.get("usuario_nick") or "usuário",
        observacao=row.get("observacao") or "", condicao=row.get("condicao"),
        devolucao_prevista=_data_br(row.get("devolucao_prevista")),
    )


def _equip_payload(equip: Equipamento) -> dict:
    return {
        "id": equip.id, "numero_serie": equip.numero_serie, "descricao": equip.descricao,
        "fabricante": equip.fabricante, "modelo": equip.modelo, "tipo": equip.tipo,
        "categoria": equip.categoria, "patrimonio": equip.patrimonio,
        "proprio_ou_alugado": equip.proprio_ou_alugado, "fornecedor": equip.fornecedor,
        "data_aquisicao": equip.data_aquisicao, "garantia_ate": equip.garantia_ate,
        "observacoes": equip.observacoes, "situacao": equip.situacao,
        "status_atual": equip.status, "setor_atual": equip.setor, "setor_fixo": equip.setor_fixo,
        "condicao": equip.condicao, "devolucao_prevista": _data_iso(equip.devolucao_prevista),
    }


class EquipamentoRepository:
    # ── LEITURA — nunca derruba a página: loga e volta vazio ─────────
    def listar(self) -> List[Equipamento]:
        try:
            rows = get_sb().table(_TB_EQUIP).select("*").order("criado_em").execute().data or []
        except Exception as e:
            _log.error("controle.listar: %s", e)
            return []
        equipamentos = [_row_to_equip(r) for r in rows]
        if not equipamentos:
            return equipamentos
        try:
            ids = [e.id for e in equipamentos]
            hist_rows = (get_sb().table(_TB_HIST).select("*")
                         .in_("equipamento_id", ids).order("criado_em").execute().data or [])
        except Exception as e:
            _log.error("controle.listar (historico): %s", e)
            hist_rows = []
        por_equip = {}
        for hr in hist_rows:
            por_equip.setdefault(hr["equipamento_id"], []).append(_row_to_evento(hr))
        for e in equipamentos:
            e.historico = por_equip.get(e.id, [])
        return equipamentos

    def buscar(self, equipamento_id: str) -> Optional[Equipamento]:
        if not equipamento_id:
            return None
        try:
            res = get_sb().table(_TB_EQUIP).select("*").eq("id", equipamento_id).execute().data
        except Exception as e:
            _log.error("controle.buscar: %s", e)
            return None
        if not res:
            return None
        equip = _row_to_equip(res[0])
        try:
            hist_rows = (get_sb().table(_TB_HIST).select("*")
                         .eq("equipamento_id", equipamento_id).order("criado_em").execute().data or [])
            equip.historico = [_row_to_evento(r) for r in hist_rows]
        except Exception as e:
            _log.error("controle.buscar (historico): %s", e)
        return equip

    # ── ESCRITA — loga e avisa a pessoa (igual criar_produto etc.) ───
    def proximo_id(self) -> str:
        try:
            n = get_sb().table(_TB_EQUIP).select("id", count="exact").execute().count or 0
        except Exception as e:
            _log.error("controle.proximo_id: %s", e)
            n = 0
        return f"EQ{n + 1:04d}"

    def salvar(self, equip: Equipamento):
        try:
            get_sb().table(_TB_EQUIP).upsert(_equip_payload(equip)).execute()
        except Exception as e:
            _log.error("controle.salvar: %s", e)
            st.error("❌ Não foi possível salvar o equipamento. Tente novamente.")

    def registrar_evento(self, equip: Equipamento, evento: EventoHistorico):
        self.salvar(equip)
        try:
            get_sb().table(_TB_HIST).insert({
                "equipamento_id": equip.id, "status_anterior": evento.status_anterior,
                "status_novo": evento.status_novo, "setor_anterior": evento.setor_anterior,
                "setor_novo": evento.setor_novo, "condicao": evento.condicao,
                "devolucao_prevista": _data_iso(evento.devolucao_prevista),
                "observacao": evento.observacao, "usuario_nick": evento.usuario,
            }).execute()
        except Exception as e:
            _log.error("controle.registrar_evento: %s", e)
            st.error("❌ Não foi possível gravar o histórico dessa alteração.")
        equip.historico.append(evento)  # mantém o objeto em memória coerente na mesma execução

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
    def listar(self) -> List[Equipamento]:
        return self.repo.listar()

    def buscar(self, equipamento_id: str) -> Optional[Equipamento]:
        return self.repo.buscar(equipamento_id)

    def buscar_por_serie(self, numero_serie: str) -> Optional[Equipamento]:
        numero_serie = (numero_serie or "").strip().lower()
        for e in self.listar():
            if e.numero_serie.strip().lower() == numero_serie:
                return e
        return None

    def por_setor(self, setor_id: str) -> List[Equipamento]:
        return [e for e in self.listar() if e.setor == setor_id and e.situacao != "Baixado"]

    def emprestimos_pendentes(self) -> List[Equipamento]:
        return [e for e in self.listar() if e.condicao == CONDICAO_EMPRESTIMO and e.devolucao_prevista]

    # ── CADASTRO EM LOTE (entrada — só Planejamento/Controladoria) ──
    # Regra: nunca recadastra um número de série já existente — em vez
    # disso, alimenta um NOVO ciclo no histórico do equipamento já
    # existente (isso é o que sustenta os indicadores de SLA de uso).
    def cadastrar_lote(self, numeros_serie: List[str], tipo: str, descricao: str,
                        acesso: str, setor_destino: str, usuario: str) -> dict:
        criados, reabertos, ignorados = [], [], []
        for bruto in numeros_serie:
            numero = (bruto or "").strip()
            if not numero:
                continue
            existente = self.buscar_por_serie(numero)
            if existente:
                self._registrar_novo_ciclo(existente, setor_destino, usuario)
                reabertos.append(existente)
            else:
                novo = Equipamento(
                    id=self.repo.proximo_id(), numero_serie=numero, descricao=descricao,
                    tipo=tipo, proprio_ou_alugado=acesso, situacao="Ativo",
                    status="Recebido", setor=setor_destino, setor_fixo=setor_destino,
                    condicao=CONDICAO_FIXO,
                )
                evento = EventoHistorico(
                    data_hora=self.repo.agora(), status_anterior=None, status_novo="Recebido",
                    setor_anterior=None, setor_novo=setor_destino, usuario=usuario,
                    observacao="Equipamento recebido e designado pelo Planejamento.",
                    condicao=CONDICAO_FIXO,
                )
                self.repo.registrar_evento(novo, evento)
                criados.append(novo)
        return {"criados": criados, "reabertos": reabertos, "ignorados": ignorados}

    def _registrar_novo_ciclo(self, equip: Equipamento, setor_destino: str, usuario: str):
        """Equipamento que já existia (saiu e voltou à empresa) — mantém
        o histórico completo, só acrescenta um novo evento de entrada."""
        evento = EventoHistorico(
            data_hora=self.repo.agora(), status_anterior=equip.status, status_novo="Recebido",
            setor_anterior=equip.setor, setor_novo=setor_destino, usuario=usuario,
            observacao="Novo ciclo de entrada registrado pelo Planejamento (equipamento já existente).",
            condicao=CONDICAO_FIXO,
        )
        equip.status = "Recebido"
        equip.setor = setor_destino
        equip.setor_fixo = setor_destino
        equip.condicao = CONDICAO_FIXO
        equip.devolucao_prevista = None
        equip.situacao = "Ativo"
        self.repo.registrar_evento(equip, evento)

    # ── TRANSIÇÃO DE STATUS (via painel "Atualizar status") ─────────
    def alterar_status(self, equip: Equipamento, novo_status: str, novo_setor: str,
                        usuario: str, observacao: str = ""):
        # Regra: equipamento quebrado vai automaticamente para o Planejamento,
        # não importa em qual setor foi apontado como quebrado.
        if novo_status == STATUS_QUEBRA:
            novo_setor = SETOR_PLANEJAMENTO

        status_anterior, setor_anterior = equip.status, equip.setor
        evento = EventoHistorico(
            data_hora=self.repo.agora(), status_anterior=status_anterior, status_novo=novo_status,
            setor_anterior=setor_anterior, setor_novo=novo_setor, usuario=usuario, observacao=observacao,
        )
        equip.status = novo_status
        equip.setor = novo_setor
        if novo_status == "Descartado":
            equip.situacao = "Baixado"
        self.repo.registrar_evento(equip, evento)
        return equip

    # ── "INFORMAR EQUIPAMENTO NESTE SETOR" (fluxo do clique no mapa) ─
    def setor_diverge_do_fixo(self, equip: Equipamento, setor_destino: str) -> bool:
        return bool(equip.setor_fixo) and equip.setor_fixo != setor_destino

    def informar_equipamento_no_setor(self, equip: Equipamento, setor_destino: str, usuario: str,
                                       condicao: str = CONDICAO_FIXO,
                                       devolucao_prevista: Optional[str] = None, observacao: str = ""):
        status_anterior, setor_anterior = equip.status, equip.setor
        evento = EventoHistorico(
            data_hora=self.repo.agora(), status_anterior=status_anterior, status_novo="Em uso",
            setor_anterior=setor_anterior, setor_novo=setor_destino, usuario=usuario,
            observacao=observacao, condicao=condicao,
            devolucao_prevista=devolucao_prevista if condicao == CONDICAO_EMPRESTIMO else None,
        )
        equip.status = "Em uso"
        equip.setor = setor_destino
        equip.condicao = condicao
        equip.devolucao_prevista = devolucao_prevista if condicao == CONDICAO_EMPRESTIMO else None
        if condicao == CONDICAO_FIXO:
            equip.setor_fixo = setor_destino  # reatribuição de propriedade do equipamento
        self.repo.registrar_evento(equip, evento)
        return equip


# ============================================================
# 4. UI
# ============================================================
_service = EquipamentoService()

# ============================================================
# CSS — tema premium (fundo preto, neon vermelho, glass, glow)
# ============================================================
_CSS = """<style>
.ct-wrap{--ct-red:#ef4444;--ct-bg:#050506;--ct-glass:rgba(18,8,8,.55);--ct-bdr:rgba(239,68,68,.5);
font-family:'Plus Jakarta Sans',sans-serif;}
.ct-wrap .ct-title{font-size:1.15rem;font-weight:800;letter-spacing:.08em;text-transform:uppercase;
color:#fff;text-shadow:0 0 12px rgba(239,68,68,.65);margin-bottom:.15rem;}
.ct-wrap .ct-sub{font-size:.72rem;color:#9a9a9a;margin-bottom:1rem;}
.ct-wrap .ct-card{background:var(--ct-glass);border:1.5px solid var(--ct-bdr);border-radius:12px;
padding:1rem 1.1rem;margin-bottom:.9rem;backdrop-filter:blur(6px);box-shadow:0 0 16px rgba(239,68,68,.14);}
.ct-wrap .ct-card-h{font-size:.72rem;font-weight:800;letter-spacing:.1em;text-transform:uppercase;
color:var(--ct-red);margin-bottom:.7rem;padding-bottom:.45rem;border-bottom:1px solid var(--ct-bdr);}
.ct-wrap .ct-card-sub{font-size:.68rem;color:#888;margin-top:-.5rem;margin-bottom:.7rem;}
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
.ct-wrap .ct-kpi-row{display:flex;gap:.7rem;flex-wrap:wrap;}
.ct-wrap .ct-kpi{flex:1;min-width:110px;text-align:center;}
.ct-wrap .ct-kpi-ico{font-size:1.1rem;}
.ct-wrap .ct-kpi-val{font-size:1.4rem;font-weight:800;color:#fff;text-shadow:0 0 8px rgba(239,68,68,.5);}
.ct-wrap .ct-kpi-label{font-size:.6rem;color:#9a9a9a;text-transform:uppercase;letter-spacing:.05em;}
.ct-wrap .ct-leg-item{display:flex;align-items:center;gap:.4rem;font-size:.74rem;color:#ddd;margin-bottom:.4rem;}
.ct-wrap .ct-dot{width:9px;height:9px;border-radius:50%;box-shadow:0 0 6px currentColor;flex-shrink:0;}
.ct-wrap .ct-badge{display:inline-flex;align-items:center;gap:.3rem;padding:.15rem .55rem;border-radius:20px;
font-size:.62rem;font-weight:700;text-transform:uppercase;letter-spacing:.05em;border:1px solid currentColor;}
.ct-wrap .ct-hist-item{border-left:2px solid var(--ct-bdr);padding:.1rem 0 .85rem 1rem;margin-left:.3rem;position:relative;}
.ct-wrap .ct-hist-dot{position:absolute;left:-6.5px;top:2px;width:11px;height:11px;border-radius:50%;box-shadow:0 0 8px currentColor;}
.ct-wrap .ct-hist-date{font-size:.66rem;color:#9a9a9a;}
.ct-wrap .ct-hist-status{font-weight:700;color:#fff;font-size:.82rem;}
.ct-wrap .ct-hist-obs{font-size:.7rem;color:#b5b5b5;}
.ct-wrap .ct-empty{color:#777;font-size:.78rem;text-align:center;padding:1.2rem 0;}
.ct-wrap .ct-alerta{background:rgba(245,158,11,.12);border:1px solid rgba(245,158,11,.5);border-radius:8px;
padding:.5rem .7rem;font-size:.74rem;color:#fbbf24;margin-bottom:.4rem;}
.ct-wrap .ct-alerta.atrasado{background:rgba(239,68,68,.14);border-color:rgba(239,68,68,.6);color:#f87171;}
</style>"""


# ============================================================
# PERMISSÕES — só Almoxarife/Administrador registram entrada/saída
# ============================================================
def _perfil_atual():
    try:
        from utils.auth import sessao
        u = sessao()
        return (u or {}).get("perfil")
    except Exception:
        return None  # ambiente sem utils.auth (ex.: testes) — tratado como permitido abaixo


def _pode_editar() -> bool:
    perfil = _perfil_atual()
    if perfil is None:
        return True  # fallback de desenvolvimento/teste
    return perfil in PERFIS_COM_EDICAO


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
# RASTRO VISUAL — roteado por pontos-âncora fixos por setor (invisíveis)
# ============================================================
_LARGURA, _ALTURA = 900, 230

# Um ponto-âncora fixo por setor: onde o "cabo" desse setor encosta no
# canvas. Nunca são desenhados como círculos — só definem a rota da linha.
def _ancoras():
    return {
        "transfer": (_LARGURA * 0.28, 0),
        "ecom": (_LARGURA * 0.72, 0),
        "par": (0, _ALTURA * 0.5),
        "entrada": (_LARGURA * 0.20, _ALTURA),
        "receb": (_LARGURA * 0.55, _ALTURA),
        "plan": (_LARGURA * 0.85, _ALTURA),
    }


def _rota_ortogonal(p1, p2):
    x1, y1 = p1
    x2, y2 = p2
    my = _ALTURA / 2
    return f"M{x1},{y1} L{x1},{my} L{x2},{my} L{x2},{y2}"


def _render_canvas(equip=None, mostrar_rastro=False):
    ancoras = _ancoras()
    partes = [
        f'<svg viewBox="0 0 {_LARGURA} {_ALTURA}" xmlns="http://www.w3.org/2000/svg">',
        '<defs><filter id="ctglow" x="-60%" y="-60%" width="220%" height="220%">'
        '<feGaussianBlur stdDeviation="4" result="b"/>'
        '<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>'
        '<marker id="ctarrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" '
        'orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#fff"/></marker></defs>',
        '<style>.ctdash{stroke-dasharray:8,7;animation:ctd 1.1s linear infinite}'
        '@keyframes ctd{to{stroke-dashoffset:-30}}</style>',
        f'<rect x="0" y="0" width="{_LARGURA}" height="{_ALTURA}" fill="#050506"/>',
    ]
    for gx in range(0, _LARGURA, 45):
        partes.append(f'<line x1="{gx}" y1="0" x2="{gx}" y2="{_ALTURA}" stroke="#161616" stroke-width="1"/>')
    for gy in range(0, _ALTURA, 45):
        partes.append(f'<line x1="0" y1="{gy}" x2="{_LARGURA}" y2="{gy}" stroke="#161616" stroke-width="1"/>')

    if mostrar_rastro and equip and equip.historico:
        setores_visitados = [ev.setor_novo for ev in equip.historico if ev.setor_novo in ancoras]
        for i in range(len(setores_visitados) - 1):
            p1 = ancoras[setores_visitados[i]]
            p2 = ancoras[setores_visitados[i + 1]]
            cor = STATUS_CORES.get(equip.historico[i + 1].status_novo, "#ef4444")
            partes.append(
                f'<path d="{_rota_ortogonal(p1, p2)}" fill="none" stroke="{cor}" stroke-width="2.5" '
                f'class="ctdash" filter="url(#ctglow)" marker-end="url(#ctarrow)"/>'
            )
        # marca só o ponto ATUAL (posição de agora do equipamento) — os
        # pontos-âncora em si permanecem invisíveis, como pedido.
        if setores_visitados:
            x, y = ancoras[setores_visitados[-1]]
            cor_atual = STATUS_CORES.get(equip.status, "#ef4444")
            partes.append(f'<circle cx="{x}" cy="{y}" r="9" fill="{cor_atual}" filter="url(#ctglow)"/>')
            partes.append(
                f'<text x="{x}" y="{y-16}" font-size="10" text-anchor="middle" fill="#fff" '
                f'font-family="sans-serif">{SETOR_NOMES.get(setores_visitados[-1], "")}</text>'
            )
    else:
        partes.append(
            f'<text x="{_LARGURA/2}" y="{_ALTURA/2}" font-size="13" text-anchor="middle" '
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
        'visual no mapa e no histórico do equipamento — inclusive movimentações de empréstimo entre setores.</div>',
        unsafe_allow_html=True,
    )
    legenda = ["Recebido", "Em uso", "Em traslado", "Quebrado", "Substituído"]
    cols = st.columns(len(legenda))
    for col, status in zip(cols, legenda):
        cor = STATUS_CORES[status]
        col.markdown(
            f'<div class="ct-leg-item"><span class="ct-dot" style="background:{cor};color:{cor}"></span>{status}</div>',
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)


def _render_emprestimos_pendentes():
    pendentes = _service.emprestimos_pendentes()
    if not pendentes:
        return
    st.markdown('<div class="ct-card"><div class="ct-card-h">🔔 Empréstimos pendentes de devolução</div>', unsafe_allow_html=True)
    hoje = date.today()
    for e in pendentes:
        try:
            venc = datetime.strptime(e.devolucao_prevista, "%d/%m/%Y").date()
            atrasado = venc < hoje
        except ValueError:
            atrasado = False
        classe = "ct-alerta atrasado" if atrasado else "ct-alerta"
        situacao_txt = "ATRASADO" if atrasado else "no prazo"
        st.markdown(
            f'<div class="{classe}">{e.numero_serie} — {e.descricao or e.tipo} está em '
            f'{SETOR_NOMES.get(e.setor, e.setor)}, deve devolver a {SETOR_NOMES.get(e.setor_fixo, e.setor_fixo)} '
            f'até {e.devolucao_prevista} ({situacao_txt})</div>',
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)


# ============================================================
# AÇÕES DO SETOR SELECIONADO — lista + "Informar equipamento"
# ============================================================
@st.dialog("Equipamento de outro setor")
def _dialog_setor_divergente():
    p = st.session_state.get("ct_pendente_setor")
    if not p:
        st.stop()
    equip = _service.buscar(p["equip_id"])
    st.warning(
        f"O equipamento **{equip.numero_serie}** pertence ao setor "
        f"**{SETOR_NOMES.get(equip.setor_fixo, equip.setor_fixo)}**. "
        f"Deseja mesmo registrá-lo em **{SETOR_NOMES.get(p['setor_destino'], p['setor_destino'])}**?"
    )
    condicao = st.radio("Condição", CONDICOES, horizontal=True, key="ct_cond_div")
    devolucao = None
    if condicao == CONDICAO_EMPRESTIMO:
        devolucao = st.date_input("Data prevista de devolução", key="ct_dev_div")
    c1, c2 = st.columns(2)
    if c1.button("Cancelar", use_container_width=True, key="ct_div_cancelar"):
        st.session_state.pop("ct_pendente_setor", None)
        st.rerun()
    if c2.button("Confirmar", type="primary", use_container_width=True, key="ct_div_confirmar"):
        dev_str = devolucao.strftime("%d/%m/%Y") if (condicao == CONDICAO_EMPRESTIMO and devolucao) else None
        _service.informar_equipamento_no_setor(
            equip, p["setor_destino"], usuario=_usuario_atual(), condicao=condicao,
            devolucao_prevista=dev_str, observacao="Registrado via mapa (setor divergente do setor fixo).",
        )
        st.session_state.pop("ct_pendente_setor", None)
        st.session_state["ct_equip_sel"] = equip.id
        st.success("Equipamento registrado no setor.")
        st.rerun()


def _render_setor_focus():
    setor_id = st.session_state.get("ct_setor_foco")
    if not setor_id:
        return
    equipamentos = _service.por_setor(setor_id)
    st.markdown(
        f'<div class="ct-card"><div class="ct-card-h">Setor selecionado: {SETOR_NOMES[setor_id]}</div>',
        unsafe_allow_html=True,
    )
    if st.button("✕ Fechar setor", key="ct_fechar_setor"):
        st.session_state["ct_setor_foco"] = None
        st.rerun()

    if not equipamentos:
        st.markdown('<div class="ct-empty">Nenhum equipamento neste setor no momento.</div>', unsafe_allow_html=True)
    for e in equipamentos:
        col1, col2 = st.columns([4, 1])
        col1.markdown(f"**{e.numero_serie}** — {e.descricao or e.tipo}  \n{_badge_status(e.status)} · {e.condicao}", unsafe_allow_html=True)
        if col2.button("Ver", key=f"foco_ver_{e.id}"):
            st.session_state["ct_equip_sel"] = e.id
            st.rerun()

    if _pode_editar():
        st.markdown("---")
        todos = _service.listar()
        if todos:
            opcoes = {f"{e.numero_serie} — {e.descricao or e.tipo}": e.id for e in todos}
            escolha = st.selectbox("Informar equipamento neste setor", list(opcoes.keys()), key="ct_informar_sel")
            if st.button("Registrar neste setor", key="ct_informar_btn"):
                equip = _service.buscar(opcoes[escolha])
                if _service.setor_diverge_do_fixo(equip, setor_id):
                    st.session_state["ct_pendente_setor"] = {"equip_id": equip.id, "setor_destino": setor_id}
                    st.rerun()
                else:
                    _service.informar_equipamento_no_setor(
                        equip, setor_id, usuario=_usuario_atual(), condicao=CONDICAO_FIXO,
                        observacao="Registrado via mapa.",
                    )
                    st.session_state["ct_equip_sel"] = equip.id
                    st.success("Equipamento registrado.")
                    st.rerun()
        else:
            st.caption("Nenhum equipamento cadastrado ainda pelo Planejamento.")
    else:
        st.caption("Apenas Almoxarife/Administrador podem registrar equipamentos em um setor.")
    st.markdown("</div>", unsafe_allow_html=True)


# ============================================================
# CONFIRMAÇÃO DE ALTERAÇÃO DE STATUS (dialog)
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
# PAINEL LATERAL — Cadastro em lote (só Almoxarife/Administrador)
# ============================================================
def _painel_cadastro_lote(ctx="a"):
    st.markdown('<div class="ct-card"><div class="ct-card-h">Cadastrar equipamentos (entrada em lote)</div>', unsafe_allow_html=True)
    if not _pode_editar():
        st.caption("Apenas Almoxarife/Administrador podem registrar entrada de equipamentos.")
        st.markdown("</div>", unsafe_allow_html=True)
        return
    st.caption("Tipo, descrição e acesso valem para todos os números de série informados abaixo.")
    tipo = st.text_input("Tipo", key=f"ct_lote_tipo_{ctx}")
    descricao = st.text_input("Descrição", key=f"ct_lote_desc_{ctx}")
    acesso = st.selectbox("Acesso", ["Próprio", "Alugado"], key=f"ct_lote_acesso_{ctx}")
    setor_destino = st.selectbox("Setor de destino (designado pelo Planejamento)", SETOR_IDS,
                                  format_func=lambda s: SETOR_NOMES[s], key=f"ct_lote_setor_{ctx}")
    numeros_txt = st.text_area("Números de série (um por linha)", key=f"ct_lote_numeros_{ctx}", height=100)

    if st.button("Registrar entrada", type="primary", use_container_width=True, key=f"ct_lote_salvar_{ctx}"):
        numeros = [n for n in numeros_txt.splitlines() if n.strip()]
        if not numeros or not descricao.strip():
            st.warning("Informe a descrição e ao menos um número de série.")
        else:
            resultado = _service.cadastrar_lote(numeros, tipo, descricao, acesso, setor_destino, usuario=_usuario_atual())
            msgs = []
            if resultado["criados"]:
                msgs.append(f"{len(resultado['criados'])} novo(s) cadastrado(s)")
            if resultado["reabertos"]:
                msgs.append(f"{len(resultado['reabertos'])} já existente(s) — novo ciclo registrado no histórico")
            st.success(" · ".join(msgs) if msgs else "Nada para registrar.")
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)


# ============================================================
# PAINEL LATERAL — Detalhes do equipamento selecionado
# ============================================================
def _painel_detalhes(ctx="a"):
    equip = _service.buscar(st.session_state.get("ct_equip_sel")) if st.session_state.get("ct_equip_sel") else None
    st.markdown('<div class="ct-card"><div class="ct-card-h">Detalhes do equipamento</div>', unsafe_allow_html=True)
    if not equip:
        st.markdown('<div class="ct-empty">📦<br/>Clique num setor no mapa e selecione um equipamento para ver os detalhes.</div>', unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
        return

    linha_emp = ""
    if equip.condicao == CONDICAO_EMPRESTIMO and equip.devolucao_prevista:
        linha_emp = f"  \n**Devolução prevista:** {equip.devolucao_prevista} → {SETOR_NOMES.get(equip.setor_fixo, equip.setor_fixo)}"
    st.markdown(
        f"**Numeração:** {equip.numero_serie}  \n**Tipo:** {equip.tipo or '-'}  \n"
        f"**Status atual:** {_badge_status(equip.status)}  \n"
        f"**Localização atual:** {SETOR_NOMES.get(equip.setor, equip.setor)}  \n"
        f"**Setor fixo (dono):** {SETOR_NOMES.get(equip.setor_fixo, equip.setor_fixo) if equip.setor_fixo else '-'}  \n"
        f"**Condição:** {equip.condicao}{linha_emp}  \n**Acesso:** {equip.proprio_ou_alugado}",
        unsafe_allow_html=True,
    )

    if not _pode_editar():
        st.caption("Apenas Almoxarife/Administrador podem alterar o status.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    with st.expander("🔄 Atualizar status"):
        novo_status = st.radio("Novo status", STATUS_LIST, horizontal=True, key=f"ct_novo_status_{ctx}")
        motivo_quebra = ""
        if novo_status == STATUS_QUEBRA:
            st.info("Equipamentos quebrados são movidos automaticamente para o setor Planejamento.")
            motivo_quebra = st.text_area("Descreva a quebra (obrigatório)", key=f"ct_motivo_quebra_{ctx}")
            novo_setor = "plan"
        else:
            novo_setor = st.selectbox("Setor", SETOR_IDS, format_func=lambda s: SETOR_NOMES[s], key=f"ct_novo_setor_{ctx}")
        observacao = st.text_area("Observação (opcional)", max_chars=200, key=f"ct_obs_{ctx}")
        if st.button("Confirmar alteração", type="primary", use_container_width=True, key=f"ct_confirmar_alt_{ctx}"):
            if novo_status == STATUS_QUEBRA and not motivo_quebra.strip():
                st.warning("Descreva o motivo da quebra antes de confirmar.")
            else:
                obs_final = f"Motivo da quebra: {motivo_quebra.strip()}" if novo_status == STATUS_QUEBRA else observacao
                st.session_state["ct_pendente"] = {
                    "equip_id": equip.id, "novo_status": novo_status,
                    "novo_setor": novo_setor, "observacao": obs_final,
                }
                st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)


# ============================================================
# PAINEL LATERAL — Histórico de movimentações
# ============================================================
def _exportar_historico(equip, ctx="a"):
    import pandas as pd
    linhas = [{
        "Data/Hora": ev.data_hora, "Status anterior": ev.status_anterior or "-",
        "Status novo": ev.status_novo, "Localização anterior": SETOR_NOMES.get(ev.setor_anterior, ev.setor_anterior or "-"),
        "Localização nova": SETOR_NOMES.get(ev.setor_novo, ev.setor_novo), "Condição": ev.condicao or "-",
        "Devolução prevista": ev.devolucao_prevista or "-", "Usuário": ev.usuario, "Observação": ev.observacao,
    } for ev in equip.historico]
    df = pd.DataFrame(linhas)
    c1, c2 = st.columns(2)
    c1.download_button("⬇ CSV", df.to_csv(index=False).encode("utf-8"),
                        file_name=f"historico_{equip.numero_serie}.csv", mime="text/csv",
                        use_container_width=True, key=f"ct_exp_csv_{ctx}")
    buf = io.BytesIO()
    df.to_excel(buf, index=False, engine="openpyxl")
    c2.download_button("⬇ Excel (vida útil)", buf.getvalue(), file_name=f"historico_{equip.numero_serie}.xlsx",
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
        cond_txt = f" · {ev.condicao}" if ev.condicao else ""
        st.markdown(
            f'<div class="ct-hist-item" style="color:{cor}">'
            f'<div class="ct-hist-dot" style="background:{cor}"></div>'
            f'<div class="ct-hist-date">{ev.data_hora}</div>'
            f'<div class="ct-hist-status">{ev.status_novo}</div>'
            f'<div class="ct-hist-obs">{SETOR_NOMES.get(ev.setor_novo, ev.setor_novo)}{cond_txt} · Usuário: {ev.usuario}</div>'
            f'<div class="ct-hist-obs">{ev.observacao}</div></div>',
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown('<div class="ct-card"><div class="ct-card-h">Exportar vida útil</div>', unsafe_allow_html=True)
    _exportar_historico(equip, ctx)
    st.markdown("</div>", unsafe_allow_html=True)


# ============================================================
# ABA "EQUIPAMENTOS" — filtros e listagem
# ============================================================
def _painel_lista():
    todos = _service.listar()
    if not todos:
        st.info('Nenhum equipamento cadastrado ainda.')
        return
    with st.expander("🔎 Filtros", expanded=False):
        c1, c2, c3, c4 = st.columns(4)
        f_serie = c1.text_input("Nº contém")
        f_status = c2.selectbox("Status", ["(todos)"] + STATUS_LIST)
        f_setor = c3.selectbox("Localização", ["(todos)"] + SETOR_IDS, format_func=lambda s: s if s == "(todos)" else SETOR_NOMES[s])
        f_condicao = c4.selectbox("Condição", ["(todos)"] + CONDICOES)

    filtrados = todos
    if f_serie:
        filtrados = [e for e in filtrados if f_serie.lower() in e.numero_serie.lower()]
    if f_status != "(todos)":
        filtrados = [e for e in filtrados if e.status == f_status]
    if f_setor != "(todos)":
        filtrados = [e for e in filtrados if e.setor == f_setor]
    if f_condicao != "(todos)":
        filtrados = [e for e in filtrados if e.condicao == f_condicao]

    st.caption(f"{len(filtrados)} equipamento(s)")
    for e in filtrados:
        col1, col2, col3 = st.columns([3, 2, 1])
        col1.markdown(f"**{e.numero_serie}**  \n{e.descricao or e.tipo}")
        col2.markdown(f"{_badge_status(e.status)} &nbsp; {SETOR_NOMES.get(e.setor,e.setor)} &nbsp; · {e.condicao}", unsafe_allow_html=True)
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
    por_status = {s: sum(1 for e in todos if e.status == s) for s in STATUS_LIST}
    proprios = sum(1 for e in todos if e.proprio_ou_alugado == "Próprio")
    alugados = len(todos) - proprios

    _render_emprestimos_pendentes()
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
    if st.session_state.get("ct_pendente_setor"):
        _dialog_setor_divergente()

    st.markdown(
        '<div class="ct-title">CONTROLE — RASTREAMENTO DE EQUIPAMENTOS</div>'
        '<div class="ct-sub">Clique em um setor para ver e registrar os equipamentos ali alocados.</div>',
        unsafe_allow_html=True,
    )

    aba_mapa, aba_lista, aba_dash = st.tabs(["🗺️ Mapa", "📋 Equipamentos", "📊 Dashboard"])

    with aba_mapa:
        col_map, col_side = st.columns([2.1, 1])
        with col_map:
            st.markdown(
                '<div class="ct-card"><div class="ct-card-h">Mapa de equipamentos</div>'
                '<div class="ct-card-sub">Visão geral em tempo real da distribuição e movimentação dos equipamentos.</div>',
                unsafe_allow_html=True,
            )
            _render_mapa()
            st.markdown("</div>", unsafe_allow_html=True)
            _render_setor_focus()
            _render_resumo()
            _render_rastro_explicacao()
        with col_side:
            _painel_cadastro_lote(ctx="mapa")
            _painel_detalhes(ctx="mapa")
            _painel_historico(ctx="mapa")

    with aba_lista:
        col_l, col_side2 = st.columns([2.1, 1])
        with col_l:
            _painel_lista()
        with col_side2:
            _painel_cadastro_lote(ctx="lista")
            _painel_detalhes(ctx="lista")
            _painel_historico(ctx="lista")

    with aba_dash:
        _painel_dashboard()

    st.markdown("</div>", unsafe_allow_html=True)
