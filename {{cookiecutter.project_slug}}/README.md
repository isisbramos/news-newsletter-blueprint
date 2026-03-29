# {{ cookiecutter.project_name }}

> Newsletter {{ 'diária' if cookiecutter.curation_style == 'daily-digest' else 'semanal' if 'weekly' in cookiecutter.curation_style else 'de análise' }} sobre **{{ cookiecutter.newsletter_topic }}**, curada por **{{ cookiecutter.correspondent_name }}** (AI-powered).
>
> Para {{ cookiecutter.newsletter_audience }}.

---

## Stack

`{{ cookiecutter.newsletter_topic }} sources` → Pre-Filter → `{{ cookiecutter.llm_provider }} / {{ cookiecutter.llm_model }}` → Jinja2 HTML → {% if cookiecutter.delivery_platform == 'buttondown' %}Buttondown API{% else %}HTML output{% endif %}

## Rodando localmente

```bash
pip install -r requirements.txt

# Dry run (não envia email)
export {% if cookiecutter.llm_provider == 'gemini' %}GEMINI_API_KEY{% else %}OPENAI_API_KEY{% endif %}="sua-key-aqui"
export DRY_RUN=true
python pipeline.py
```

O HTML gerado fica em `output/edition_NNN.html`.

## Secrets necessários no GitHub Actions

{% if cookiecutter.llm_provider == 'gemini' -%}
- `GEMINI_API_KEY` — Google AI Studio
{% else -%}
- `OPENAI_API_KEY` — OpenAI Platform
{% endif -%}
{% if cookiecutter.delivery_platform == 'buttondown' -%}
- `BUTTONDOWN_API_KEY` — Buttondown Settings → API Keys
{% endif -%}
- `FEEDBACK_BASE_URL` — (opcional) URL do feedback form no GitHub Pages

## Customizando

| O que mudar | Onde |
|-------------|------|
| Persona, tom de voz | `prompts/system_instruction.txt` |
| Regras de curadoria + exemplos | `prompts/curation_template.txt` |
| Fontes (subreddits, RSS) | `sources_config.json` |
| Layout do email | `templates/email.html` |
| Horário de envio | `.github/workflows/newsletter.yml` → cron |

## Gerado com

[News Newsletter Blueprint](https://github.com/{{ cookiecutter.github_username }}/news-newsletter-blueprint) por {{ cookiecutter.author_name }}.
