"""pages/controle/service.py — Regras de negócio do módulo de rastreamento.

Nenhuma lógica de negócio deve viver nas telas (ui.py) — tudo passa por
aqui. Isso deixa o módulo testável e fácil de conectar num backend real.
"""
from typing import Optional

from .models import Equipamento, EventoHistorico
from .repository import EquipamentoRepository


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
