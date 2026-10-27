"""
Jarvis Mark 1 - Painel de acompanhamento dos projetos EnerMais (Streamlit).

* So LE. Quem grava no banco e a ponte (script no PC do Rafael), com a chave secreta.
* Login real pelo Supabase Auth (e-mail e senha). Depois do login, o banco so entrega dados a quem estiver
  na lista gestao.usuarios_autorizados (RLS). Visitante sem login nao ve nada.
* Este app usa SOMENTE a chave publica (publishable). A chave secreta NUNCA entra aqui.

Configuracao (Streamlit Cloud > Settings > Secrets, ou arquivo .env local):
  SUPABASE_URL = "https://<ref>.supabase.co"
  SUPABASE_PUBLISHABLE_KEY = "sb_publishable_..."
"""
import base64
import os
from datetime import datetime, timedelta, timezone

import pandas as pd
import streamlit as st

APP_VERSION = "0.3.1"  # atualizar a cada versao nova
SCHEMA = "gestao"
LOGO_PATH = os.path.join(os.path.dirname(__file__), "logo-enermais-grupo.png")

st.set_page_config(page_title="Jarvis Mark 1 — EnerMais", page_icon="🧭", layout="wide")

st.markdown(
    """
<style>
[data-testid="stSidebar"] { background-color: #111113; min-width: 250px; max-width: 250px; border-right: 1px solid #2A2B30; }
[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 { color: #F99D20; }
hr { border-color: #3A3B40 !important; opacity: 0.6; }
[data-testid="stMetric"] { background: #1A1A1D; border: 1px solid #2A2B30; border-radius: 8px; padding: 10px 14px; }
[data-testid="stForm"] { background: #1A1A1D; border: 1px solid #2A2B30; border-radius: 10px; }
/* campos de digitacao: fundo mais escuro que o cartao, borda clara, texto branco, cursor laranja */
[data-baseweb="input"], [data-baseweb="base-input"], [data-baseweb="select"] > div, [data-baseweb="textarea"] {
  background-color: #0E0E10 !important; border-color: #5A5B63 !important; border-radius: 6px !important; }
[data-baseweb="input"] input, [data-baseweb="base-input"] input, [data-baseweb="textarea"] textarea, [data-baseweb="select"] input {
  color: #FFFFFF !important; -webkit-text-fill-color: #FFFFFF !important; caret-color: #F99D20 !important; background-color: transparent !important; }
[data-baseweb="input"]:focus-within, [data-baseweb="base-input"]:focus-within, [data-baseweb="textarea"]:focus-within {
  border-color: #F99D20 !important; box-shadow: 0 0 0 1px #F99D20 !important; }
input::placeholder, textarea::placeholder { color: #8A8B93 !important; -webkit-text-fill-color: #8A8B93 !important; }
input:-webkit-autofill { -webkit-text-fill-color: #FFFFFF !important; -webkit-box-shadow: 0 0 0 1000px #0E0E10 inset !important; }
[data-testid="stTextInput"] label p, [data-testid="stSelectbox"] label p { color: #D8D8DC !important; }
[data-baseweb="popover"] ul { background-color: #1A1A1D !important; }
</style>
""",
    unsafe_allow_html=True,
)


@st.cache_data
def logo_base64():
    with open(LOGO_PATH, "rb") as f:
        return base64.b64encode(f.read()).decode()


def render_logo(height=56):
    try:
        st.markdown(
            f'<img src="data:image/png;base64,{logo_base64()}" height="{height}" '
            'style="filter: brightness(0) invert(1); margin-bottom: 12px;">',
            unsafe_allow_html=True,
        )
    except Exception:
        pass


def config(chave):
    """Le dos Secrets do Streamlit Cloud ou das variaveis de ambiente (.env local)."""
    try:
        if chave in st.secrets:
            return st.secrets[chave]
    except Exception:
        pass
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except Exception:
        pass
    return os.environ.get(chave)


@st.cache_resource
def novo_cliente():
    from supabase import create_client

    url, chave = config("SUPABASE_URL"), config("SUPABASE_PUBLISHABLE_KEY")
    if not url or not chave:
        st.error("Faltam SUPABASE_URL e SUPABASE_PUBLISHABLE_KEY nos Secrets do app.")
        st.stop()
    if chave.startswith("sb_secret_"):
        st.error("Chave secreta nos Secrets: troque pela chave PÚBLICA (sb_publishable_). Isso é uma trava de segurança.")
        st.stop()
    return create_client(url, chave)


def tabela(db, nome, order=None, desc=False, limit=None):
    q = db.schema(SCHEMA).table(nome).select("*")
    if order:
        q = q.order(order, desc=desc)
    if limit:
        q = q.limit(limit)
    return pd.DataFrame(q.execute().data)


def vazio(v):
    return "—" if (v is None or (isinstance(v, float) and pd.isna(v)) or str(v).strip() in ("", "None", "nan")) else str(v)


def mostrar(df, colunas, nomes=None, **kw):
    """Tabela sem 'None'/'nan': vazio vira traço."""
    d = df[colunas].copy().astype(object).where(df[colunas].notna(), "—")
    if nomes:
        d = d.rename(columns=nomes)
    st.dataframe(d, width="stretch", hide_index=True, **kw)


# --------------------------------------------------------------------------- login
db = novo_cliente()
if "sessao" not in st.session_state:
    st.session_state.sessao = None

if st.session_state.sessao is None:
    render_logo(height=84)
    st.title("Jarvis Mark 1")
    st.caption("Acompanhamento dos projetos EnerMais. Acesso restrito: entre com seu e-mail e senha.")
    with st.form("login"):  # dentro de um formulario, apertar Enter envia
        email = st.text_input("E-mail")
        senha = st.text_input("Senha", type="password")
        entrar = st.form_submit_button("Entrar")
    if entrar:
        try:
            resp = db.auth.sign_in_with_password({"email": email.strip(), "password": senha})
            st.session_state.sessao = resp.session
            st.rerun()
        except Exception:
            st.error("E-mail ou senha inválidos.")
    st.stop()

# reanexa o token a cada rerun (senao as consultas vao como visitante e o banco devolve vazio)
db.postgrest.auth(st.session_state.sessao.access_token)

try:
    meu = db.schema(SCHEMA).table("usuarios_autorizados").select("papel").execute().data
except Exception:
    meu = []
if not meu:
    st.error("Você entrou, mas este usuário não está autorizado a ver o painel. Fale com o Rafael.")
    if st.button("Sair"):
        st.session_state.sessao = None
        st.rerun()
    st.stop()

PAGINAS = ["Visão geral", "Projetos", "Demandas", "Histórico de evoluções", "Métricas", "Fila de comandos"]
with st.sidebar:
    render_logo(height=64)
    st.header("Jarvis Mark 1")
    st.caption(f"Logado como: {st.session_state.sessao.user.email}")
    pagina = st.radio("Ir para", PAGINAS)
    if st.button("🔄 Recarregar dados"):
        st.cache_data.clear()
        st.rerun()
    if st.button("Sair"):
        st.session_state.sessao = None
        st.rerun()


@st.cache_data(ttl=120, show_spinner="Carregando...")
def carregar(_db, nome, ordem=None, desc=False, limite=None):
    return tabela(_db, nome, order=ordem, desc=desc, limit=limite)


def _fuso():
    """Horario de Brasilia (America/Sao_Paulo). O servidor do Streamlit roda em UTC, por isso converte aqui."""
    try:
        from zoneinfo import ZoneInfo

        return ZoneInfo("America/Sao_Paulo")
    except Exception:
        return timezone(timedelta(hours=-3))  # Brasil sem horario de verao desde 2019


def rotulo_data(v):
    try:
        return datetime.fromisoformat(str(v).replace("Z", "+00:00")).astimezone(_fuso()).strftime("%d/%m/%Y %H:%M")
    except Exception:
        return "—"


proj = carregar(db, "projetos", "sigla")
pend = carregar(db, "pendencias")
mets = carregar(db, "metricas_def", "codigo")
fila = carregar(db, "fila_comandos")
sync = carregar(db, "sincronizacoes", "iniciada_em")
evs = carregar(db, "eventos_status", "ocorrido_em", True, 1500)
nome_proj = dict(zip(proj["id"], proj["sigla"])) if not proj.empty else {}

# --------------------------------------------------------------------------- paginas
if pagina == "Visão geral":
    st.title("Visão geral dos projetos")
    if sync.empty:
        st.warning("A ponte ainda não enviou nenhuma atualização. Rode ponte-mark1.bat no PC do Rafael.")
    else:
        ult = sync.sort_values("iniciada_em").iloc[-1]
        cor = st.success if ult["status"] == "ok" else st.warning
        cor(f"Última atualização do vault: {rotulo_data(ult['iniciada_em'])} (resultado: {ult['status']})")
    if proj.empty:
        st.info("Nenhum projeto carregado ainda.")
    else:
        a, b, c, d = st.columns(4)
        a.metric("Projetos", len(proj))
        b.metric("Ativos", int((proj["status"] == "ativo").sum()))
        c.metric("Em planejamento", int((proj["status"] == "planejamento").sum()))
        abertas = pend[pend["status"].isin(["aberta", "em_andamento"])] if not pend.empty else pend
        d.metric("Pendências abertas", 0 if abertas.empty else len(abertas))
        st.subheader("Onde cada projeto está")
        vis = proj.copy()
        vis["atualizado_vault_em"] = vis["atualizado_vault_em"].map(rotulo_data)
        mostrar(vis, ["sigla", "nome", "status", "etapa_atual", "proximo_passo", "acesso", "atualizado_vault_em"],
                {"sigla": "Sigla", "nome": "Projeto", "status": "Status", "etapa_atual": "Etapa",
                 "proximo_passo": "Próximo passo", "acesso": "Acesso", "atualizado_vault_em": "Handoff atualizado"})
        if not evs.empty:
            st.subheader("Últimas evoluções")
            ult_ev = evs.head(8).copy()
            ult_ev["projeto"] = ult_ev["projeto_id"].map(nome_proj)
            ult_ev["quando"] = ult_ev["ocorrido_em"].map(lambda v: rotulo_data(v)[:10])
            mostrar(ult_ev, ["quando", "projeto", "versao", "resumo"],
                    {"quando": "Data", "projeto": "Projeto", "versao": "Versão", "resumo": "O que mudou"})

elif pagina == "Projetos":
    st.title("Projetos")
    if proj.empty:
        st.info("Nenhum projeto carregado ainda.")
    else:
        sel = st.selectbox("Projeto", proj["sigla"].tolist(),
                           format_func=lambda s: f"{s} — {proj.loc[proj['sigla'] == s, 'nome'].iloc[0]}")
        p = proj[proj["sigla"] == sel].iloc[0]
        st.subheader(vazio(p["nome"]))
        st.write(vazio(p["descricao"]))
        c1, c2, c3 = st.columns(3)
        c1.metric("Status", vazio(p["status"]))
        c2.metric("Etapa", vazio(p["etapa_atual"]))
        c3.metric("Acesso do app", vazio(p["acesso"]))
        st.write(f"**Próximo passo:** {vazio(p['proximo_passo'])}")
        st.write(f"**Stack:** {vazio(p['stack'])}  |  **Repositório:** {vazio(p['repositorio'])}  |  **Pasta no vault:** {vazio(p['caminho_vault'])}")
        pp = pend[pend["projeto_id"] == p["id"]] if not pend.empty else pend
        st.markdown("**Pendências deste projeto**")
        if pp.empty:
            st.caption("Nenhuma pendência registrada.")
        else:
            mostrar(pp, ["titulo", "depende_de", "prioridade", "status", "prazo"],
                    {"titulo": "Pendência", "depende_de": "Depende de", "prioridade": "Prioridade", "status": "Status", "prazo": "Prazo"})
        ee = evs[evs["projeto_id"] == p["id"]] if not evs.empty else evs
        st.markdown("**Evoluções deste projeto**")
        if ee.empty:
            st.caption("Nenhuma evolução registrada ainda (a ponte lê o versoes.md do projeto).")
        else:
            ee = ee.assign(quando=ee["ocorrido_em"].map(lambda v: rotulo_data(v)[:10]))
            mostrar(ee.head(30), ["quando", "versao", "tipo", "resumo"],
                    {"quando": "Data", "versao": "Versão", "tipo": "Tipo", "resumo": "O que mudou"})

elif pagina == "Demandas":
    st.title("Demandas de todos os projetos")
    st.caption("Vem do bloco PENDÊNCIAS de cada handoff (a ponte atualiza a cada 15 min). Para criar, mudar ou resolver uma demanda: edite o handoff do projeto, ou peça ao Claude na conversa do projeto.")
    if pend.empty:
        st.info("Nenhuma pendência registrada ainda. Elas entram quando os handoffs ganharem o bloco PENDÊNCIAS.")
    else:
        ordem_prio = {"critica": 0, "alta": 1, "media": 2, "baixa": 3}
        rotulo_prio = {"critica": "🔴 crítica", "alta": "🟠 alta", "media": "🟡 média", "baixa": "⚪ baixa"}
        base = pend.assign(projeto=pend["projeto_id"].map(nome_proj))
        abertas = base[base["status"].isin(["aberta", "em_andamento"])]
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Abertas", len(abertas))
        m2.metric("Dependem do Rafael", int((abertas["depende_de"] == "rafael").sum()))
        m3.metric("Dependem do Claude", int((abertas["depende_de"] == "claude").sum()))
        m4.metric("Prioridade alta/crítica", int(abertas["prioridade"].isin(["alta", "critica"]).sum()))
        f1, f2, f3 = st.columns(3)
        deps = sorted(base["depende_de"].unique())
        dep = f1.multiselect("Depende de", deps, default=["rafael"] if "rafael" in deps else [])
        projs = sorted(p for p in base["projeto"].dropna().unique())
        sel_proj = f2.multiselect("Projeto", projs)
        prios = [x for x in ["critica", "alta", "media", "baixa"] if x in set(base["prioridade"])]
        sel_prio = f3.multiselect("Prioridade", prios, format_func=lambda x: rotulo_prio.get(x, x))
        com_resolvidas = st.checkbox("Mostrar também as resolvidas/descartadas")
        v = base if com_resolvidas else abertas
        if dep:
            v = v[v["depende_de"].isin(dep)]
        if sel_proj:
            v = v[v["projeto"].isin(sel_proj)]
        if sel_prio:
            v = v[v["prioridade"].isin(sel_prio)]
        v = v.assign(_o=v["prioridade"].map(ordem_prio).fillna(2)).sort_values(["_o", "projeto"])
        v = v.assign(prioridade=v["prioridade"].map(lambda x: rotulo_prio.get(x, x)))
        st.write(f"{len(v)} demanda(s) na lista")
        if "detalhe" not in v.columns:
            v = v.assign(detalhe=None)
        mostrar(v, ["prioridade", "projeto", "titulo", "depende_de", "detalhe", "prazo", "status"],
                {"prioridade": "Prioridade", "projeto": "Projeto", "titulo": "Demanda", "depende_de": "Depende de",
                 "detalhe": "Responsável", "prazo": "Cobrar em / prazo", "status": "Status"})

elif pagina == "Histórico de evoluções":
    st.title("Histórico de evoluções")
    st.caption("Vem do versoes.md de cada projeto (a ponte lê). Nunca é apagado.")
    if evs.empty:
        st.info("Ainda não há evoluções carregadas.")
    else:
        e = evs.assign(projeto=evs["projeto_id"].map(nome_proj),
                       quando=evs["ocorrido_em"].map(lambda v: rotulo_data(v)[:10]))
        f1, f2 = st.columns(2)
        pj = f1.multiselect("Projeto", sorted(e["projeto"].dropna().unique()))
        tp = f2.multiselect("Tipo", sorted(e["tipo"].dropna().unique()))
        if pj:
            e = e[e["projeto"].isin(pj)]
        if tp:
            e = e[e["tipo"].isin(tp)]
        st.caption(f"{len(e)} registros")
        mostrar(e, ["quando", "projeto", "versao", "tipo", "resumo"],
                {"quando": "Data", "projeto": "Projeto", "versao": "Versão", "tipo": "Tipo", "resumo": "O que mudou"})

elif pagina == "Métricas":
    st.title("Indicadores e entregas")
    if mets.empty:
        st.info("Catálogo vazio. A ponte carrega a matriz do ENERDATA.")
    else:
        f1, f2, f3 = st.columns(3)
        tipo = f1.multiselect("Tipo", ["indicador", "entrega"], default=["indicador", "entrega"])
        resp = f2.multiselect("Responsável", sorted(mets["responsavel"].dropna().unique()))
        sit = f3.multiselect("Situação", sorted(mets["situacao"].dropna().unique()))
        v = mets[mets["tipo"].isin(tipo)]
        if resp:
            v = v[v["responsavel"].isin(resp)]
        if sit:
            v = v[v["situacao"].isin(sit)]
        v = v.assign(projeto=v["projeto_id"].map(nome_proj))
        st.caption(f"{len(v)} de {len(mets)} itens")
        mostrar(v, ["codigo", "tipo", "nome", "responsavel", "meta", "periodicidade", "projeto", "fonte", "situacao"],
                {"codigo": "Código", "tipo": "Tipo", "nome": "Nome", "responsavel": "Responsável", "meta": "Meta",
                 "periodicidade": "Periodicidade", "projeto": "Projeto", "fonte": "Fonte", "situacao": "Situação"})

elif pagina == "Fila de comandos":
    st.title("Fila de comandos do Jarvis")
    st.caption("O Jarvis propõe, o Rafael aprova, só o aprovado roda. Nesta versão a fila é só de leitura.")
    if fila.empty:
        st.info("Fila vazia.")
    else:
        mostrar(fila, ["codigo", "titulo", "status", "proposto_por", "criado_em", "concluido_em"],
                {"codigo": "Código", "titulo": "Título", "status": "Status", "proposto_por": "Proposto por",
                 "criado_em": "Criado em", "concluido_em": "Concluído em"})

st.markdown(
    f"""<div style="margin-top:2rem;padding-top:.75rem;border-top:1px solid rgba(245,246,250,.12);font-size:.72rem;color:rgba(245,246,250,.45);">
Jarvis Mark 1 · v{APP_VERSION} · dados em tempo real (schema gestao) · rafael.nakahara@enermais.com.br</div>""",
    unsafe_allow_html=True,
)
