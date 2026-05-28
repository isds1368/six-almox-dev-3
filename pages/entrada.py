"""pages/entrada.py — Entrada de Produtos com nova entrada do mesmo item"""
import datetime, streamlit as st
from utils.database import (buscar_produto_por_ean, buscar_produtos_por_nome,
    criar_produto, registrar_movimentacao, criar_documento,
    upload_pdf, listar_categorias, listar_movimentacoes)
from utils.auth import sessao
from utils.ui import badge
from utils.fmt import datahora_br, qtd_br

UNS   = ["UN","CX","KG","LT","MT","PC","RL","FR","GL","DZ","CT","SC","FD","BL"]
TIPOS = ["Nota Fiscal","FL","Entrada Interna","Ajuste Manual"]


def tela_entrada():
    st.markdown('<div class="pg">', unsafe_allow_html=True)
    st.markdown('<div class="pg-title">📥 Entrada de Produtos</div>'
                '<div class="pg-sub">Registre entradas por EAN, nome ou cadastro avulso</div>',
                unsafe_allow_html=True)
    t1, t2 = st.tabs(["Nova Entrada", "Histórico"])
    with t1: _form()
    with t2: _hist()
    st.markdown("</div>", unsafe_allow_html=True)


def _form():
    u    = sessao()
    cats = listar_categorias()
    cm   = {c["nome"]: c["id"] for c in cats}

    # ── estado da sessão ─────────────────────────────────────────
    prod        = st.session_state.get("ps")
    busca_feita = st.session_state.get("busca_feita", False)

    # ── BUSCA ────────────────────────────────────────────────────
    st.markdown('<div class="card"><div class="card-h">🔍 Identificar Produto</div>',
                unsafe_allow_html=True)
    c1, c2, c3 = st.columns([3, 1, 1])
    with c1:
        termo = st.text_input("EAN ou nome", placeholder="Bipe ou digite", key="eb")
    with c2:
        st.markdown("<div style='height:27px'></div>", unsafe_allow_html=True)
        be = st.button("Buscar EAN",  use_container_width=True)
    with c3:
        st.markdown("<div style='height:27px'></div>", unsafe_allow_html=True)
        bn = st.button("Buscar Nome", use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

    if be and termo.strip():
        p = buscar_produto_por_ean(termo.strip())
        if p:
            st.session_state["ps"]          = p
            st.session_state["busca_feita"] = True
            st.session_state.pop("en", None)
            prod = p
        else:
            st.warning("EAN não encontrado. Cadastre abaixo.")
            st.session_state.pop("ps", None)
            st.session_state["en"]          = termo.strip()
            st.session_state["busca_feita"] = False

    if bn and termo.strip():
        res = buscar_produtos_por_nome(termo.strip())
        if res:
            opts = {f"{r['nome']} ({r['codigo_interno']})": r for r in res}
            sel  = st.selectbox("Selecione", list(opts.keys()), key="snr")
            if st.button("Usar este produto →"):
                st.session_state["ps"]          = opts[sel]
                st.session_state["busca_feita"] = True
                st.session_state.pop("en", None)
                st.rerun()
        else:
            st.warning("Não encontrado.")
            st.session_state.pop("ps", None)

    # ── PRODUTO ENCONTRADO: mostra info + formulário de entrada ──
    if prod:
        est = float(prod.get("quantidade_total_secundaria", 0))
        fat = float(prod.get("fator_conversao", 1))
        up  = prod.get("unidade_primaria",  "UN")
        us  = prod.get("unidade_secundaria","UN")

        # Card com info do produto
        st.markdown(f"""
        <div style="background:var(--ok-bg);border:1px solid rgba(22,163,74,.25);
                    border-radius:8px;padding:.8rem 1.1rem;margin:.5rem 0;font-size:.84rem;">
            ✅ <strong>{prod['nome']}</strong>
            &nbsp;<span class="mono" style="color:var(--t3);">{prod['codigo_interno']}</span>
            &nbsp;|&nbsp; Estoque atual:
            <strong style="color:var(--ok);">{qtd_br(est)} {us}</strong>
            <span style="color:var(--t3);font-size:.75rem;"> (= {qtd_br(est/fat if fat else 0)} {up})</span>
        </div>
        """, unsafe_allow_html=True)

        st.markdown('<div class="card"><div class="card-h">📥 Registrar Nova Entrada</div>',
                    unsafe_allow_html=True)

        with st.form("fer"):
            c1, c2 = st.columns(2)
            with c1:
                te  = st.selectbox("Tipo de entrada *", TIPOS)
                qtd = st.number_input("Quantidade *", min_value=0.001, value=1.0, step=1.0)
                ui  = st.selectbox("Unidade", UNS, index=UNS.index(up) if up in UNS else 0)
            with c2:
                nfn  = st.text_input("Número NF",   placeholder="Opcional")
                forn = st.text_input("Fornecedor",  placeholder="Opcional")
                obs  = st.text_area("Observação",   height=60)

            qc = qtd * fat
            st.markdown(f"""
            <div style="background:var(--bg2);border:1px solid var(--bdr);border-radius:7px;
                        padding:.65rem .9rem;margin:.4rem 0;font-size:.8rem;">
                📦 <strong>{qtd_br(qtd)} {ui}</strong>
                <span style="color:var(--t3);"> = </span>
                <strong style="color:var(--red);">{qtd_br(qc)} {us}</strong>
                <span style="color:var(--t3);"> serão adicionados ao estoque</span>
            </div>
            """, unsafe_allow_html=True)

            pdf = st.file_uploader("Anexar PDF/Comprovante (opcional)", type=["pdf","png","jpg"])

            if st.form_submit_button("✅ Confirmar Entrada", type="primary", use_container_width=True):
                did = None
                if pdf:
                    ts  = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
                    nm  = f"{ts}_{pdf.name}"
                    url = upload_pdf(pdf.read(), nm) if pdf.type == "application/pdf" else None
                    doc = criar_documento({
                        "nome_arquivo":    pdf.name,
                        "caminho_arquivo": url,
                        "status_envio":    "pendente" if te == "Nota Fiscal" else "nao_requer",
                    })
                    did = doc["id"]

                registrar_movimentacao({
                    "produto_id":            prod["id"],
                    "tipo":                  "entrada",
                    "tipo_entrada":          te,
                    "status":                "concluido",
                    "quantidade_informada":  qtd,
                    "unidade_informada":     ui,
                    "quantidade_convertida": qc,
                    "envio_financeiro":      te != "Nota Fiscal",
                    "fornecedor":            forn.strip() or None,
                    "numero_nf":             nfn.strip()  or None,
                    "observacao":            obs.strip()  or None,
                    "documento_id":          did,
                    "usuario_executor":      u["id"],
                    "data_movimentacao":     datetime.datetime.utcnow().isoformat(),
                })

                st.success(
                    f"✅ Entrada registrada! "
                    f"**+{qtd_br(qc)} {us}** de **{prod['nome']}** "
                    f"adicionados por **{u.get('nick','')}**."
                )
                if te == "Nota Fiscal":
                    st.info("📎 NF registrada — acesse **Notas Fiscais** para enviar ao financeiro.")

                # Mantém o produto selecionado para permitir nova entrada do mesmo item
                # Atualiza estoque exibido via rerun
                st.session_state["busca_feita"] = True
                # Busca dados atualizados do produto
                from utils.database import buscar_produto_por_id
                p_atualizado = buscar_produto_por_id(prod["id"])
                if p_atualizado:
                    st.session_state["ps"] = p_atualizado
                st.rerun()

        # Botões de ação após o form
        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("🔄 Buscar outro produto", use_container_width=True):
                for k in ["ps","en","busca_feita"]:
                    st.session_state.pop(k, None)
                st.rerun()
        with col_b:
            if st.button("➕ Nova entrada deste produto", use_container_width=True):
                # Recarrega dados atualizados e mantém produto selecionado
                from utils.database import buscar_produto_por_id
                p_atualizado = buscar_produto_por_id(prod["id"])
                if p_atualizado:
                    st.session_state["ps"] = p_atualizado
                st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)
        return

    # ── CADASTRO NOVO PRODUTO (EAN não encontrado) ───────────────
    if st.session_state.get("en") and not prod:
        st.markdown('<div class="card"><div class="card-h">📋 Cadastrar Novo Produto</div>',
                    unsafe_allow_html=True)
        with st.form("fnp"):
            c1, c2 = st.columns(2)
            with c1:
                nm   = st.text_input("Nome *")
                cat  = st.selectbox("Categoria", list(cm.keys()))
                up_n = st.selectbox("Un. primária",   UNS, index=1)
                us_n = st.selectbox("Un. secundária", UNS)
            with c2:
                fat_n = st.number_input("Fator (1 prim = ? sec)", value=1.0, min_value=0.001, step=1.0)
                em_n  = st.number_input("Estoque mínimo", value=0.0, min_value=0.0)
                ean_n = st.text_input("EAN", value=st.session_state.get("en",""))
            desc_n = st.text_area("Descrição", height=60)
            if st.form_submit_button("Cadastrar produto →", type="primary"):
                if not nm.strip():
                    st.error("Nome obrigatório.")
                else:
                    novo = criar_produto({
                        "nome":                    nm.strip(),
                        "ean":                     ean_n.strip() or None,
                        "categoria_id":            cm.get(cat),
                        "unidade_primaria":        up_n,
                        "unidade_secundaria":      us_n,
                        "fator_conversao":         fat_n,
                        "estoque_minimo_primario": em_n,
                        "descricao":               desc_n.strip() or None,
                    })
                    st.session_state["ps"]          = novo
                    st.session_state["busca_feita"] = True
                    st.session_state.pop("en", None)
                    st.success(f"✅ Produto **{novo['nome']}** cadastrado — {novo['codigo_interno']}")
                    st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    # ── AVULSO (sem EAN) ─────────────────────────────────────────
    if not prod and not st.session_state.get("en"):
        with st.expander("➕ Criar produto sem EAN"):
            with st.form("fav"):
                c1, c2 = st.columns(2)
                with c1:
                    nav  = st.text_input("Nome *")
                    cav  = st.selectbox("Categoria", list(cm.keys()), key="cav")
                    upav = st.selectbox("Un. primária",   UNS, index=1, key="upav")
                    usav = st.selectbox("Un. secundária", UNS,          key="usav")
                with c2:
                    ftav = st.number_input("Fator", value=1.0, min_value=0.001)
                    emav = st.number_input("Est. mín", value=0.0, min_value=0.0)
                if st.form_submit_button("Criar →", type="primary"):
                    if nav.strip():
                        novo = criar_produto({
                            "nome":                    nav.strip(),
                            "categoria_id":            cm.get(cav),
                            "unidade_primaria":        upav,
                            "unidade_secundaria":      usav,
                            "fator_conversao":         ftav,
                            "estoque_minimo_primario": emav,
                        })
                        st.session_state["ps"]          = novo
                        st.session_state["busca_feita"] = True
                        st.rerun()


def _hist():
    movs = listar_movimentacoes(tipo="entrada", limite=100)
    if not movs:
        st.info("Nenhuma entrada registrada.")
        return
    st.markdown('<div class="card"><div class="card-h">Histórico de Entradas</div>',
                unsafe_allow_html=True)
    rows = ""
    for m in movs:
        prod = (m.get("produto") or {}).get("nome","—")
        cod  = (m.get("produto") or {}).get("codigo_interno","—")
        eu   = (m.get("exe") or {}).get("nick","—")
        tp   = badge(m.get("tipo_entrada","—"),
                     "manual" if m.get("tipo_entrada") == "FL" else "concluido")
        rows += (
            f'<tr>'
            f'<td style="color:var(--t3);font-size:.73rem;">{datahora_br(m["criado_em"])}</td>'
            f'<td><strong>{prod}</strong></td>'
            f'<td class="mono">{cod}</td>'
            f'<td style="font-weight:600;">{qtd_br(m["quantidade_informada"])} {m["unidade_informada"]}</td>'
            f'<td>{tp}</td>'
            f'<td style="color:var(--t3);">{m.get("numero_nf") or "—"}</td>'
            f'<td style="color:var(--t3);">{eu}</td>'
            f'</tr>'
        )
    st.markdown(
        f'<table class="tbl"><thead><tr>'
        f'<th>Data</th><th>Produto</th><th>Código</th>'
        f'<th>Qtd</th><th>Tipo</th><th>NF</th><th>Executor</th>'
        f'</tr></thead><tbody>{rows}</tbody></table>',
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)
