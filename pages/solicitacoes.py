"""pages/solicitacoes.py — Tela de solicitações por perfil"""
import datetime, streamlit as st
from utils.database import (listar_produtos, listar_setores, registrar_movimentacao,
    listar_solicitacoes, atualizar_movimentacao, listar_notificacoes_usuario,
    estoque_disponivel, buscar_produto_por_id)
from utils.auth import sessao
from utils.ui import badge
from utils.fmt import datahora_br, qtd_br
from utils.unidades import sigla_para_opcao


def tela_solicitacoes_usuario():
    u = sessao()
    st.markdown('<div class="pg">', unsafe_allow_html=True)
    st.markdown('<div class="pg-title">📋 Solicitações</div>'
                '<div class="pg-sub">Solicite materiais e acompanhe seus pedidos</div>',
                unsafe_allow_html=True)
    # Notificações de aprovação
    notifs = listar_notificacoes_usuario(u["nick"])
    for n in notifs:
        prod = (n.get("produto") or {}).get("nome", "—")
        un   = sigla_para_opcao(n.get("unidade_informada", "UN"))
        st.success(f"🔔 **Aprovada!** {qtd_br(n['quantidade_informada'])} {un} de **{prod}** reservado e pronto para retirada.")
        if st.button("✅ Entendido", key=f"notif_{n['id']}"):
            try: atualizar_movimentacao(n["id"], {"notificacao_lida": True})
            except: pass
            st.rerun()
    t1, t2 = st.tabs(["Nova Solicitação", "Minhas Solicitações"])
    with t1: _form_solicitar(u)
    with t2: _minhas(u)
    st.markdown("</div>", unsafe_allow_html=True)


def tela_solicitacoes_almoxarife():
    st.markdown('<div class="pg">', unsafe_allow_html=True)
    st.markdown('<div class="pg-title">📋 Solicitações</div>'
                '<div class="pg-sub">Gerencie aprovações e consulte o histórico</div>',
                unsafe_allow_html=True)
    t1, t2 = st.tabs(["Aprovações Pendentes", "Histórico"])
    with t1: _aprovar()
    with t2: _hist_completo()
    st.markdown("</div>", unsafe_allow_html=True)


def _form_solicitar(u):
    if st.session_state.get("sol_enviada_ok"):
        st.success("📨 **Solicitação Enviada.** O retorno de aprovação será dado no seu aplicativo.")
        if st.button("➕ Nova Solicitação", type="primary"):
            del st.session_state["sol_enviada_ok"]
            st.session_state.pop("sol_prod_sel", None)
            st.rerun()
        return

    prods = listar_produtos()
    sets  = listar_setores()
    if not prods:
        st.warning("Nenhum produto cadastrado.")
        return

    pm = {p['nome']: p for p in prods}
    sn = [s["nome"] for s in sets] or ["Sem setor"]

    st.markdown('<div class="card"><div class="card-h">📝 Nova Solicitação</div>', unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        # Selectbox FORA do form para saldo em tempo real
        prod_nome = st.selectbox("Produto *", list(pm.keys()), key="sol_prod_sel")
        prod      = pm[prod_nome]
        un_sec    = prod.get("unidade_secundaria", "UN")
        un_lbl    = sigla_para_opcao(un_sec)

        # Saldo em tempo real — busca sempre que o produto mudar
        disp    = estoque_disponivel(prod["id"])
        cor_est = "var(--ok)" if disp > 0 else "var(--err)"
        st.markdown(f"""
        <div style="background:var(--bg2);border:1px solid var(--bdr);
                    border-radius:7px;padding:.55rem .9rem;font-size:.82rem;margin:.4rem 0;">
            📦 Saldo disponível:
            <strong style="color:{cor_est};">{qtd_br(disp)} {un_lbl}</strong>
        </div>
        """, unsafe_allow_html=True)

        qtd = st.number_input(f"Quantidade * ({un_lbl})", min_value=0.001, value=1.0, step=1.0, key="sol_qtd")

    with c2:
        setor  = st.selectbox("Setor *", sn, key="sol_setor")
        nome_s = st.text_input("Nome do solicitante *", value=u.get("nome") or u.get("nick", ""), key="sol_nome")
        obs    = st.text_area("Observação (opcional)", height=68, key="sol_obs")

    # Botão de envio fora do form para manter o selectbox reativo
    if st.button("📨 Enviar Solicitação →", type="primary", use_container_width=True, key="btn_enviar_sol"):
        if not nome_s.strip():
            st.error("Nome obrigatório.")
        else:
            registrar_movimentacao({
                "produto_id":            prod["id"],
                "tipo":                  "saida",
                "tipo_saida":            "SOLICITADA",
                "status":                "pendente",
                "quantidade_informada":  qtd,
                "unidade_informada":     un_sec,
                "quantidade_convertida": qtd,
                "setor_solicitante":     setor,
                "nome_solicitante":      nome_s.strip(),
                "nick_solicitante":      u["nick"],
                "observacao":            obs.strip() or None,
                "usuario_solicitante":   u["id"],
            })
            st.session_state["sol_enviada_ok"] = True
            st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)


def _minhas(u):
    todas  = listar_solicitacoes()
    minhas = [s for s in todas if s.get("nick_solicitante") == u["nick"]]
    _tbl(minhas, "Minhas Solicitações", mostrar_rejeicao=True)


def _aprovar():
    u    = sessao()
    pend = listar_solicitacoes("pendente")
    st.markdown('<div class="card"><div class="card-h">🔐 Pendentes de Aprovação</div>', unsafe_allow_html=True)
    if not pend:
        st.markdown('<p style="color:var(--t3);font-size:.82rem;">Nenhuma solicitação pendente.</p>', unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
        return
    conf = st.session_state.get("conf_sol")
    for s in pend:
        prod   = s.get("produto") or {}
        sol    = s.get("sol")     or {}
        un_lbl = sigla_para_opcao(s.get("unidade_informada", "UN"))
        disp   = estoque_disponivel(prod.get("id", ""))
        c1, c2, c3, c4 = st.columns([4, 3, 1, 1])
        with c1:
            st.markdown(f"**{prod.get('nome','—')}**")
            st.caption(f"{sol.get('nick','—')} | {s.get('setor_solicitante','—')} | {datahora_br(s['criado_em'])}")
        with c2:
            st.markdown(f"**{qtd_br(s['quantidade_informada'])} {un_lbl}**")
            cor = "var(--ok)" if disp >= float(s['quantidade_convertida']) else "var(--err)"
            st.markdown(f"<span style='font-size:.75rem;color:{cor};'>Disponível: {qtd_br(disp)} {un_lbl}</span>",
                        unsafe_allow_html=True)
        with c3:
            if st.button("✅", key=f"a_{s['id']}", help="Aprovar"):
                st.session_state["conf_sol"] = {"id": s["id"], "acao": "aprovar",
                    "prod": prod.get("nome","—"), "qtd": qtd_br(s["quantidade_informada"]),
                    "un": un_lbl, "nick": sol.get("nick","")}
                st.rerun()
        with c4:
            if st.button("❌", key=f"r_{s['id']}", help="Rejeitar"):
                st.session_state["conf_sol"] = {"id": s["id"], "acao": "rejeitar",
                    "prod": prod.get("nome","—"), "qtd": qtd_br(s["quantidade_informada"]),
                    "un": un_lbl, "nick": sol.get("nick","")}
                st.rerun()
        st.markdown('<div class="div"></div>', unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    if conf:
        acao   = conf["acao"]
        emoji  = "✅" if acao == "aprovar" else "❌"
        titulo = "Aprovar" if acao == "aprovar" else "Rejeitar"
        cor    = "var(--ok-bg)" if acao == "aprovar" else "var(--err-bg)"
        borda  = "rgba(22,163,74,.3)" if acao == "aprovar" else "rgba(220,38,38,.3)"
        st.markdown(f"""
        <div style="background:{cor};border:2px solid {borda};border-radius:10px;
                    padding:1.2rem 1.5rem;margin:1rem 0;">
            <div style="font-size:1rem;font-weight:700;margin-bottom:.6rem;">{emoji} Confirmar {titulo}</div>
            <div style="font-size:.85rem;color:var(--t2);line-height:1.8;">
                <b>Produto:</b> {conf['prod']}<br>
                <b>Qtd:</b> {conf['qtd']} {conf['un']}<br>
                <b>Solicitante:</b> {conf['nick']}
            </div>
        </div>
        """, unsafe_allow_html=True)
        motivo_rej = ""
        if acao == "rejeitar":
            motivo_rej = st.text_area("Motivo da rejeição * (será exibido ao solicitante)", key="motivo_rej_input")
        cs, cn, _ = st.columns([1, 1, 4])
        with cs:
            if st.button(f"{emoji} SIM, {titulo.lower()}", type="primary", use_container_width=True):
                if acao == "rejeitar" and not motivo_rej.strip():
                    st.error("Informe o motivo.")
                else:
                    if acao == "aprovar":
                        upd = {"status": "aprovado", "usuario_autorizador": u["id"],
                               "data_autorizacao": datetime.datetime.utcnow().isoformat()}
                        try: upd["notificacao_lida"] = False
                        except: pass
                        atualizar_movimentacao(conf["id"], upd)
                        st.success("✅ Aprovada! Solicitante será notificado.")
                    else:
                        atualizar_movimentacao(conf["id"], {"status": "rejeitado",
                                                             "motivo_rejeicao": motivo_rej.strip()})
                        st.success("Rejeitada com motivo registrado.")
                    del st.session_state["conf_sol"]
                    st.rerun()
        with cn:
            if st.button("↩ Cancelar", use_container_width=True):
                del st.session_state["conf_sol"]
                st.rerun()


def _hist_completo():
    _tbl(listar_solicitacoes(), "Histórico de Solicitações", mostrar_rejeicao=True)


def _tbl(movs, titulo="", mostrar_rejeicao=False):
    if not movs:
        st.info("Nenhuma solicitação encontrada.")
        return
    st.markdown(f'<div class="card"><div class="card-h">{titulo}</div>', unsafe_allow_html=True)
    rows = ""
    for m in movs:
        prod   = m.get("produto") or {}
        b      = badge(m["status"].capitalize(), m["status"])
        un_lbl = sigla_para_opcao(m.get("unidade_informada", "UN"))
        rows  += (f'<tr>'
                  f'<td style="color:var(--t3);font-size:.73rem;">{datahora_br(m["criado_em"])}</td>'
                  f'<td><strong>{prod.get("nome","—")}</strong></td>'
                  f'<td>{qtd_br(m["quantidade_informada"])} {un_lbl}</td>'
                  f'<td>{m.get("setor_solicitante","—")}</td>'
                  f'<td>{m.get("nome_solicitante","—")}</td>'
                  f'<td>{b}</td>'
                  f'</tr>')
    st.markdown(
        f'<table class="tbl"><thead><tr><th>Data</th><th>Produto</th><th>Qtd</th>'
        f'<th>Setor</th><th>Solicitante</th><th>Status</th>'
        f'</tr></thead><tbody>{rows}</tbody></table>',
        unsafe_allow_html=True)
    if mostrar_rejeicao:
        rejeitadas = [m for m in movs if m.get("status") == "rejeitado" and m.get("motivo_rejeicao")]
        for m in rejeitadas:
            prod = m.get("produto") or {}
            with st.expander(f"💬 Motivo rejeição — {prod.get('nome','—')} ({datahora_br(m['criado_em'])})"):
                st.markdown(
                    f'<div style="background:var(--err-bg);border:1px solid rgba(220,38,38,.2);'
                    f'border-radius:7px;padding:.75rem 1rem;font-size:.85rem;">'
                    f'<strong style="color:var(--err);">Motivo:</strong><br>{m["motivo_rejeicao"]}</div>',
                    unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)
