"""pages/controle/__init__.py — Módulo de Rastreamento Inteligente de Equipamentos.

Camadas:
    models.py     — dataclasses e constantes de domínio (setores, status, cores)
    repository.py — acesso a dados (hoje em session_state; troca marcada p/ Supabase)
    service.py    — regras de negócio (criação, transição de status/setor)
    ui.py         — telas Streamlit (mapa, detalhe, cadastro, dashboard)

app.py só precisa de: from pages.controle import tela_controle
"""
from .ui import tela_controle

__all__ = ["tela_controle"]
