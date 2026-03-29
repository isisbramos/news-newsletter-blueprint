"""
Daily Scout — Audit Agent v1.0
LLM-as-Judge para PE study do prompt de curadoria da AYA.

Avalia 3 dimensões:
  1. Output da AYA: editorial alignment, tom, diversidade, intro quality
  2. Reasoning Coherence: o campo 'reasoning' é coerente com a seleção?
  3. False Negatives: bons itens descartados / False Positives: itens ruins selecionados

Requisito: DEBUG_SAVE=true no pipeline para gerar os arquivos de entrada.

Uso:
  python audit_agent.py --edition 001
  python audit_agent.py --all
  python audit_agent.py --edition 001 --verbose

Outputs:
  debug/edition_XXX_audit.json        — structured report (programático)
  debug/edition_XXX_audit_report.md   — human-readable report
"""

import argparse
import json
import os
import sys
import glob
import logging
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel, Field
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("audit-agent")

# ── Config ────────────────────────────────────────────────────────────
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
DEBUG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "debug")

# ── Audit Schema (structured output) ─────────────────────────────────

class DimensionScore(BaseModel):
    score: int = Field(description="Score de 1 a 5. 5 = sem problemas.")
    rationale: str = Field(description="2-3 frases explicando o score.")
    issues: list[str] = Field(
        default_factory=list,
        description="Lista de problemas específicos encontrados. Vazio se score = 5."
    )

class FalseNegative(BaseModel):
    title: str = Field(description="Título do item que ficou de fora")
    source: str = Field(description="Fonte do item")
    why_should_include: str = Field(
        description="1-2 frases: por que este item deveria ter sido selecionado"
    )
    missed_criteria: list[str] = Field(
        description="Quais critérios ele satisfaz? (AI Gate, Acionável, Sinal de mercado, Afeta workflows)"
    )

class FalsePositive(BaseModel):
    title: str = Field(description="Título do item selecionado")
    field: str = Field(description="'main_find' ou 'quick_finds[N]'")
    why_should_discard: str = Field(
        description="1-2 frases: por que este item não deveria ter sido selecionado"
    )
    violated_rule: str = Field(
        description="Qual regra foi violada? (ex: 'STEP 1 - AI Gate', 'STEP 3 - Anti-signal: funding')"
    )

class PromptHypothesis(BaseModel):
    hypothesis: str = Field(
        description="Hipótese sobre o que no prompt causou este erro. Cite o STEP ou regra específica."
    )
    evidence: str = Field(
        description="Qual erro no output é evidência desta hipótese?"
    )
    suggested_fix: str = Field(
        description="1 frase: como corrigir o prompt para evitar este erro?"
    )

class AuditReport(BaseModel):
    edition: str = Field(description="Número da edição auditada")
    audited_at: str = Field(description="Timestamp ISO da auditoria")

    # Dimensão 1: Editorial Alignment
    editorial_alignment: DimensionScore = Field(
        description="Avalia se os itens selecionados passam genuinamente no AI Gate + 2-of-3 critérios + anti-signal."
    )

    # Dimensão 2: Tom e Acurácia
    tone_accuracy: DimensionScore = Field(
        description="Avalia hype language, certeza aumentada e informações inventadas."
    )

    # Dimensão 3: Diversidade
    diversity: DimensionScore = Field(
        description="Avalia diversidade de fontes, audiência e geografia."
    )

    # Dimensão 4: Correspondent Intro
    correspondent_intro_quality: DimensionScore = Field(
        description="Avalia se a intro cita o tema real do achado ou é genérica."
    )

    # Dimensão 5: Reasoning Coherence
    reasoning_coherence: DimensionScore = Field(
        description="Avalia se o campo 'reasoning' é coerente com a seleção e o raciocínio é genuíno."
    )

    # False Negatives / Positives
    false_negatives: list[FalseNegative] = Field(
        default_factory=list,
        description="Até 3 itens do INPUT que deveriam ter sido selecionados mas não foram."
    )
    false_positives: list[FalsePositive] = Field(
        default_factory=list,
        description="Até 3 itens selecionados que não deveriam estar no output."
    )

    # Prompt hypotheses
    prompt_hypotheses: list[PromptHypothesis] = Field(
        default_factory=list,
        description="1-3 hipóteses sobre o que no PROMPT causou os erros encontrados."
    )

    # Overall
    overall_score: int = Field(description="Score geral de 1 a 5. Média ponderada das 5 dimensões.")
    top_issues_summary: str = Field(
        description="2-3 frases resumindo os principais problemas desta edição para um leitor rápido."
    )

# ── Audit System Prompt ────────────────────────────────────────────────
AUDIT_SYSTEM = """Você é um editor sênior exigente de newsletters de tech. Seu papel é auditar as decisões editoriais da AYA — a correspondente de AI do Daily Scout.

MISSÃO: Encontrar falhas, não validar acertos. Seja crítico e específico.
- Se não encontrou problemas numa dimensão, diga isso claramente (score 5) e siga em frente.
- Se encontrou, descreva com precisão: qual item, qual trecho, qual regra foi violada.
- Não invente problemas. Não exagere. Não seja condescendente.

CRITÉRIOS QUE A AYA DEVERIA SEGUIR (resumo):

AI GATE (obrigatório): o item tem conexão com AI/ML, automação inteligente, ou decisão de empresa de AI?
→ Exceção: magnitude excepcional (aquisição >$1B, regulação governamental, shutdown de plataforma major).

CRITÉRIOS DE SELEÇÃO (precisa de pelo menos 2 de 3):
1. Acionável — o leitor pode testar ferramenta, mudar processo, tomar decisão
2. Sinal de mercado — revela movimento estratégico: player mudando de categoria, shift de política, M&A
3. Afeta workflows — muda como pessoas trabalham com tech/AI no dia a dia

ANTI-SIGNALS (descartar):
- Preço/assinatura consumer (Netflix, Spotify)
- Funding round sem info nova (feature, produto, shift de estratégia) — exceto >$5B ou OpenAI/Anthropic/DeepMind
- Crypto/apostas sem AI
- Rehashed news (evento já reportado sem info nova)
- Blog corporativo de thought-leadership sem novidade concreta

RANKING: main_find = mais acionável OU maior sinal de mercado. Tração (score) é tiebreaker NUNCA critério principal.
main_find deve ser sobre UM evento singular (não roundup/compilação).

TOM: frases curtas, verbos factuais, zero hype. Preservar nível de certeza do título original (may/might → condicional)."""


# ── Audit User Prompt ──────────────────────────────────────────────────
def build_audit_prompt(edition: str, curation_output: dict, input_items: list[dict]) -> str:
    return f"""Audite a edição #{edition} do Daily Scout.

═══ INPUT (itens que entraram no LLM) ═══
{json.dumps(input_items, ensure_ascii=False, indent=2)}

═══ OUTPUT DA AYA ═══
{json.dumps(curation_output, ensure_ascii=False, indent=2)}

═══ INSTRUÇÕES DE AUDITORIA ═══

Avalie CINCO dimensões:

DIMENSÃO 1 — EDITORIAL ALIGNMENT (score 1-5)
Para cada item no output (main_find + quick_finds), verifique:
- Passa no AI Gate?
- Satisfaz pelo menos 2 dos 3 critérios?
- Não é anti-signal?
Identifique qualquer item que não deveria ter sido selecionado (false positive).

DIMENSÃO 2 — TOM E ACURÁCIA (score 1-5)
Leia o main_find.body, main_find.bullets, e cada quick_find.signal.
Verifique:
- Palavras de hype: revolucion*, bombástic*, massiv*, enorme, game-changer, impressionant*, incrível
- Certeza aumentada: título com "may/might/could/reportedly" virou afirmação direta?
- Informação inventada: algum detalhe no texto que não estava no título?

DIMENSÃO 3 — DIVERSIDADE (score 1-5)
- Fontes: mais de 2 itens do mesmo source entre main_find + quick_finds?
- Audiência: todos os primary_audience são "developers"? Há pelo menos 1 diferente?
- Geografia: mais de 2 itens da mesma região (ex: todos dos EUA, ou 3+ da China)?

DIMENSÃO 4 — CORRESPONDENT INTRO (score 1-5)
Leia o campo correspondent_intro.
- A PRIMEIRA frase menciona o tema específico do main_find?
- Ou é genérica (poderia servir para qualquer edição)?

DIMENSÃO 5 — REASONING COHERENCE (score 1-5)
Leia o campo reasoning.
- Os itens em ai_gate_passed são coerentes com o que foi selecionado?
- O main_find_rationale explica por que AQUELE item e não outro?
- A perspective_check é observação real ou frase de preenchimento?
- Há contradição entre o que o reasoning descreve e o que foi efetivamente selecionado?

FALSE NEGATIVES (até 3):
Olhe os itens do INPUT que NÃO aparecem no output.
Identifique até 3 que deveriam ter sido selecionados mas ficaram de fora.

FALSE POSITIVES (até 3):
Identifique até 3 itens no OUTPUT que não deveriam estar lá.

PROMPT HYPOTHESES (1-3):
Com base nos erros encontrados, aponte hipóteses sobre O QUE NO PROMPT causou esses erros.
Seja específico: cite o STEP, a regra ou o few-shot que pode ter levado ao comportamento errado.

OVERALL SCORE (1-5):
Score geral, considerando as 5 dimensões. 5 = edição excelente sem problemas. 1 = múltiplas falhas graves.
"""


# ── Load debug files ───────────────────────────────────────────────────
def load_edition_files(edition: str) -> tuple[dict, list[dict]]:
    """Carrega os arquivos de debug de uma edição."""
    curation_path = os.path.join(DEBUG_DIR, f"edition_{edition}_curation.json")
    items_path = os.path.join(DEBUG_DIR, f"edition_{edition}_items.json")

    if not os.path.exists(curation_path):
        raise FileNotFoundError(
            f"Curation output não encontrado: {curation_path}\n"
            f"Execute o pipeline com DEBUG_SAVE=true para gerar os arquivos."
        )
    if not os.path.exists(items_path):
        raise FileNotFoundError(
            f"Pre-filter items não encontrado: {items_path}\n"
            f"Execute o pipeline com DEBUG_SAVE=true para gerar os arquivos."
        )

    with open(curation_path, "r", encoding="utf-8") as f:
        curation_output = json.load(f)
    with open(items_path, "r", encoding="utf-8") as f:
        input_items = json.load(f)

    logger.info(f"Loaded edition {edition}: {len(input_items)} input items, curation output OK")
    return curation_output, input_items


# ── Run audit via Gemini ───────────────────────────────────────────────
def run_audit(edition: str, curation_output: dict, input_items: list[dict]) -> AuditReport:
    """Chama Gemini como LLM-as-Judge e retorna o AuditReport estruturado."""
    from google import genai
    from google.genai import types

    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY não configurada")

    client = genai.Client(api_key=GEMINI_API_KEY)

    user_prompt = build_audit_prompt(edition, curation_output, input_items)
    logger.info(f"Audit prompt: {len(user_prompt)} chars")

    brt = timezone(timedelta(hours=-3))
    audited_at = datetime.now(brt).isoformat()

    logger.info("Calling Gemini (audit)...")
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=user_prompt,
        config=types.GenerateContentConfig(
            system_instruction=AUDIT_SYSTEM,
            response_mime_type="application/json",
            response_schema=AuditReport,
            temperature=0.0,
            max_output_tokens=8192,
        ),
    )

    finish_reason = None
    if response.candidates and response.candidates[0].finish_reason:
        finish_reason = response.candidates[0].finish_reason
    logger.info(f"Gemini audit returned {len(response.text)} chars (finish_reason={finish_reason})")

    raw = json.loads(response.text.strip())
    # Injeta edition e timestamp (podem não vir preenchidos corretamente)
    raw["edition"] = edition
    raw["audited_at"] = audited_at

    return AuditReport(**raw)


# ── Save outputs ───────────────────────────────────────────────────────
def save_audit_report(edition: str, report: AuditReport) -> tuple[str, str]:
    """Salva o audit report em JSON e Markdown. Retorna os paths."""
    os.makedirs(DEBUG_DIR, exist_ok=True)

    # JSON (programático)
    json_path = os.path.join(DEBUG_DIR, f"edition_{edition}_audit.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report.model_dump(), f, ensure_ascii=False, indent=2)

    # Markdown (human-readable)
    md_path = os.path.join(DEBUG_DIR, f"edition_{edition}_audit_report.md")
    md = build_markdown_report(edition, report)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md)

    return json_path, md_path


def score_emoji(score: int) -> str:
    return {5: "🟢", 4: "🟡", 3: "🟠", 2: "🔴", 1: "🔴"}.get(score, "⚪")


def build_markdown_report(edition: str, r: AuditReport) -> str:
    lines = [
        f"# Daily Scout — Audit Report — Edição #{edition}",
        f"",
        f"**Auditado em:** {r.audited_at}  ",
        f"**Overall Score:** {score_emoji(r.overall_score)} {r.overall_score}/5",
        f"",
        f"> {r.top_issues_summary}",
        f"",
        f"---",
        f"",
        f"## Scores por Dimensão",
        f"",
        f"| Dimensão | Score | Resumo |",
        f"|---|---|---|",
        f"| Editorial Alignment | {score_emoji(r.editorial_alignment.score)} {r.editorial_alignment.score}/5 | {r.editorial_alignment.rationale[:80]}... |",
        f"| Tom e Acurácia | {score_emoji(r.tone_accuracy.score)} {r.tone_accuracy.score}/5 | {r.tone_accuracy.rationale[:80]}... |",
        f"| Diversidade | {score_emoji(r.diversity.score)} {r.diversity.score}/5 | {r.diversity.rationale[:80]}... |",
        f"| Correspondent Intro | {score_emoji(r.correspondent_intro_quality.score)} {r.correspondent_intro_quality.score}/5 | {r.correspondent_intro_quality.rationale[:80]}... |",
        f"| Reasoning Coherence | {score_emoji(r.reasoning_coherence.score)} {r.reasoning_coherence.score}/5 | {r.reasoning_coherence.rationale[:80]}... |",
        f"",
        f"---",
        f"",
        f"## Detalhes por Dimensão",
        f"",
    ]

    for dim_name, dim in [
        ("Editorial Alignment", r.editorial_alignment),
        ("Tom e Acurácia", r.tone_accuracy),
        ("Diversidade", r.diversity),
        ("Correspondent Intro", r.correspondent_intro_quality),
        ("Reasoning Coherence", r.reasoning_coherence),
    ]:
        lines.append(f"### {score_emoji(dim.score)} {dim_name} — {dim.score}/5")
        lines.append(f"")
        lines.append(dim.rationale)
        if dim.issues:
            lines.append(f"")
            lines.append(f"**Issues encontradas:**")
            for issue in dim.issues:
                lines.append(f"- {issue}")
        lines.append(f"")

    # False Negatives
    if r.false_negatives:
        lines += [
            f"---",
            f"",
            f"## False Negatives (bons itens que ficaram de fora)",
            f"",
        ]
        for fn in r.false_negatives:
            lines += [
                f"### ❌ {fn.title}",
                f"**Fonte:** {fn.source}  ",
                f"**Por que deveria entrar:** {fn.why_should_include}  ",
                f"**Critérios satisfeitos:** {', '.join(fn.missed_criteria)}",
                f"",
            ]

    # False Positives
    if r.false_positives:
        lines += [
            f"---",
            f"",
            f"## False Positives (itens que não deveriam estar no output)",
            f"",
        ]
        for fp in r.false_positives:
            lines += [
                f"### ⚠️ {fp.title}",
                f"**Campo:** `{fp.field}`  ",
                f"**Por que descartar:** {fp.why_should_discard}  ",
                f"**Regra violada:** {fp.violated_rule}",
                f"",
            ]

    # Prompt Hypotheses
    if r.prompt_hypotheses:
        lines += [
            f"---",
            f"",
            f"## Prompt Hypotheses",
            f"",
            f"Hipóteses sobre o que no PROMPT causou esses erros:",
            f"",
        ]
        for i, ph in enumerate(r.prompt_hypotheses, 1):
            lines += [
                f"### Hipótese {i}",
                f"**Hipótese:** {ph.hypothesis}  ",
                f"**Evidência:** {ph.evidence}  ",
                f"**Fix sugerido:** {ph.suggested_fix}",
                f"",
            ]

    lines += [
        f"---",
        f"",
        f"*Generated by Daily Scout Audit Agent v1.0*",
    ]

    return "\n".join(lines)


# ── List available editions ────────────────────────────────────────────
def list_available_editions() -> list[str]:
    """Lista edições com arquivos de debug disponíveis."""
    pattern = os.path.join(DEBUG_DIR, "edition_*_curation.json")
    files = glob.glob(pattern)
    editions = []
    for f in sorted(files):
        name = os.path.basename(f)
        # edition_XXX_curation.json → XXX
        edition = name.split("_")[1]
        editions.append(edition)
    return editions


# ── Print summary to console ───────────────────────────────────────────
def print_summary(edition: str, report: AuditReport, verbose: bool = False):
    print(f"\n{'=' * 60}")
    print(f"AUDIT REPORT — Edição #{edition}")
    print(f"{'=' * 60}")
    print(f"Overall: {score_emoji(report.overall_score)} {report.overall_score}/5")
    print(f"")
    print(f"  Editorial Alignment:   {score_emoji(report.editorial_alignment.score)} {report.editorial_alignment.score}/5")
    print(f"  Tom e Acurácia:        {score_emoji(report.tone_accuracy.score)} {report.tone_accuracy.score}/5")
    print(f"  Diversidade:           {score_emoji(report.diversity.score)} {report.diversity.score}/5")
    print(f"  Correspondent Intro:   {score_emoji(report.correspondent_intro_quality.score)} {report.correspondent_intro_quality.score}/5")
    print(f"  Reasoning Coherence:   {score_emoji(report.reasoning_coherence.score)} {report.reasoning_coherence.score}/5")
    print(f"")
    print(f"False Negatives:  {len(report.false_negatives)}")
    print(f"False Positives:  {len(report.false_positives)}")
    print(f"Prompt Hypotheses: {len(report.prompt_hypotheses)}")
    print(f"")
    print(f"Summary: {report.top_issues_summary}")

    if verbose:
        print(f"\n{'─' * 60}")
        print(f"ISSUES DETALHADAS")
        print(f"{'─' * 60}")

        for dim_name, dim in [
            ("Editorial Alignment", report.editorial_alignment),
            ("Tom e Acurácia", report.tone_accuracy),
            ("Diversidade", report.diversity),
            ("Correspondent Intro", report.correspondent_intro_quality),
            ("Reasoning Coherence", report.reasoning_coherence),
        ]:
            if dim.issues:
                print(f"\n[{dim_name}]")
                for issue in dim.issues:
                    print(f"  • {issue}")

        if report.false_negatives:
            print(f"\n[FALSE NEGATIVES]")
            for fn in report.false_negatives:
                print(f"  ❌ {fn.title}")
                print(f"     {fn.why_should_include}")

        if report.false_positives:
            print(f"\n[FALSE POSITIVES]")
            for fp in report.false_positives:
                print(f"  ⚠️  {fp.title} ({fp.field})")
                print(f"     {fp.why_should_discard}")

        if report.prompt_hypotheses:
            print(f"\n[PROMPT HYPOTHESES]")
            for i, ph in enumerate(report.prompt_hypotheses, 1):
                print(f"  {i}. {ph.hypothesis}")
                print(f"     Fix: {ph.suggested_fix}")

    print(f"{'=' * 60}\n")


# ── Main ───────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Daily Scout — Audit Agent. Avalia o output da AYA como LLM-as-Judge."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--edition", type=str, help="Número da edição a auditar (ex: 001)")
    group.add_argument("--all", action="store_true", help="Audita todas as edições com debug files disponíveis")
    group.add_argument("--list", action="store_true", help="Lista edições disponíveis para auditoria")
    parser.add_argument("--verbose", action="store_true", help="Mostra detalhes dos issues no console")
    parser.add_argument("--dry-run", action="store_true", help="Simula o carregamento sem chamar o LLM")

    args = parser.parse_args()

    if args.list:
        editions = list_available_editions()
        if not editions:
            print(f"Nenhum arquivo de debug encontrado em: {DEBUG_DIR}")
            print("Execute o pipeline com DEBUG_SAVE=true para gerar os arquivos.")
        else:
            print(f"Edições disponíveis para auditoria ({len(editions)}):")
            for e in editions:
                print(f"  - {e}")
        return

    editions_to_audit = []
    if args.all:
        editions_to_audit = list_available_editions()
        if not editions_to_audit:
            logger.error(f"Nenhum arquivo de debug encontrado em: {DEBUG_DIR}")
            logger.error("Execute o pipeline com DEBUG_SAVE=true")
            sys.exit(1)
        logger.info(f"Auditando {len(editions_to_audit)} edições: {editions_to_audit}")
    else:
        editions_to_audit = [args.edition]

    results = []
    for edition in editions_to_audit:
        logger.info(f"\n{'=' * 50}")
        logger.info(f"Auditando edição #{edition}...")

        try:
            curation_output, input_items = load_edition_files(edition)

            if args.dry_run:
                logger.info(f"[DRY RUN] Carregado: {len(input_items)} items de input, output com {len(curation_output.get('quick_finds', []))} quick_finds")
                logger.info(f"[DRY RUN] Skipping LLM call — use sem --dry-run para auditoria real")
                continue

            report = run_audit(edition, curation_output, input_items)
            json_path, md_path = save_audit_report(edition, report)

            logger.info(f"Audit saved: {json_path}")
            logger.info(f"Audit saved: {md_path}")

            print_summary(edition, report, verbose=args.verbose)
            results.append((edition, report))

        except FileNotFoundError as e:
            logger.error(str(e))
            if len(editions_to_audit) == 1:
                sys.exit(1)
        except Exception as e:
            logger.error(f"Erro ao auditar edição {edition}: {e}")
            if len(editions_to_audit) == 1:
                raise

    # Resumo batch (quando --all)
    if len(results) > 1:
        print(f"\n{'═' * 60}")
        print(f"RESUMO BATCH — {len(results)} edições auditadas")
        print(f"{'═' * 60}")
        print(f"{'Edição':<12} {'Overall':<10} {'Editorial':<12} {'Tom':<8} {'Diversidade':<14} {'Intro':<8} {'Reasoning':<12}")
        print(f"{'─' * 76}")
        for edition, r in results:
            print(
                f"#{edition:<11} "
                f"{score_emoji(r.overall_score)}{r.overall_score}/5     "
                f"{score_emoji(r.editorial_alignment.score)}{r.editorial_alignment.score}/5        "
                f"{score_emoji(r.tone_accuracy.score)}{r.tone_accuracy.score}/5    "
                f"{score_emoji(r.diversity.score)}{r.diversity.score}/5          "
                f"{score_emoji(r.correspondent_intro_quality.score)}{r.correspondent_intro_quality.score}/5    "
                f"{score_emoji(r.reasoning_coherence.score)}{r.reasoning_coherence.score}/5"
            )
        avg = sum(r.overall_score for _, r in results) / len(results)
        print(f"\nMédia overall: {avg:.1f}/5")
        print(f"{'═' * 60}\n")


if __name__ == "__main__":
    main()
