"""app.py — SFC Almoxarifado"""
import streamlit as st
st.set_page_config(page_title="SFC Almoxarifado",page_icon="📦",layout="wide",initial_sidebar_state="collapsed")

from utils.ui   import inject_css,topbar,pagina_atual,navegar
from utils.auth import sessao,primeiro_acesso,pode
from pages.auth          import tela_login,tela_primeiro_acesso
from pages.dashboard     import tela_dashboard
from pages.entrada       import tela_entrada
from pages.saidas        import tela_solicitacoes,tela_saida_manual,tela_saida_aprovada
from pages.estoque       import tela_estoque
from pages.notas         import tela_notas
from pages.usuarios      import tela_usuarios
from pages.configuracoes import tela_configuracoes

def main():
    inject_css()
    u=sessao()
    if not u:
        if primeiro_acesso(): tela_primeiro_acesso()
        else: tela_login()
        return
    p=pagina_atual()
    topbar(p,u)
    rotas={
        "dashboard":     (tela_dashboard,    True),
        "entrada":       (tela_entrada,       pode("entrada")),
        "solicitacoes":  (tela_solicitacoes,  pode("solicitar")),
        "saida_manual":  (tela_saida_manual,  pode("saida_manual")),
        "saida_aprovada":(tela_saida_aprovada,pode("saida_aprovada")),
        "estoque":       (tela_estoque,       pode("estoque")),
        "notas":         (tela_notas,         pode("notas")),
        "usuarios":      (tela_usuarios,      pode("usuarios")),
        "configuracoes": (tela_configuracoes, pode("configuracoes")),
    }
    fn,ok=rotas.get(p,(tela_dashboard,True))
    if not ok: st.error("🔒 Sem permissão."); navegar("dashboard"); return
    fn()

if __name__=="__main__": main()
