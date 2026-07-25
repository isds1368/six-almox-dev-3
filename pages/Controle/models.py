"""pages/controle/models.py — Modelos de domínio do módulo de rastreamento.

Camada isolada: nenhuma dependência do Streamlit aqui. Só dados e regras
de nomenclatura/cores usadas pelas outras camadas (repository/service/ui).
"""
from dataclasses import dataclass, field
from typing import List, Optional

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
    "Quebrado": "#ef4444",
    "Em manutenção": "#eab308",
    "Substituído": "#f5f5f5",
    "Disponível": "#38bdf8",
    "Descartado": "#6b7280",
}
STATUS_LIST = list(STATUS_CORES.keys())

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
