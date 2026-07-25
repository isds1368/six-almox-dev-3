"""pages/controle/repository.py — Acesso a dados do módulo de rastreamento.

Hoje os dados vivem em st.session_state (funciona sem depender de nenhuma
tabela nova já existir no seu banco). Quando o schema equipment_tracking
(ver /schema/equipment_tracking_schema.sql) estiver criado no Supabase,
troque os métodos abaixo pelas chamadas reais — os pontos exatos estão
marcados com TODO. A camada acima (service.py) não muda nada.

Isolamento: nenhuma função aqui toca em tabelas do schema "public" usado
pelo resto do sistema (usuarios, produtos, movimentacoes...).
"""
from datetime import datetime
from typing import List, Optional

import streamlit as st

from .models import Equipamento, EventoHistorico

# from utils.database import get_sb  # TODO: descomentar quando for usar Supabase


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
