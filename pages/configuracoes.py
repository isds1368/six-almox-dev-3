"""pages/configuracoes.py"""
import streamlit as st
from utils.database import listar_configs,set_config,listar_categorias,criar_categoria,listar_setores,criar_setor,atualizar_setor

def tela_configuracoes():
    st.markdown('<div class="pg">', unsafe_allow_html=True)
    st.markdown('<div class="pg-title">⚙️ Configurações</div><div class="pg-sub">E-mail, setores e categorias</div>', unsafe_allow_html=True)
    t1,t2,t3=st.tabs(["E-mail","Setores","Categorias"])
    with t1: _email()
    with t2: _setores()
    with t3: _cats()
    st.markdown("</div>", unsafe_allow_html=True)

def _email():
    cfg=listar_configs()
    st.markdown('<div class="card"><div class="card-h">📧 E-mail Financeiro</div>', unsafe_allow_html=True)
    with st.form("fce"):
        c1,c2=st.columns(2)
        with c1:
            dest=st.text_input("E-mail destino *",value=cfg.get("email_financeiro","financeiro@empresa.com.br"))
            subj=st.text_input("Assunto",value=cfg.get("email_assunto","[NF] Nota Fiscal - SFC Almoxarifado"))
        with c2:
            assin=st.text_area("Assinatura",height=80,value=cfg.get("email_assinatura","Equipe de Almoxarifado"))
        corpo=st.text_area("Corpo",height=100,value=cfg.get("email_corpo","Prezados,\n\nSegue nota fiscal.\n\nAtenciosamente,"))
        if st.form_submit_button("Salvar →",type="primary"):
            set_config("email_financeiro",dest.strip())
            set_config("email_assunto",subj.strip())
            set_config("email_assinatura",assin.strip())
            set_config("email_corpo",corpo.strip())
            st.success("✅ Configurações salvas!")
    st.markdown("</div>", unsafe_allow_html=True)

def _setores():
    sets=listar_setores(apenas_ativos=False)
    st.markdown('<div class="card"><div class="card-h">🏢 Setores</div>', unsafe_allow_html=True)
    c1,c2=st.columns([2,1])
    with c1:
        rows="".join(f'<tr><td><strong>{s["nome"]}</strong></td><td style="text-align:center;">{"✅" if s["ativo"] else "❌"}</td></tr>' for s in sets)
        st.markdown(f'<table class="tbl"><thead><tr><th>Setor</th><th>Ativo</th></tr></thead><tbody>{rows or "<tr><td colspan=2 style=color:var(--t3);text-align:center;padding:1rem>Nenhum</td></tr>"}</tbody></table>', unsafe_allow_html=True)
    with c2:
        with st.form("fns"):
            nm=st.text_input("Novo setor")
            if st.form_submit_button("Adicionar →",type="primary"):
                if nm.strip():
                    try: criar_setor(nm.strip()); st.success("Adicionado!"); st.rerun()
                    except: st.error("Já existe.")
        if sets:
            with st.form("fts"):
                sel=st.selectbox("Ativar/Inativar",[s["nome"] for s in sets])
                if st.form_submit_button("Alternar"):
                    so=next(s for s in sets if s["nome"]==sel)
                    atualizar_setor(so["id"],{"ativo":not so["ativo"]}); st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

def _cats():
    cats=listar_categorias()
    st.markdown('<div class="card"><div class="card-h">🏷️ Categorias</div>', unsafe_allow_html=True)
    c1,c2=st.columns([2,1])
    with c1:
        rows="".join(f'<tr><td><strong>{c["nome"]}</strong></td><td style="color:var(--t3);">{c.get("descricao") or "—"}</td></tr>' for c in cats)
        st.markdown(f'<table class="tbl"><thead><tr><th>Categoria</th><th>Descrição</th></tr></thead><tbody>{rows or "<tr><td colspan=2 style=color:var(--t3);text-align:center;padding:1rem>Nenhuma</td></tr>"}</tbody></table>', unsafe_allow_html=True)
    with c2:
        with st.form("fnc"):
            nm=st.text_input("Nova categoria"); desc=st.text_input("Descrição")
            if st.form_submit_button("Adicionar →",type="primary"):
                if nm.strip():
                    try: criar_categoria(nm.strip(),desc.strip()); st.success("Adicionada!"); st.rerun()
                    except: st.error("Já existe.")
    st.markdown("</div>", unsafe_allow_html=True)
