# Jarvis Mark 1 — painel

Painel Streamlit (somente leitura) do acompanhamento de projetos EnerMais. Dados no Supabase (schema `gestao`), alimentados por uma ponte que lê o vault Obsidian. Login obrigatório (Supabase Auth); só quem está em `gestao.usuarios_autorizados` vê dados.

- Secrets: `SUPABASE_URL` e `SUPABASE_PUBLISHABLE_KEY` (chave pública). A chave secreta nunca entra neste repositório nem no Streamlit.
- Deploy: Streamlit Community Cloud, arquivo principal `app.py`.
