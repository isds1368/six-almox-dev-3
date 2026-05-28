"""pages/usuarios.py — Gestão de Usuários com nick/perfil"""
import streamlit as st
from utils.database import listar_usuarios,criar_usuario,atualizar_usuario,buscar_por_nick
from utils.auth import hash_senha,sessao
from utils.ui import badge,kpi_html
from utils.fmt import datahora_br

PERFIS   = ["admin","almoxarife","usuario"]
P_LABEL  = {"admin":"Administrador","almoxarife":"Almoxarife","usuario":"Usuário"}
P_COR    = {"admin":"var(--err)","almoxarife":"var(--warn)","usuario":"var(--info)"}

def tela_usuarios():
    st.markdown('<div class="pg">', unsafe_allow_html=True)
    st.markdown('<div class="pg-title">👥 Gestão de Usuários</div><div class="pg-sub">Cadastre e gerencie acessos ao sistema</div>', unsafe_allow_html=True)
    t1,t2=st.tabs(["Usuários","Novo Usuário"])
    with t1: _listar()
    with t2: _cadastrar()
    st.markdown("</div>", unsafe_allow_html=True)

def _listar():
    ul=sessao(); us=listar_usuarios()
    at=sum(1 for u in us if u["ativo"]); it=len(us)-at
    st.markdown(f'<div class="kpis" style="grid-template-columns:repeat(3,1fr);margin-bottom:1rem;">{kpi_html("Total",len(us),"","var(--t2)")}{kpi_html("Ativos",at,"","var(--ok)")}{kpi_html("Inativos",it,"","var(--t3)")}</div>', unsafe_allow_html=True)
    st.markdown('<div class="card"><div class="card-h">Lista de Usuários</div>', unsafe_allow_html=True)
    rows=""
    for u in us:
        bx=badge("Ativo","ok") if u["ativo"] else badge("Inativo","cancelado")
        cor=P_COR.get(u["perfil"],"var(--t3)")
        rows+=f'<tr><td class="mono">{u["nick"]}</td><td style="color:var(--t3);">{u.get("nome") or "—"}</td><td style="color:{cor};font-weight:600;font-size:.76rem;">{P_LABEL.get(u["perfil"],"—")}</td><td style="color:var(--t3);">{u.get("email") or "—"}</td><td>{bx}</td><td style="color:var(--t3);font-size:.73rem;">{datahora_br(u["criado_em"])}</td></tr>'
    st.markdown(f'<table class="tbl"><thead><tr><th>Nick</th><th>Nome</th><th>Perfil</th><th>E-mail</th><th>Status</th><th>Criado em</th></tr></thead><tbody>{rows}</tbody></table>', unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    outros=[u for u in us if u["id"]!=ul["id"]]
    if outros:
        with st.expander("✏️ Editar usuário"):
            um={f"{u['nick']} ({P_LABEL.get(u['perfil'],'')})":u for u in outros}
            sel=st.selectbox("Selecione",list(um.keys()),key="seu")
            us_=um[sel]
            with st.form("feu"):
                c1,c2=st.columns(2)
                with c1:
                    ne=st.text_input("Nome completo",value=us_.get("nome") or "")
                    ee=st.text_input("E-mail",value=us_.get("email") or "")
                with c2:
                    pe=st.selectbox("Perfil",PERFIS,
                        index=PERFIS.index(us_["perfil"]) if us_["perfil"] in PERFIS else 2,
                        format_func=lambda x:P_LABEL[x])
                    ae=st.selectbox("Status",["ativo","inativo"],
                        index=0 if us_["ativo"] else 1)
                    nsp=st.text_input("Nova senha (em branco = manter)",type="password")
                if st.form_submit_button("Salvar →",type="primary"):
                    d={"nome":ne.strip() or None,"email":ee.strip() or None,"perfil":pe,"ativo":ae=="ativo"}
                    if nsp.strip():
                        if len(nsp)<4: st.error("Senha mín. 4 chars."); st.stop()
                        d["senha_hash"]=hash_senha(nsp)
                    atualizar_usuario(us_["id"],d)
                    st.success(f"✅ Usuário **{us_['nick']}** atualizado!"); st.rerun()

def _cadastrar():
    st.markdown('<div class="card"><div class="card-h">➕ Novo Usuário</div>', unsafe_allow_html=True)
    st.info("O usuário receberá uma senha temporária que deverá alterar após o primeiro acesso.")
    with st.form("fnu"):
        c1,c2=st.columns(2)
        with c1:
            nick=st.text_input("Nick (login) *",placeholder="ex: maria.silva",
                               help="Apelido único para login. Apenas letras, números e ponto.")
            nome=st.text_input("Nome completo (opcional)",placeholder="Maria Silva")
            email=st.text_input("E-mail (opcional)")
        with c2:
            perfil=st.selectbox("Perfil de acesso *",PERFIS,format_func=lambda x:P_LABEL[x])
            senha=st.text_input("Senha temporária *",type="password",
                                help="Mínimo 4 caracteres.")
            senha2=st.text_input("Confirmar senha *",type="password")
        if st.form_submit_button("Criar Usuário →",type="primary",use_container_width=True):
            erros=[]
            if not nick.strip(): erros.append("Nick obrigatório.")
            if len(senha)<4: erros.append("Senha mínima: 4 caracteres.")
            if senha!=senha2: erros.append("Senhas não coincidem.")
            if not erros and buscar_por_nick(nick.strip().lower()): erros.append("Nick já cadastrado.")
            if erros:
                for e in erros: st.error(e)
            else:
                # Colunas exatas do schema.sql: nick, senha_hash, perfil, nome, email, ativo
                dados={
                    "nick":       nick.strip().lower(),
                    "senha_hash": hash_senha(senha),
                    "perfil":     perfil,
                    "ativo":      True,
                }
                if nome.strip(): dados["nome"]=nome.strip()
                if email.strip(): dados["email"]=email.strip()
                criar_usuario(dados)
                st.success(f"✅ Usuário **{nick.strip().lower()}** criado como **{P_LABEL[perfil]}**.")
                st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)
