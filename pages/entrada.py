def _hist():
    HIST_ITENS_PAGINA_OPCOES = [10, 20, 40]

    movs = listar_movimentacoes(tipo="entrada", limite=100)

    st.markdown('<div class="card"><div class="card-h">📋 Histórico de Entradas</div>', unsafe_allow_html=True)

    if not movs:
        st.info("Nenhuma entrada registrada.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    # ── Filtros ──────────────────────────────────────────────────────────
    fc1, fc2, fc3, fc4 = st.columns([2.5, 2, 2, 1.5])
    with fc1:
        filtro_nota = st.text_input("🔎 Nota (NF)", key="inv_filtro_nota", placeholder="Buscar por nº da NF...")
    with fc2:
        filtro_data = st.date_input("📅 Data", value=None, key="inv_filtro_data", format="DD/MM/YYYY")
    with fc3:
        filtro_tipo = st.selectbox("🏷️ Tipo de Entrada", ["Todos"] + TIPOS, key="inv_filtro_tipo")
    with fc4:
        itens_pag = st.selectbox("Itens/página", HIST_ITENS_PAGINA_OPCOES, key="inv_itens_pag")

    # ── Aplica filtros ───────────────────────────────────────────────────
    filtrados = movs
    if filtro_nota.strip():
        termo = filtro_nota.strip().lower()
        filtrados = [m for m in filtrados if termo in (m.get("numero_nf") or "").lower()]
    if filtro_data:
        data_str = filtro_data.isoformat()
        filtrados = [m for m in filtrados if (m.get("criado_em") or "")[:10] == data_str]
    if filtro_tipo != "Todos":
        filtrados = [m for m in filtrados if m.get("tipo_entrada") == filtro_tipo]

    # Reinicia a página quando algum filtro (ou itens/página) muda
    assinatura_filtros = (filtro_nota, str(filtro_data), filtro_tipo, itens_pag)
    if st.session_state.get("inv_filtro_assinatura") != assinatura_filtros:
        st.session_state["inv_filtro_assinatura"] = assinatura_filtros
        st.session_state["inv_pagina"] = 1

    total = len(filtrados)
    if total == 0:
        st.markdown(
            '<p style="color:var(--t3);font-size:.82rem;">'
            'Nenhuma entrada encontrada com os filtros aplicados.</p>',
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)
        return

    total_paginas = max(1, -(-total // itens_pag))  # ceil division
    pagina_atual  = min(max(1, st.session_state.get("inv_pagina", 1)), total_paginas)
    st.session_state["inv_pagina"] = pagina_atual

    inicio = (pagina_atual - 1) * itens_pag
    fim    = inicio + itens_pag
    pagina_itens = filtrados[inicio:fim]

    # ── Tabela ───────────────────────────────────────────────────────────
    rows = ""
    for m in pagina_itens:
        prod   = (m.get("produto") or {}).get("nome", "—")
        cod    = (m.get("produto") or {}).get("codigo_interno", "—")
        eu     = (m.get("exe") or {}).get("nick", "—")
        tp     = badge(m.get("tipo_entrada", "—"), "concluido")
        un_lbl = sigla_para_opcao(m.get("unidade_informada", "UN"))
        nf     = m.get("numero_nf") or "—"
        obs    = m.get("observacao") or "—"
        rows += (
            f'<tr>'
            f'<td style="color:var(--t3);font-size:.73rem;">{datahora_br(m["criado_em"])}</td>'
            f'<td><strong>{esc(prod)}</strong></td>'
            f'<td class="mono">{esc(cod)}</td>'
            f'<td style="font-weight:600;">{qtd_br(m["quantidade_informada"])} {un_lbl}</td>'
            f'<td>{tp}</td>'
            f'<td style="color:var(--t3);">{esc(nf)}</td>'
            f'<td style="color:var(--t3);font-size:.72rem;">{esc_trunc(obs, 30)}</td>'
            f'<td style="color:var(--t3);">{esc(eu)}</td>'
            f'</tr>'
        )
    st.markdown(
        f'<table class="tbl"><thead><tr>'
        f'<th>Data/Hora</th><th>Produto</th><th>Código</th>'
        f'<th>Qtd</th><th>Tipo</th><th>NF</th><th>Obs/CNR</th><th>Executor</th>'
        f'</tr></thead><tbody>{rows}</tbody></table>',
        unsafe_allow_html=True,
    )

    # ── Paginação ────────────────────────────────────────────────────────
    st.markdown('<div class="div" style="margin:.6rem 0;"></div>', unsafe_allow_html=True)
    pc1, pc2, pc3 = st.columns([1, 2, 1])
    with pc1:
        if st.button("← Anterior", disabled=(pagina_atual <= 1), key="inv_pag_ant", use_container_width=True):
            st.session_state["inv_pagina"] = pagina_atual - 1
            st.rerun()
    with pc2:
        st.markdown(
            f'<p style="text-align:center;font-size:.8rem;color:var(--t3);margin-top:.4rem;">'
            f'Página {pagina_atual} de {total_paginas} · {total} entrada(s)</p>',
            unsafe_allow_html=True,
        )
    with pc3:
        if st.button("Próxima →", disabled=(pagina_atual >= total_paginas), key="inv_pag_prox", use_container_width=True):
            st.session_state["inv_pagina"] = pagina_atual + 1
            st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)
