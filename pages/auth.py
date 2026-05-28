"""pages/auth.py — Login e Primeiro Acesso simplificado"""
import streamlit as st
from utils.auth import hash_senha, fazer_login, primeiro_acesso
from utils.database import criar_usuario, buscar_por_nick
from utils.ui import navegar

def tela_login():
    col1, col2, col3 = st.columns([1, 1.1, 1])
    with col2:
        st.markdown("<div style='height:15vh'></div>", unsafe_allow_html=True)
        st.markdown('<div class="auth-logo">SFC · ALM</div>', unsafe_allow_html=True)
        st.markdown('<div class="auth-tag">Sistema de Controle de Almoxarifado</div>', unsafe_allow_html=True)
        st.markdown('<div class="div"></div>', unsafe_allow_html=True)

        with st.form("lf"):
            nick  = st.text_input("Nick / Login", placeholder="ex: joao")
            senha = st.text_input("Senha", type="password", placeholder="••••••••")
            ok    = st.form_submit_button("Entrar →", type="primary", use_container_width=True)

        if ok:
            if not nick or not senha:
                st.error("Preencha nick e senha.")
            else:
                u = fazer_login(nick.strip().lower(), senha)
                if u:
                    st.session_state["usuario"] = u
                    navegar("dashboard")
                else:
                    st.error("Nick ou senha incorretos, ou usuário inativo.")

        st.markdown('<div style="text-align:center;margin-top:1rem;font-size:.7rem;color:var(--t4);">SFC Almoxarifado &copy; 2025</div>', unsafe_allow_html=True)


def tela_primeiro_acesso():
    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        st.markdown("<div style='height:10vh'></div>", unsafe_allow_html=True)
        st.markdown('<div class="auth-logo">SFC · ALM</div>', unsafe_allow_html=True)
        st.markdown('<div class="auth-tag">Configuração Inicial</div>', unsafe_allow_html=True)

        st.markdown("""
        <div style="background:var(--warn-bg);border:1px solid rgba(217,119,6,.3);
                    border-radius:7px;padding:.75rem 1rem;margin-bottom:1.2rem;font-size:.8rem;color:var(--warn);">
            ⚙️ Bem-vindo! Crie o primeiro administrador do sistema.
        </div>
        """, unsafe_allow_html=True)

        with st.form("paf"):
            nick   = st.text_input("Nick (apelido de login) *",
                                   placeholder="ex: admin",
                                   help="Será usado para entrar no sistema. Pode ser qualquer apelido.")
            perfil_info = st.info("👑 Este usuário será criado como **Administrador** automaticamente.")
            col_a, col_b = st.columns(2)
            with col_a:
                senha  = st.text_input("Senha *", type="password",
                                       help="Mínimo 4 caracteres. Você pode alterar depois.")
            with col_b:
                senha2 = st.text_input("Confirmar senha *", type="password")
            nome   = st.text_input("Nome completo (opcional)", placeholder="ex: João Silva")
            criar  = st.form_submit_button("Criar Administrador →", type="primary", use_container_width=True)

        if criar:
            erros = []
            if not nick.strip():    erros.append("Nick obrigatório.")
            if len(senha) < 4:      erros.append("Senha mínima: 4 caracteres.")
            if senha != senha2:     erros.append("Senhas não coincidem.")
            if not erros and buscar_por_nick(nick.strip().lower()):
                erros.append("Este nick já existe.")

            if erros:
                for e in erros: st.error(e)
            else:
                # Insere apenas as colunas que existem no schema.sql:
                # nick, senha_hash, perfil, nome (opcional), ativo
                dados = {
                    "nick":       nick.strip().lower(),
                    "senha_hash": hash_senha(senha),
                    "perfil":     "admin",
                    "ativo":      True,
                }
                if nome.strip():
                    dados["nome"] = nome.strip()

                criar_usuario(dados)
                st.success(f"✅ Administrador **{nick.strip().lower()}** criado!")
                st.info("Agora faça login com suas credenciais.")
                st.session_state["pagina"] = "login"
                st.rerun()
