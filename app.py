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
import os
from datetime import datetime

import pandas as pd
import streamlit as st

APP_VERSION = "0.1"
SCHEMA = "gestao"

st.set_page_config(page_title="Jarvis Mark 1 - EnerMais", page_icon="🧭", layout="wide")

st.markdown(
    """
<style>
[data-testid="stSidebar"] { background-color: #0A0C2E; min-width: 250px; max-width: 250px; }
[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 { color: #F99D20; }
hr { border-color: #F99D20 !important; opacity: 0.5; }
</style>
""",
    unsafe_allow_html=True,
)


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
        st.error("Chave secreta nos Secrets: troque pela chave PUBLICA (sb_publishable_). Isso e uma trava de seguranca.")
        st.stop()
    return create_client(url, chave)


def tabela(db, nome, **kw):
    q = db.schema(SCHEMA).table(nome).select(kw.get("select", "*"))
    if "order" in kw:
        q = q.order(kw["order"], desc=kw.get("desc", False))
    return pd.DataFrame(q.execute().data)


# --------------------------------------------------------------------------- login
db = novo_cliente()
if "sessao" not in st.session_state:
    st.session_state.sessao = None

if st.session_state.sessao is None:
    st.title("🧭 Jarvis Mark 1")
    st.caption("Acompanhamento dos projetos EnerMais. Acesso restrito: entre com seu e-mail e senha.")
    email = st.text_input("E-mail")
    senha = st.text_input("Senha", type="password")
    if st.button("Entrar"):
        try:
            resp = db.auth.sign_in_with_password({"email": email, "password": senha})
            st.session_state.sessao = resp.session
            st.rerun()
        except Exception:
            st.error("E-mail ou senha invalidos.")
    st.stop()

# reanexa o token a cada rerun (senao as consultas vao como visitante e o banco devolve vazio)
db.postgrest.auth(st.session_state.sessao.access_token)

try:
    meu = db.schema(SCHEMA).table("usuarios_autorizados").select("papel").execute().data
except Exception:
    meu = []
if not meu:
    st.error("Voce entrou, mas este usuario nao esta autorizado a ver o painel. Fale com o Rafael.")
    if st.button("Sair"):
        st.session_state.sessao = None
        st.rerun()
    st.stop()

with st.sidebar:
    st.header("🧭 Jarvis Mark 1")
    st.caption(f"Logado como: {st.session_state.sessao.user.email}")
    pagina = st.radio("Ir para", ["Visao geral", "Projetos", "Pendencias", "Metricas", "Fila de comandos"])
    if st.button("🔄 Recarregar dados"):
        st.cache_data.clear()
        st.rerun()
    if st.button("Sair"):
        st.session_state.sessao = None
        st.rerun()


@st.cache_data(ttl=120, show_spinner="Carregando...")
def carregar(_db, nome, ordem=None):
    return tabela(_db, nome, order=ordem) if ordem else tabela(_db, nome)


def rotulo_data(v):
    try:
        return datetime.fromisoformat(str(v).replace("Z", "+00:00")).astimezone().strftime("%d/%m/%Y %H:%M")
    except Exception:
        return "-"


proj = carregar(db, "projetos", "sigla")
pend = carregar(db, "pendencias")
mets = carregar(db, "metricas_def", "codigo")
fila = carregar(db, "fila_comandos")
sync = carregar(db, "sincronizacoes", "iniciada_em")

# --------------------------------------------------------------------------- paginas
if pagina == "Visao geral":
    st.title("Visao geral dos projetos")
    if sync.empty:
        st.warning("A ponte ainda nao enviou nenhuma atualizacao. Rode ponte-mark1.bat no PC do Rafael.")
    else:
        ult = sync.sort_values("iniciada_em").iloc[-1]
        cor = st.success if ult["status"] == "ok" else st.warning
        cor(f"Ultima atualizacao do vault: {rotulo_data(ult['iniciada_em'])} (resultado: {ult['status']})")
    if proj.empty:
        st.info("Nenhum projeto carregado ainda.")
    else:
        a, b, c, d = st.columns(4)
        a.metric("Projetos", len(proj))
        b.metric("Ativos", int((proj["status"] == "ativo").sum()))
        c.metric("Em planejamento", int((proj["status"] == "planejamento").sum()))
        abertas = pend[pend["status"].isin(["aberta", "em_andamento"])] if not pend.empty else pend
        d.metric("Pendencias abertas", 0 if abertas.empty else len(abertas))
        st.subheader("Onde cada projeto esta")
        vis = proj[["sigla", "nome", "status", "etapa_atual", "proximo_passo", "acesso", "atualizado_vault_em"]].copy()
        vis["atualizado_vault_em"] = vis["atualizado_vault_em"].map(rotulo_data)
        st.dataframe(
            vis.rename(columns={"sigla": "Sigla", "nome": "Projeto", "status": "Status", "etapa_atual": "Etapa",
                                "proximo_passo": "Proximo passo", "acesso": "Acesso", "atualizado_vault_em": "Handoff atualizado"}),
            width="stretch", hide_index=True)

elif pagina == "Projetos":
    st.title("Projetos")
    if proj.empty:
        st.info("Nenhum projeto carregado ainda.")
    else:
        sel = st.selectbox("Projeto", proj["sigla"].tolist(), format_func=lambda s: f"{s} - {proj.loc[proj['sigla'] == s, 'nome'].iloc[0]}")
        p = proj[proj["sigla"] == sel].iloc[0]
        st.subheader(p["nome"])
        st.write(p["descricao"] or "")
        c1, c2, c3 = st.columns(3)
        c1.metric("Status", p["status"] or "-")
        c2.metric("Etapa", p["etapa_atual"] or "-")
        c3.metric("Acesso do app", p["acesso"] or "-")
        st.write(f"**Proximo passo:** {p['proximo_passo'] or '-'}")
        st.write(f"**Stack:** {p['stack'] or '-'}  |  **Repositorio:** {p['repositorio'] or '-'}  |  **Pasta no vault:** {p['caminho_vault'] or '-'}")
        pp = pend[pend["projeto_id"] == p["id"]] if not pend.empty else pend
        st.markdown("**Pendencias deste projeto**")
        if pp.empty:
            st.caption("Nenhuma pendencia registrada.")
        else:
            st.dataframe(pp[["titulo", "depende_de", "prioridade", "status", "prazo"]], width="stretch", hide_index=True)

elif pagina == "Pendencias":
    st.title("Pendencias")
    if pend.empty:
        st.info("Nenhuma pendencia registrada ainda. Elas entram quando os handoffs ganharem o bloco STATUS.")
    else:
        dep = st.multiselect("Depende de", sorted(pend["depende_de"].unique()), default=["rafael"] if "rafael" in set(pend["depende_de"]) else [])
        v = pend if not dep else pend[pend["depende_de"].isin(dep)]
        nome_proj = dict(zip(proj["id"], proj["sigla"])) if not proj.empty else {}
        v = v.assign(projeto=v["projeto_id"].map(nome_proj))
        st.dataframe(v[["projeto", "titulo", "depende_de", "prioridade", "status", "prazo"]], width="stretch", hide_index=True)

elif pagina == "Metricas":
    st.title("Indicadores e entregas")
    if mets.empty:
        st.info("Catalogo vazio. A ponte carrega a matriz do ENERDATA.")
    else:
        f1, f2, f3 = st.columns(3)
        tipo = f1.multiselect("Tipo", ["indicador", "entrega"], default=["indicador", "entrega"])
        resp = f2.multiselect("Responsavel", sorted(mets["responsavel"].dropna().unique()))
        sit = f3.multiselect("Situacao", sorted(mets["situacao"].dropna().unique()))
        v = mets[mets["tipo"].isin(tipo)]
        if resp:
            v = v[v["responsavel"].isin(resp)]
        if sit:
            v = v[v["situacao"].isin(sit)]
        nome_proj = dict(zip(proj["id"], proj["sigla"])) if not proj.empty else {}
        v = v.assign(projeto=v["projeto_id"].map(nome_proj))
        st.caption(f"{len(v)} de {len(mets)} itens")
        st.dataframe(v[["codigo", "tipo", "nome", "responsavel", "meta", "periodicidade", "projeto", "fonte", "situacao"]],
                     width="stretch", hide_index=True)

elif pagina == "Fila de comandos":
    st.title("Fila de comandos do Jarvis")
    st.caption("O Jarvis propoe, o Rafael aprova, so o aprovado roda. Nesta versao a fila e so de leitura.")
    if fila.empty:
        st.info("Fila vazia.")
    else:
        st.dataframe(fila[["codigo", "titulo", "status", "proposto_por", "criado_em", "concluido_em"]], width="stretch", hide_index=True)

st.markdown(
    f"""<div style="margin-top:2rem;padding-top:.75rem;border-top:1px solid rgba(245,246,250,.12);font-size:.72rem;color:rgba(245,246,250,.45);">
Jarvis Mark 1 · painel v{APP_VERSION} · leitura do schema gestao · rafael.nakahara@enermais.com.br</div>""",
    unsafe_allow_html=True,
)
