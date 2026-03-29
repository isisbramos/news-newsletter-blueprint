#!/usr/bin/env python3
"""
News Newsletter Blueprint — Setup Wizard
Guia interativo para criar um novo projeto de newsletter.
Roda o cookiecutter com as respostas que você der aqui.

Usage: python setup_wizard.py
"""

import subprocess
import sys
import json
import os

RESET = "\033[0m"
BOLD = "\033[1m"
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
DIM = "\033[2m"


def print_header():
    print(f"\n{CYAN}{BOLD}")
    print("╔══════════════════════════════════════════════════════╗")
    print("║       🗞️  NEWS NEWSLETTER BLUEPRINT WIZARD           ║")
    print("║       Crie sua newsletter automatizada em minutos    ║")
    print("╚══════════════════════════════════════════════════════╝")
    print(RESET)
    print(f"{DIM}Baseado no Daily Scout (tech & AI). Responda as perguntas abaixo.")
    print(f"Dica: aperte Enter pra aceitar o padrão entre [colchetes].{RESET}\n")


def ask(question: str, default: str = "", options: list[str] | None = None, hint: str = "") -> str:
    """Ask a question and return the answer."""
    if options:
        print(f"{BOLD}{question}{RESET}")
        for i, opt in enumerate(options, 1):
            marker = f"{GREEN}[padrão]{RESET} " if i == 1 else "          "
            print(f"  {marker}{CYAN}{i}{RESET}. {opt}")
        if hint:
            print(f"  {DIM}{hint}{RESET}")
        while True:
            raw = input(f"\n  → Escolha [1-{len(options)}] (Enter = 1): ").strip()
            if raw == "":
                return options[0]
            try:
                idx = int(raw) - 1
                if 0 <= idx < len(options):
                    return options[idx]
            except ValueError:
                # Allow direct text input
                return raw
            print(f"  {RED}Por favor escolha um número entre 1 e {len(options)}{RESET}")
    else:
        if default:
            prompt = f"{BOLD}{question}{RESET} [{GREEN}{default}{RESET}]: "
        else:
            prompt = f"{BOLD}{question}{RESET}: "
        if hint:
            print(f"  {DIM}{hint}{RESET}")
        raw = input(prompt).strip()
        return raw if raw else default


def slugify(name: str) -> str:
    return name.lower().replace(" ", "-").replace("_", "-")


def cron_for_frequency(freq: str, time_utc: str) -> str:
    hour, minute = time_utc.split(":")
    schedules = {
        "daily": f"{minute} {hour} * * *",
        "weekly-monday": f"{minute} {hour} * * 1",
        "weekly-friday": f"{minute} {hour} * * 5",
    }
    return schedules.get(freq, f"{minute} {hour} * * *")


def section(title: str):
    print(f"\n{CYAN}── {title} {'─' * (45 - len(title))}{RESET}")


def collect_answers() -> dict:
    answers = {}

    # ── IDENTIDADE ──
    section("IDENTIDADE DA NEWSLETTER")

    answers["project_name"] = ask(
        "Nome da newsletter",
        default="Finance Scout",
        hint="Ex: Finance Scout, Health Weekly, Crypto Radar..."
    )
    answers["project_slug"] = slugify(answers["project_name"])
    print(f"  {DIM}→ Slug gerado: {answers['project_slug']}{RESET}")

    answers["correspondent_name"] = ask(
        "Nome da correspondente (persona da IA)",
        default="AYA",
        hint="É quem 'escreve' a newsletter. Ex: AYA, MAIA, SCOUT, FINN..."
    )
    answers["correspondent_role"] = ask(
        "Papel da correspondente",
        default="analista de campo",
        hint="Ex: analista de mercado, repórter financeira, curador de saúde..."
    )
    answers["correspondent_tagline"] = ask(
        "Tagline da correspondente",
        default="curadoria com contexto, sem hype",
        hint="Uma frase curta que define o tom. Ex: 'só o que importa, sem noise'"
    )

    # ── CONTEÚDO ──
    section("TEMA E AUDIÊNCIA")

    answers["newsletter_topic"] = ask(
        "Qual é o tema da newsletter?",
        default="tech & AI",
        hint="Ex: finanças pessoais, saúde & longevidade, startups, crypto, política tech..."
    )
    answers["newsletter_topic_short"] = ask(
        "Tema abreviado (1-2 palavras)",
        default=answers["newsletter_topic"].split("&")[0].strip(),
        hint="Ex: 'finanças', 'saúde', 'tech'. Usado em alguns títulos."
    )
    answers["newsletter_audience"] = ask(
        "Quem é o seu leitor?",
        default="profissionais curiosos",
        hint="Ex: 'investidores pessoa física', 'devs que querem entender negócios', 'gestores de saúde'..."
    )

    answers["newsletter_language"] = ask(
        "Idioma da newsletter",
        options=["pt-BR", "en-US"],
        hint="O idioma em que a correspondente vai escrever."
    )

    # ── CURADORIA ──
    section("ESTILO DE CURADORIA")

    answers["curation_style"] = ask(
        "Qual o estilo de curadoria?",
        options=["daily-digest", "weekly-roundup", "deep-dive"],
        hint="daily-digest: 1 destaque + 3-5 achados. weekly-roundup: top-5 da semana. deep-dive: 1 tema em profundidade."
    )

    answers["topic_gate_description"] = ask(
        "O que qualifica um post como relevante pro seu tema?",
        default=f"O post tem conexão direta com {answers['newsletter_topic']}?",
        hint="Será usado pelo LLM pra filtrar o que entra. Quanto mais específico, melhor a curadoria."
    )

    answers["anti_signal_examples"] = ask(
        "O que deve ser excluído automaticamente?",
        default="posts genéricos, conteúdo de entretenimento, clickbait sem substância",
        hint="Liste categorias que devem ser descartadas mesmo se tiverem engajamento alto."
    )

    print(f"\n  {DIM}Subreddits do seu tema (separados por vírgula):{RESET}")
    print(f"  {DIM}Ex: personalfinance, investing, financialindependence{RESET}")
    answers["reddit_subreddits"] = ask(
        "Subreddits para monitorar",
        default="artificial, MachineLearning, technology, programming",
        hint=""
    )

    # ── FREQUÊNCIA ──
    section("FREQUÊNCIA E ENTREGA")

    answers["schedule_frequency"] = ask(
        "Com que frequência vai rodar?",
        options=["daily", "weekly-monday", "weekly-friday"],
        hint="daily = todos os dias. weekly = uma vez por semana."
    )

    time_input = ask(
        "Horário de envio (formato HH:MM, fuso UTC)",
        default="10:00",
        hint="10:00 UTC = 07:00 BRT (Brasília). 13:00 UTC = 10:00 BRT."
    )
    answers["schedule_time_utc"] = time_input
    answers["schedule_cron"] = cron_for_frequency(answers["schedule_frequency"], time_input)

    answers["launch_date"] = ask(
        "Data de lançamento (YYYY-MM-DD)",
        default="2026-01-01",
        hint="Usada pra calcular o número da edição automaticamente."
    )

    answers["delivery_platform"] = ask(
        "Plataforma de envio de email",
        options=["buttondown", "none"],
        hint="Buttondown é gratuito até 100 subscribers. 'none' = só gera o HTML."
    )

    # ── LLM ──
    section("MODELO DE IA")

    answers["llm_provider"] = ask(
        "Qual IA vai fazer a curadoria?",
        options=["gemini", "openai"],
        hint="Gemini tem tier gratuito generoso. OpenAI é pago mas muito bom."
    )

    if answers["llm_provider"] == "gemini":
        answers["llm_model"] = ask(
            "Qual modelo do Gemini?",
            options=["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"],
            hint="gemini-2.5-flash é o melhor custo-benefício atual."
        )
    else:
        answers["llm_model"] = ask(
            "Qual modelo da OpenAI?",
            options=["gpt-4o-mini", "gpt-4o", "gpt-4.1-mini"],
            hint="gpt-4o-mini é o mais barato."
        )

    # ── SOCIAL ──
    section("SOCIAL (OPCIONAL)")

    answers["social_linkedin"] = ask(
        "Quer postar automaticamente no LinkedIn depois do envio?",
        options=["no", "yes"],
        hint="Requer configuração adicional de API credentials do LinkedIn."
    )

    # ── META ──
    section("META")

    answers["github_username"] = ask(
        "Seu username no GitHub",
        default="your-username",
        hint="Usado nos URLs internos do projeto."
    )
    answers["author_name"] = ask(
        "Seu nome (para o README)",
        default="Author"
    )

    return answers


def preview_answers(answers: dict):
    print(f"\n{YELLOW}{BOLD}══ RESUMO DO PROJETO ══════════════════════════════{RESET}")
    print(f"  📰  Nome: {BOLD}{answers['project_name']}{RESET}")
    print(f"  🤖  Persona: {answers['correspondent_name']} ({answers['correspondent_role']})")
    print(f"  🎯  Tema: {answers['newsletter_topic']} → audiência: {answers['newsletter_audience']}")
    print(f"  📋  Estilo: {answers['curation_style']}")
    print(f"  ⏰  Frequência: {answers['schedule_frequency']} às {answers['schedule_time_utc']} UTC")
    print(f"  📬  Entrega: {answers['delivery_platform']}")
    print(f"  🧠  LLM: {answers['llm_provider']} / {answers['llm_model']}")
    print(f"  📁  Slug: {answers['project_slug']}")
    print(f"{YELLOW}{'─' * 50}{RESET}")


def ensure_cookiecutter():
    try:
        import cookiecutter  # noqa: F401
    except ImportError:
        print(f"\n{YELLOW}Instalando cookiecutter...{RESET}")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "cookiecutter", "-q"])
        print(f"{GREEN}✓ Cookiecutter instalado{RESET}")


def write_config(answers: dict, path: str = "/tmp/blueprint_answers.json"):
    with open(path, "w") as f:
        json.dump(answers, f, indent=2, ensure_ascii=False)
    return path


def run():
    print_header()

    try:
        answers = collect_answers()
    except KeyboardInterrupt:
        print(f"\n\n{RED}Cancelado.{RESET}")
        sys.exit(0)

    preview_answers(answers)

    confirm = input(f"\n{BOLD}Gerar o projeto com essas configurações? [S/n]: {RESET}").strip().lower()
    if confirm in ("n", "no", "não", "nao"):
        print(f"\n{YELLOW}Cancelado. Rode novamente quando quiser.{RESET}")
        sys.exit(0)

    ensure_cookiecutter()

    # Write answers to temp file for cookiecutter
    config_path = write_config(answers)

    # Template dir = the directory where this script lives
    template_dir = os.path.dirname(os.path.abspath(__file__))

    print(f"\n{CYAN}Gerando projeto...{RESET}")
    try:
        from cookiecutter.main import cookiecutter
        output_dir = cookiecutter(
            template_dir,
            no_input=True,
            extra_context=answers,
            output_dir="."
        )
        print(f"\n{GREEN}{BOLD}✅ Projeto gerado com sucesso!{RESET}")
        print(f"\n  📁 Pasta: {BOLD}{output_dir}{RESET}")
        print(f"\n  Próximos passos:")
        print(f"  1. {CYAN}cd {answers['project_slug']}{RESET}")
        print(f"  2. {CYAN}pip install -r requirements.txt{RESET}")
        print(f"  3. Configure seus secrets (veja SETUP_GUIDE.md)")
        print(f"  4. {CYAN}DRY_RUN=true GEMINI_API_KEY=sua-key python pipeline.py{RESET}")
        print(f"\n  📖 Leia o SETUP_GUIDE.md pra mais detalhes.\n")
    except Exception as e:
        print(f"\n{RED}Erro ao gerar projeto: {e}{RESET}")
        print(f"Tente rodar manualmente: cookiecutter .")
        sys.exit(1)


if __name__ == "__main__":
    run()
