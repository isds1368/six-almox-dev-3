"""utils/ui.py — Design System SFC — tema adaptativo claro/escuro"""
import streamlit as st

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');

:root {
    --red:#CC0000; --red-d:#A80000; --red-l:#FF1A1A;
    --red-bg:rgba(204,0,0,0.07); --red-bdr:rgba(204,0,0,0.18);
    --bg:#FFFFFF; --bg2:#F7F7F8; --bg3:#EFEFEF;
    --bdr:#E5E5E5; --bdr2:#D0D0D0;
    --t1:#0F0F0F; --t2:#3D3D3D; --t3:#6B6B6B; --t4:#9B9B9B;
    --ok:#16A34A; --ok-bg:#F0FDF4;
    --warn:#D97706; --warn-bg:#FFFBEB;
    --err:#DC2626; --err-bg:#FEF2F2;
    --info:#2563EB; --info-bg:#EFF6FF;
    --r:8px; --rl:14px;
    --sh:0 1px 4px rgba(0,0,0,0.07),0 1px 2px rgba(0,0,0,0.04);
    --sh2:0 4px 16px rgba(0,0,0,0.09);
    --font:'Plus Jakarta Sans',sans-serif;
    --mono:'JetBrains Mono',monospace;
}
@media(prefers-color-scheme:dark){
    :root{
        --red:#E53535; --red-d:#CC0000; --red-l:#FF4444;
        --red-bg:rgba(229,53,53,0.11); --red-bdr:rgba(229,53,53,0.25);
        --bg:#0C0C0C; --bg2:#161616; --bg3:#1E1E1E;
        --bdr:#2A2A2A; --bdr2:#383838;
        --t1:#F5F5F5; --t2:#CCCCCC; --t3:#888888; --t4:#555555;
        --ok:#22C55E; --ok-bg:rgba(22,163,74,0.12);
        --warn:#F59E0B; --warn-bg:rgba(217,119,6,0.12);
        --err:#EF4444; --err-bg:rgba(220,38,38,0.12);
        --info:#3B82F6; --info-bg:rgba(37,99,235,0.12);
        --sh:0 1px 4px rgba(0,0,0,0.35);
        --sh2:0 4px 16px rgba(0,0,0,0.5);
    }
}

html,body,[class*="css"],[data-testid="stAppViewContainer"]{
    font-family:var(--font)!important;
    background:var(--bg)!important;
    color:var(--t1)!important;
}
#MainMenu,footer,header{visibility:hidden!important;}
[data-testid="stSidebar"]{display:none!important;}
.block-container{padding:0!important;max-width:100%!important;}

/* ── TOPBAR ── */
.sfc-bar{
    display:flex;align-items:center;justify-content:space-between;
    background:var(--red);height:52px;padding:0 1.5rem;
    position:sticky;top:0;z-index:1000;
    box-shadow:0 2px 8px rgba(180,0,0,0.3);
}
.sfc-brand{
    font-size:.9rem;font-weight:800;color:#fff;
    letter-spacing:.12em;text-transform:uppercase;
    display:flex;align-items:center;gap:.5rem;
}
.sfc-brand span{opacity:.5;font-weight:300;}
.sfc-avatar{
    width:28px;height:28px;background:rgba(255,255,255,.2);
    border:1.5px solid rgba(255,255,255,.35);border-radius:50%;
    display:flex;align-items:center;justify-content:center;
    font-size:.68rem;font-weight:700;color:#fff;flex-shrink:0;
}

/* ── SUBNAV ── */
.sfc-nav{
    background:var(--bg);border-bottom:1.5px solid var(--bdr);
    padding:0 1.2rem;display:flex;align-items:center;
    gap:.1rem;height:40px;overflow-x:auto;scrollbar-width:none;
}
.sfc-nav::-webkit-scrollbar{display:none;}

/* nav botões */
.sfc-nav [data-testid="stButton"] button{
    background:transparent!important;border:none!important;
    color:var(--t3)!important;font-family:var(--font)!important;
    font-size:.76rem!important;font-weight:500!important;
    padding:.25rem .7rem!important;border-radius:6px!important;
    height:28px!important;min-height:28px!important;
    white-space:nowrap!important;transition:all .15s!important;
}
.sfc-nav [data-testid="stButton"] button:hover{
    background:var(--red-bg)!important;color:var(--red)!important;
}
.nav-on [data-testid="stButton"] button{
    background:var(--red-bg)!important;color:var(--red)!important;
    font-weight:700!important;
}
.nav-sair [data-testid="stButton"] button{
    background:transparent!important;
    border:1px solid var(--red-bdr)!important;
    color:var(--red)!important;font-size:.72rem!important;
    height:26px!important;min-height:26px!important;
}

/* ── PAGE ── */
.pg{padding:1.6rem 2rem;max-width:1440px;margin:0 auto;}
.pg-title{font-size:1.35rem;font-weight:700;color:var(--t1);margin-bottom:.2rem;}
.pg-sub{font-size:.78rem;color:var(--t3);margin-bottom:1.4rem;}

/* ── KPI GRID ── */
.kpis{
    display:grid;
    grid-template-columns:repeat(auto-fit,minmax(150px,1fr));
    gap:.8rem;margin-bottom:1.4rem;
}
.kpi{
    background:var(--bg);border:1.5px solid var(--bdr);
    border-radius:var(--r);padding:.9rem 1rem;position:relative;
    overflow:hidden;transition:box-shadow .15s;
}
.kpi:hover{box-shadow:var(--sh2);}
.kpi-bar{
    position:absolute;left:0;top:0;bottom:0;width:3px;
    background:var(--ac,var(--red));
    border-radius:8px 0 0 8px;
}
.kpi-label{
    font-size:.65rem;font-weight:700;letter-spacing:.07em;
    text-transform:uppercase;color:var(--t3);margin-bottom:.35rem;
}
.kpi-val{
    font-size:1.85rem;font-weight:800;
    color:var(--ac,var(--red));line-height:1;
}
.kpi-sub{font-size:.68rem;color:var(--t4);margin-top:.25rem;}

/* ── CARD ── */
.card{
    background:var(--bg);border:1.5px solid var(--bdr);
    border-radius:var(--r);padding:1.1rem 1.3rem;margin-bottom:.9rem;
}
.card-h{
    font-size:.75rem;font-weight:700;letter-spacing:.05em;
    text-transform:uppercase;color:var(--t2);
    margin-bottom:.9rem;padding-bottom:.55rem;
    border-bottom:1px solid var(--bdr);
}

/* ── TABELA ── */
.tbl{width:100%;border-collapse:collapse;font-size:.81rem;}
.tbl th{
    font-size:.63rem;font-weight:700;letter-spacing:.08em;
    text-transform:uppercase;color:var(--t3);
    padding:.45rem .7rem;border-bottom:1.5px solid var(--bdr);
    text-align:left;background:var(--bg2);white-space:nowrap;
}
.tbl td{
    padding:.55rem .7rem;border-bottom:1px solid var(--bdr);
    color:var(--t2);vertical-align:middle;
}
.tbl tbody tr:hover td{background:var(--red-bg);}
.mono{font-family:var(--mono);font-size:.73rem;color:var(--t3);}

/* ── BADGES ── */
.bx{
    display:inline-flex;align-items:center;gap:.25rem;
    padding:.13rem .5rem;border-radius:20px;
    font-size:.62rem;font-weight:700;letter-spacing:.05em;
    text-transform:uppercase;white-space:nowrap;
}
.bx::before{content:'●';font-size:.45rem;}
.bx-ok      {background:var(--ok-bg);  color:var(--ok);  border:1px solid rgba(22,163,74,.2);}
.bx-baixo   {background:var(--warn-bg);color:var(--warn);border:1px solid rgba(217,119,6,.2);}
.bx-critico {background:var(--err-bg); color:var(--err); border:1px solid rgba(220,38,38,.2);}
.bx-pendente{background:var(--warn-bg);color:var(--warn);border:1px solid rgba(217,119,6,.2);}
.bx-aprovado{background:var(--info-bg);color:var(--info);border:1px solid rgba(37,99,235,.2);}
.bx-concluido{background:var(--ok-bg); color:var(--ok);  border:1px solid rgba(22,163,74,.2);}
.bx-rejeitado{background:var(--err-bg);color:var(--err); border:1px solid rgba(220,38,38,.2);}
.bx-cancelado{background:var(--bg3);   color:var(--t3);  border:1px solid var(--bdr);}
.bx-enviado  {background:var(--ok-bg); color:var(--ok);  border:1px solid rgba(22,163,74,.2);}
.bx-manual   {background:var(--info-bg);color:var(--info);border:1px solid rgba(37,99,235,.2);}

/* ── INPUTS ── */
[data-testid="stTextInput"] input,
[data-testid="stNumberInput"] input,
[data-testid="stTextArea"] textarea{
    background:var(--bg2)!important;border:1.5px solid var(--bdr)!important;
    color:var(--t1)!important;border-radius:6px!important;
    font-family:var(--font)!important;font-size:.83rem!important;
}
[data-testid="stTextInput"] input:focus,
[data-testid="stNumberInput"] input:focus,
[data-testid="stTextArea"] textarea:focus{
    border-color:var(--red)!important;
    box-shadow:0 0 0 3px var(--red-bdr)!important;
}

/* ── BOTÕES ── */
[data-testid="stButton"] button{
    background:var(--bg2)!important;border:1.5px solid var(--bdr)!important;
    color:var(--t2)!important;font-family:var(--font)!important;
    font-size:.8rem!important;font-weight:600!important;
    border-radius:6px!important;transition:all .15s!important;
}
[data-testid="stButton"] button:hover{
    background:var(--bg3)!important;border-color:var(--bdr2)!important;
}
[data-testid="stButton"] button[kind="primary"]{
    background:var(--red)!important;border-color:var(--red)!important;
    color:#fff!important;
}
[data-testid="stButton"] button[kind="primary"]:hover{
    background:var(--red-d)!important;
}

/* ── TABS ── */
[data-testid="stTabs"] [data-baseweb="tab-list"]{
    background:transparent!important;
    border-bottom:1.5px solid var(--bdr)!important;gap:0!important;
}
[data-testid="stTabs"] [data-baseweb="tab"]{
    background:transparent!important;border:none!important;
    border-bottom:2px solid transparent!important;
    color:var(--t3)!important;font-family:var(--font)!important;
    font-size:.77rem!important;font-weight:600!important;
    padding:.45rem .9rem!important;margin-bottom:-1.5px!important;
}
[data-testid="stTabs"] [aria-selected="true"]{
    color:var(--red)!important;border-bottom-color:var(--red)!important;
}

/* ── SELECTBOX ── */
[data-testid="stSelectbox"]>div>div{
    background:var(--bg2)!important;border:1.5px solid var(--bdr)!important;
    border-radius:6px!important;color:var(--t1)!important;
}

/* ── EXPANDER ── */
[data-testid="stExpander"]{
    background:var(--bg)!important;border:1.5px solid var(--bdr)!important;
    border-radius:var(--r)!important;
}

/* ── SCROLLBAR ── */
::-webkit-scrollbar{width:4px;height:4px;}
::-webkit-scrollbar-track{background:var(--bg2);}
::-webkit-scrollbar-thumb{background:var(--bdr2);border-radius:3px;}
::-webkit-scrollbar-thumb:hover{background:var(--red);}

/* ── AUTH ── */
.auth-wrap{
    min-height:100vh;display:flex;align-items:center;
    justify-content:center;background:var(--bg2);padding:1rem;
}
.auth-card{
    background:var(--bg);border:1.5px solid var(--bdr);
    border-radius:var(--rl);padding:2.2rem 1.8rem;
    width:100%;max-width:370px;box-shadow:var(--sh2);
}
.auth-logo{
    font-size:1.4rem;font-weight:800;color:var(--red);
    letter-spacing:.1em;text-align:center;margin-bottom:.15rem;
}
.auth-tag{
    font-size:.68rem;color:var(--t3);text-align:center;
    letter-spacing:.08em;text-transform:uppercase;margin-bottom:1.8rem;
}
.div{height:1px;background:var(--bdr);margin:1.2rem 0;}
</style>
"""


def inject_css():
    st.markdown(CSS, unsafe_allow_html=True)


def topbar(pagina: str, usuario: dict):
    from utils.auth import pode

    MENU = [
        ("Dashboard",      "dashboard",      pode("dashboard")),
        ("Entrada",        "entrada",        pode("entrada")),
        ("Solicitações",   "solicitacoes",   pode("solicitar")),
        ("Saída Manual",   "saida_manual",   pode("saida_manual")),
        ("Saída Aprovada", "saida_aprovada", pode("saida_aprovada")),
        ("Estoque",        "estoque",        pode("estoque")),
        ("Notas Fiscais",  "notas",          pode("notas")),
        ("Usuários",       "usuarios",       pode("usuarios")),
        ("Configurações",  "configuracoes",  pode("configuracoes")),
    ]
    itens = [(l, d) for l, d, v in MENU if v]

    iniciais = "".join(w[0].upper() for w in usuario["nome_completo"].split()[:2])
    nivel_map = {"admin": "Administrador", "almoxarife": "Almoxarife", "usuario": "Usuário"}

    st.markdown(f"""
    <div class="sfc-bar">
        <div class="sfc-brand">SFC <span>|</span> ALMOXARIFADO</div>
        <div style="display:flex;align-items:center;gap:.6rem;color:rgba(255,255,255,.9);font-size:.78rem;">
            <span style="color:rgba(255,255,255,.6);font-size:.72rem;">
                {nivel_map.get(usuario['nivel_acesso'],'')}
            </span>
            <div class="sfc-avatar">{iniciais}</div>
            <span style="font-weight:600;">{usuario['nome_completo'].split()[0]}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="sfc-nav">', unsafe_allow_html=True)
    cols = st.columns(len(itens) + 1)
    for i, (label, dest) in enumerate(itens):
        with cols[i]:
            cls = "nav-on" if pagina == dest else ""
            st.markdown(f'<div class="{cls}">', unsafe_allow_html=True)
            if st.button(label, key=f"nav_{dest}"):
                navegar(dest)
            st.markdown("</div>", unsafe_allow_html=True)
    with cols[-1]:
        st.markdown('<div class="nav-sair">', unsafe_allow_html=True)
        if st.button("Sair →", key="nav_sair"):
            st.session_state.clear()
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)


def badge(texto: str, tipo: str) -> str:
    return f'<span class="bx bx-{tipo}">{texto}</span>'


def status_estoque(est_sec: float, min_prim: float, fator: float) -> tuple[str, str]:
    mins = min_prim * fator
    if est_sec <= 0:      return "Crítico", "critico"
    if est_sec <= mins:   return "Baixo", "baixo"
    return "OK", "ok"


def kpi_html(label: str, valor, sub: str = "", ac: str = "var(--red)") -> str:
    return f"""<div class="kpi">
        <div class="kpi-bar" style="background:{ac}"></div>
        <div class="kpi-label">{label}</div>
        <div class="kpi-val" style="color:{ac}">{valor}</div>
        {"<div class='kpi-sub'>"+sub+"</div>" if sub else ""}
    </div>"""


def navegar(pagina: str):
    st.session_state["pagina"] = pagina
    st.rerun()


def pagina_atual() -> str:
    return st.session_state.get("pagina", "dashboard")
