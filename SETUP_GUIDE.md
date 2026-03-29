# 🗞️ News Newsletter Blueprint — Setup Guide

> Este template gera um projeto completo de newsletter automatizada com curadoria por IA.
> Baseado no Daily Scout (tech & AI). Não precisa saber programar pra usar — siga os passos.

---

## O que você vai ter no final

Um projeto que:
- Coleta conteúdo de múltiplas fontes (Reddit, HN, RSS, etc.) automaticamente
- Usa IA (Gemini ou GPT) para curar e escrever a newsletter com a sua persona
- Envia por e-mail via Buttondown (ou outra plataforma)
- Roda automaticamente no GitHub Actions, na hora que você escolher
- (Opcional) Posta no LinkedIn depois do envio

**Tempo estimado de setup: 30–45 minutos.**

---

## Pré-requisitos (o que você precisa ter)

### 1. Conta no GitHub
- Crie em [github.com](https://github.com) se não tiver
- Você vai guardar o código aqui — de graça

### 2. API Key do Gemini (ou OpenAI)
- **Gemini (recomendado — gratuito no tier básico):**
  Acesse [aistudio.google.com/apikey](https://aistudio.google.com/apikey) → "Create API Key"
- **OpenAI (alternativa paga):**
  Acesse [platform.openai.com/api-keys](https://platform.openai.com/api-keys) → "Create new secret key"

### 3. Conta no Buttondown (se quiser enviar por e-mail)
- Crie em [buttondown.email](https://buttondown.email) — gratuito até 100 subscribers
- Após criar: vá em Settings → API Keys → copie sua key

### 4. Python 3.10+ no seu computador
- Verifique: abra o Terminal e digite `python3 --version`
- Se não tiver: [python.org/downloads](https://python.org/downloads)

---

## Passo a passo

### PASSO 1 — Gere seu projeto com o wizard

No Terminal, dentro da pasta onde você quer criar o projeto:

```bash
# Instala o cookiecutter (só na primeira vez)
pip install cookiecutter

# Roda o wizard interativo
python setup_wizard.py
```

O wizard vai te perguntar tudo em linguagem humana e gerar o projeto automaticamente.

**Alternativa (avançado):** rode direto o cookiecutter:
```bash
cookiecutter .
```
Ele vai pedir as variáveis pelo nome técnico (definidas em `cookiecutter.json`).

---

### PASSO 2 — Crie o repositório no GitHub

1. Vá em [github.com/new](https://github.com/new)
2. Nome do repositório: o mesmo `project_slug` que você escolheu (ex: `finance-scout`)
3. Marque como **Private** se quiser manter privado
4. **Não** inicialize com README
5. Clique em "Create repository"

No Terminal, dentro da pasta gerada:
```bash
git init
git add .
git commit -m "feat: initial setup from blueprint"
git remote add origin https://github.com/SEU_USERNAME/NOME_DO_REPO.git
git push -u origin main
```

---

### PASSO 3 — Configure os secrets no GitHub

No GitHub, vá em: `Settings → Secrets and variables → Actions → New repository secret`

Adicione os seguintes secrets:

| Secret | Onde pegar | Obrigatório? |
|--------|-----------|--------------|
| `GEMINI_API_KEY` | Google AI Studio | Sim (se usar Gemini) |
| `OPENAI_API_KEY` | OpenAI Platform | Sim (se usar OpenAI) |
| `BUTTONDOWN_API_KEY` | Buttondown Settings | Só se quiser enviar email |
| `FEEDBACK_BASE_URL` | URL do seu GitHub Pages (ex: `https://SEU_USER.github.io/REPO/feedback.html`) | Não (opcional) |

---

### PASSO 4 — Configure as fontes

Abra o arquivo `sources_config.json` e ajuste:

- **`reddit.subreddits`**: troque pelos subreddits do seu tema
- **`hackernews`**: mantenha se o seu tema for tech
- **Fontes RSS extras**: adicione qualquer site que tenha feed RSS no bloco `rss_generic`

Para encontrar o RSS de um site: geralmente é `https://siteexemplo.com/feed` ou `https://siteexemplo.com/rss`

---

### PASSO 5 — Ajuste a persona

Abra `prompts/system_instruction.txt` e customize:

- Nome da correspondente (já preenchido pelo wizard)
- Tom de voz
- Exemplos de calibração (os exemplos com `Exemplo 1`, `Exemplo 2`...)

Quanto mais exemplos relevantes pro seu tema você colocar, melhor a qualidade da curadoria.

---

### PASSO 6 — Teste antes de enviar

No Terminal, dentro da pasta do projeto:

```bash
pip install -r requirements.txt
export GEMINI_API_KEY="sua-key-aqui"
export DRY_RUN=true
python pipeline.py
```

Isso roda o pipeline completo mas **não envia** o email. Você vai ver o HTML gerado em `output/`.

Se tudo correu bem, o output vai ter um arquivo `output/edition_001.html`. Abra no browser pra visualizar.

---

### PASSO 7 — Ative o envio automático

No GitHub, vá em: `Actions → Daily Scout Pipeline → Enable workflow`

O workflow vai rodar automaticamente no horário que você configurou. Você também pode rodar manualmente clicando em "Run workflow".

---

## Variáveis configuráveis (referência rápida)

| Variável | O que controla | Onde editar |
|----------|---------------|-------------|
| `correspondent_name` | Nome da persona da newsletter | `prompts/system_instruction.txt` |
| `newsletter_topic` | Tema central (afeta o filtro de curadoria) | `prompts/curation_template.txt` |
| `curation_style` | Estilo: digest diário, roundup semanal, deep-dive | `prompts/curation_template.txt` |
| `reddit_subreddits` | Quais subreddits monitorar | `sources_config.json` |
| `schedule_cron` | Quando roda (UTC) | `.github/workflows/newsletter.yml` |
| `delivery_platform` | Onde envia (Buttondown, etc.) | `delivery.py` |

---

## Problemas comuns

**"ModuleNotFoundError"** → rode `pip install -r requirements.txt`

**"GEMINI_API_KEY não configurada"** → verifique se exportou a variável: `export GEMINI_API_KEY="sua-key"`

**Email não está enviando** → verifique se `DRY_RUN=false` e se `BUTTONDOWN_API_KEY` está correta

**Curadoria está incluindo tópicos fora do tema** → edite o `TOPIC GATE` em `prompts/curation_template.txt` pra deixar mais restritivo

**Qualidade do texto ruim** → adicione mais exemplos de calibração em `prompts/curation_template.txt` (seção `═══ EXEMPLOS DE CALIBRAÇÃO ═══`)

---

## Estrutura do projeto gerado

```
seu-projeto/
├── pipeline.py              ← ponto de entrada principal
├── sources_config.json      ← configure suas fontes aqui
├── prompts/
│   ├── system_instruction.txt   ← personalidade da correspondente
│   └── curation_template.txt    ← regras de curadoria + exemplos
├── templates/
│   └── email.html           ← layout do email (HTML)
├── sources/                 ← módulos de coleta (não precisa mexer)
├── delivery.py              ← módulo de envio
├── .github/workflows/
│   └── newsletter.yml       ← automação GitHub Actions
└── output/                  ← HTMLs gerados ficam aqui
```

---

Dúvidas? Abra uma issue no repositório template ou entre em contato com quem te indicou.
