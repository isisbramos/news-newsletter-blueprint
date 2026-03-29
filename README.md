# 🗞️ News Newsletter Blueprint

Template cookiecutter para criar newsletters automatizadas com curadoria por IA.
Baseado no **Daily Scout** (tech & AI). Funciona para qualquer tema.

## O que este template gera

Um projeto completo com:
- Pipeline multi-source (Reddit, HN, RSS)
- Curadoria por LLM com persona configurável
- Email HTML responsivo via Jinja2
- Entrega por Buttondown (ou só HTML local)
- GitHub Actions para automação (diária ou semanal)
- (Opcional) Post automático no LinkedIn

## Como usar

### Opção 1 — Wizard interativo (recomendado para não-técnicos)

```bash
python setup_wizard.py
```

Responde perguntas em linguagem humana → gera o projeto.

### Opção 2 — Cookiecutter direto (para devs)

```bash
pip install cookiecutter
cookiecutter .
```

Preenche as variáveis do `cookiecutter.json`.

## Variáveis do template

| Variável | Descrição | Exemplo |
|----------|-----------|---------|
| `project_name` | Nome da newsletter | "Finance Scout" |
| `correspondent_name` | Nome da persona IA | "MAIA" |
| `newsletter_topic` | Tema central | "finanças pessoais" |
| `newsletter_audience` | Quem lê | "investidores pessoa física" |
| `newsletter_language` | Idioma | "pt-BR" ou "en-US" |
| `curation_style` | Estilo editorial | "daily-digest", "weekly-roundup", "deep-dive" |
| `topic_gate_description` | O que qualifica como relevante | "Post tem conexão com finanças pessoais?" |
| `anti_signal_examples` | O que descartar | "crypto especulativa, celebridades..." |
| `reddit_subreddits` | Subreddits para monitorar | "personalfinance, investing" |
| `schedule_frequency` | Frequência | "daily", "weekly-monday", "weekly-friday" |
| `schedule_time_utc` | Horário UTC | "10:00" |
| `delivery_platform` | Plataforma de envio | "buttondown", "none" |
| `llm_provider` | Qual IA | "gemini", "openai" |
| `llm_model` | Modelo específico | "gemini-2.5-flash" |
| `social_linkedin` | Post no LinkedIn? | "yes", "no" |
| `github_username` | Seu GitHub | "your-username" |

## Estrutura do template

```
blueprint/
├── cookiecutter.json              ← spec de variáveis
├── README.md                      ← este arquivo
├── SETUP_GUIDE.md                 ← guia passo-a-passo para usuários
├── setup_wizard.py                ← wizard interativo
└── {{cookiecutter.project_slug}}/
    ├── pipeline.py                ← ponto de entrada (templateizado)
    ├── sources_config.json        ← fontes (templateizado)
    ├── prompts/
    │   ├── system_instruction.txt ← persona (templateizado)
    │   └── curation_template.txt  ← regras de curadoria (templateizado)
    ├── templates/email.html       ← email HTML (copy-without-render)
    ├── sources/                   ← módulos de coleta (infraestrutura)
    ├── delivery.py                ← módulo de envio (infraestrutura)
    ├── pre_filter.py              ← pré-filtro (infraestrutura)
    ├── schemas.py                 ← schemas LLM (infraestrutura)
    └── .github/workflows/
        └── newsletter.yml        ← GitHub Actions (templateizado)
```

## Depois de gerar o projeto

1. Leia `SETUP_GUIDE.md` — passo a passo completo
2. Configure seus secrets no GitHub Actions
3. Edite `sources_config.json` pras fontes do seu tema
4. Adicione exemplos de calibração em `prompts/curation_template.txt`
5. Rode `DRY_RUN=true python pipeline.py` pra testar

---

Criado a partir do [Daily Scout](https://github.com/isisbramos/daily-scout).
