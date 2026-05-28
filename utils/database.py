"""utils/database.py — Colunas: nick, senha_hash, perfil, nome, email, ativo"""
import os, streamlit as st
from supabase import create_client, Client
from dotenv import load_dotenv
load_dotenv()

@st.cache_resource(show_spinner=False)
def get_sb() -> Client:
    url = os.getenv("SUPABASE_URL") or st.secrets.get("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_SERVICE_KEY") or st.secrets.get("SUPABASE_SERVICE_KEY", "")
    if not url or not key:
        st.error("❌ Configure SUPABASE_URL e SUPABASE_SERVICE_KEY nos secrets.")
        st.stop()
    return create_client(url, key)

def _safe(fn):
    try: return fn()
    except Exception: return None

# ── USUÁRIOS ────────────────────────────────────────────────────
def contar_usuarios() -> int:
    try: return get_sb().table("usuarios").select("id", count="exact").execute().count or 0
    except: return 0

def buscar_por_nick(nick: str):
    try:
        r = get_sb().table("usuarios").select("*").eq("nick", nick.strip().lower()).maybe_single().execute()
        return r.data
    except: return None

def criar_usuario(dados: dict) -> dict:
    """Campos: nick, senha_hash, perfil. Opcionais: nome, email"""
    try:
        r = get_sb().table("usuarios").insert(dados).execute()
        return r.data[0]
    except Exception as e:
        err = str(e)
        if "42501" in err or "row-level security" in err:
            st.error("❌ Permissão negada (RLS). Use a chave **service_role** nos secrets, não a anon.")
        elif "42P01" in err or "does not exist" in err:
            st.error("❌ Tabela não encontrada. Execute o **schema.sql** no Supabase.")
        elif "23505" in err or "unique" in err.lower():
            st.error("❌ Este nick já está em uso. Escolha outro.")
        else:
            st.error(f"❌ Erro ao criar usuário: {err}")
        st.stop()

def listar_usuarios() -> list:
    try: return get_sb().table("usuarios").select("*").order("nick").execute().data or []
    except: return []

def atualizar_usuario(uid: str, dados: dict):
    try: get_sb().table("usuarios").update(dados).eq("id", uid).execute()
    except Exception as e: st.error(f"Erro: {e}")

# ── CATEGORIAS ──────────────────────────────────────────────────
def listar_categorias() -> list:
    try: return get_sb().table("categorias").select("*").order("nome").execute().data or []
    except: return []

def criar_categoria(nome, desc=""):
    return get_sb().table("categorias").insert({"nome": nome, "descricao": desc}).execute().data[0]

# ── SETORES ─────────────────────────────────────────────────────
def listar_setores(apenas_ativos=True) -> list:
    try:
        q = get_sb().table("setores").select("*").order("nome")
        if apenas_ativos: q = q.eq("ativo", True)
        return q.execute().data or []
    except: return []

def criar_setor(nome):
    return get_sb().table("setores").insert({"nome": nome}).execute().data[0]

def atualizar_setor(sid, dados):
    get_sb().table("setores").update(dados).eq("id", sid).execute()

# ── PRODUTOS ────────────────────────────────────────────────────
def listar_produtos(apenas_ativos=True) -> list:
    try:
        q = get_sb().table("produtos").select("*, categorias(nome)").order("nome")
        if apenas_ativos: q = q.eq("ativo", True)
        return q.execute().data or []
    except: return []

def buscar_produto_por_ean(ean):
    try:
        r = get_sb().table("produtos").select("*, categorias(nome)").eq("ean", ean.strip()).maybe_single().execute()
        return r.data
    except: return None

def buscar_produto_por_id(pid):
    try:
        r = get_sb().table("produtos").select("*, categorias(nome)").eq("id", pid).maybe_single().execute()
        return r.data
    except: return None

def buscar_produtos_por_nome(nome) -> list:
    try: return get_sb().table("produtos").select("*, categorias(nome)").ilike("nome", f"%{nome}%").eq("ativo", True).execute().data or []
    except: return []

def criar_produto(dados) -> dict:
    return get_sb().table("produtos").insert(dados).execute().data[0]

def atualizar_produto(pid, dados):
    get_sb().table("produtos").update(dados).eq("id", pid).execute()

# ── DOCUMENTOS ──────────────────────────────────────────────────
def criar_documento(dados) -> dict:
    return get_sb().table("documentos").insert(dados).execute().data[0]

def upload_pdf(b, nome):
    try:
        sb = get_sb(); path = f"notas/{nome}"
        sb.storage.from_("notas-fiscais").upload(path, b, file_options={"content-type": "application/pdf", "upsert": "true"})
        return sb.storage.from_("notas-fiscais").create_signed_url(path, 60*60*24*365).get("signedURL")
    except Exception as e: st.warning(f"Upload falhou: {e}"); return None

# ── MOVIMENTAÇÕES ────────────────────────────────────────────────
_SEL = """*, produto:produtos(id,nome,codigo_interno,unidade_primaria,unidade_secundaria,fator_conversao,quantidade_total_secundaria),
    sol:usuarios!movimentacoes_usuario_solicitante_fkey(nick,nome),
    aut:usuarios!movimentacoes_usuario_autorizador_fkey(nick,nome),
    exe:usuarios!movimentacoes_usuario_executor_fkey(nick,nome),
    doc:documentos(nome_arquivo,status_envio,caminho_arquivo)"""

def registrar_movimentacao(dados) -> dict:
    return get_sb().table("movimentacoes").insert(dados).execute().data[0]

def atualizar_movimentacao(mid, dados) -> dict:
    return get_sb().table("movimentacoes").update(dados).eq("id", mid).execute().data[0]

def listar_movimentacoes(tipo=None, status=None, tipo_saida=None, limite=200) -> list:
    try:
        q = get_sb().table("movimentacoes").select(_SEL).order("criado_em", desc=True).limit(limite)
        if tipo: q = q.eq("tipo", tipo)
        if status: q = q.eq("status", status)
        if tipo_saida: q = q.eq("tipo_saida", tipo_saida)
        return q.execute().data or []
    except: return []

def listar_solicitacoes(status=None) -> list:
    try:
        q = get_sb().table("movimentacoes").select(_SEL).eq("tipo", "saida").eq("tipo_saida", "SOLICITADA").order("criado_em", desc=True)
        if status: q = q.eq("status", status)
        return q.execute().data or []
    except: return []

def listar_notas_pendentes() -> list:
    try: return get_sb().table("movimentacoes").select(_SEL).eq("tipo", "entrada").eq("tipo_entrada", "Nota Fiscal").eq("envio_financeiro", False).eq("status", "concluido").order("criado_em", desc=True).execute().data or []
    except: return []

def listar_notas_enviadas() -> list:
    try: return get_sb().table("movimentacoes").select(_SEL).eq("tipo", "entrada").eq("tipo_entrada", "Nota Fiscal").eq("envio_financeiro", True).order("criado_em", desc=True).execute().data or []
    except: return []

# ── CONFIGURAÇÕES ────────────────────────────────────────────────
def get_config(chave, default="") -> str:
    try:
        r = get_sb().table("configuracoes").select("valor").eq("chave", chave).maybe_single().execute()
        return r.data["valor"] if r.data else default
    except: return default

def set_config(chave, valor):
    get_sb().table("configuracoes").upsert({"chave": chave, "valor": valor}).execute()

def listar_configs() -> dict:
    try: return {c["chave"]: c["valor"] for c in get_sb().table("configuracoes").select("*").execute().data or []}
    except: return {}

# ── DASHBOARD ────────────────────────────────────────────────────
def stats_dashboard() -> dict:
    try:
        sb = get_sb(); prods = listar_produtos()
        criticos = baixos = ok_c = 0
        for p in prods:
            est = float(p.get("quantidade_total_secundaria") or 0)
            minp = float(p.get("estoque_minimo_primario") or 0)
            fat = float(p.get("fator_conversao") or 1)
            if est <= 0: criticos += 1
            elif est <= minp * fat: baixos += 1
            else: ok_c += 1
        pend_sol = sb.table("movimentacoes").select("id", count="exact").eq("tipo", "saida").eq("tipo_saida", "SOLICITADA").eq("status", "pendente").execute().count or 0
        pend_nf = sb.table("movimentacoes").select("id", count="exact").eq("tipo_entrada", "Nota Fiscal").eq("envio_financeiro", False).eq("status", "concluido").execute().count or 0
        total_mov = sb.table("movimentacoes").select("id", count="exact").execute().count or 0
        saidas_ok = sb.table("movimentacoes").select("setor_solicitante,quantidade_convertida").eq("tipo", "saida").eq("status", "concluido").execute().data or []
        consumo = {}
        for s in saidas_ok:
            k = s.get("setor_solicitante") or "Sem setor"
            consumo[k] = consumo.get(k, 0) + float(s.get("quantidade_convertida") or 0)
        from datetime import datetime, timedelta
        lim = (datetime.utcnow() - timedelta(days=30)).isoformat()
        ids_mov = {m["produto_id"] for m in sb.table("movimentacoes").select("produto_id").gte("criado_em", lim).execute().data or []}
        parados = sum(1 for p in prods if p["id"] not in ids_mov)
        recentes = sb.table("movimentacoes").select("criado_em,tipo,quantidade_informada,unidade_informada,status,produtos(nome)").order("criado_em", desc=True).limit(10).execute().data or []
        return {"total_produtos": len(prods), "criticos": criticos, "baixos": baixos, "ok": ok_c,
                "pend_solicitacoes": pend_sol, "pend_notas": pend_nf, "total_movimentacoes": total_mov,
                "consumo_setor": consumo, "parados": parados, "recentes": recentes, "produtos": prods}
    except Exception as e:
        st.error(f"Erro dashboard: {e}")
        return {"total_produtos":0,"criticos":0,"baixos":0,"ok":0,"pend_solicitacoes":0,"pend_notas":0,"total_movimentacoes":0,"consumo_setor":{},"parados":0,"recentes":[],"produtos":[]}


# ── CONSUMO POR PERÍODO (dashboard) ─────────────────────────────
def consumo_por_periodo(data_ini: str, data_fim: str, setor: str | None = None) -> list:
    """
    Retorna movimentações de saída concluídas no período.
    data_ini / data_fim: strings no formato 'YYYY-MM-DD'
    setor: filtro opcional por setor_solicitante
    """
    try:
        q = (get_sb().table("movimentacoes")
             .select("criado_em, quantidade_convertida, setor_solicitante, produto:produtos(nome, unidade_secundaria)")
             .eq("tipo", "saida")
             .eq("status", "concluido")
             .gte("criado_em", f"{data_ini}T00:00:00")
             .lte("criado_em", f"{data_fim}T23:59:59")
             .order("criado_em", desc=False))
        if setor:
            q = q.eq("setor_solicitante", setor)
        return q.execute().data or []
    except Exception as e:
        return []
