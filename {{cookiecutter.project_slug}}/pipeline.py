"""
{{ cookiecutter.project_name }} — Pipeline
Correspondente: {{ cookiecutter.correspondent_name }} ({{ cookiecutter.correspondent_role }})
Tema: {{ cookiecutter.newsletter_topic }}
Style: {{ cookiecutter.curation_style }}
LLM: {{ cookiecutter.llm_provider }} / {{ cookiecutter.llm_model }}
Stack: Sources → Pre-Filter → {{ cookiecutter.llm_model }} (curadoria) → Jinja2 → {% if cookiecutter.delivery_platform == 'buttondown' %}Buttondown{% else %}HTML output{% endif %}

Arquitetura:
  sources/ (pluggable modules) → pre_filter.py → LLM curadoria → Jinja2 render → delivery
  Config-driven: sources_config.json controla tudo sem mudar código.

Gerado com: News Newsletter Blueprint
"""

import os
import random
import re
import sys
import json
import time
import logging
from collections import Counter
from datetime import datetime, timezone, timedelta
from jinja2 import Environment, FileSystemLoader

from sources.base import SourceRegistry, SourceItem
import sources.reddit
import sources.hackernews
import sources.rss_generic
from pre_filter import run_pre_filter
from schemas import Reasoning, MainFind, QuickFind, RadarItem, Meta, CurationOutput
from delivery import send_via_buttondown, send_fallback
from exceptions import FetchError, CurationError, DeliveryError

# ── Logging ──────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("{{ cookiecutter.project_slug }}")

# ── Config ───────────────────────────────────────────────────────────
{% if cookiecutter.llm_provider == 'gemini' -%}
LLM_API_KEY = os.environ.get("GEMINI_API_KEY")
{% else -%}
LLM_API_KEY = os.environ.get("OPENAI_API_KEY")
{% endif -%}
{% if cookiecutter.delivery_platform == 'buttondown' -%}
BUTTONDOWN_API_KEY = os.environ.get("BUTTONDOWN_API_KEY")
{% endif -%}
EDITION_NUMBER = os.environ.get("EDITION_NUMBER", "001")
FEEDBACK_BASE_URL = os.environ.get(
    "FEEDBACK_BASE_URL",
    "https://{{ cookiecutter.github_username }}.github.io/{{ cookiecutter.project_slug }}/feedback.html",
)
CORRESPONDENT_AVATAR_URL = os.environ.get(
    "CORRESPONDENT_AVATAR_URL",
    "",
)
DRY_RUN = os.environ.get("DRY_RUN", "false").lower() == "true"
SOCIAL_ENABLED = os.environ.get("SOCIAL_ENABLED", "false").lower() == "true"
DEBUG_SAVE = os.environ.get("DEBUG_SAVE", "false").lower() == "true"


def load_config() -> dict:
    """Carrega sources_config.json. Fallback pra defaults se não existir."""
    config_paths = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "sources_config.json"),
        "sources_config.json",
    ]
    for path in config_paths:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                config = json.load(f)
            logger.info(f"Config loaded: {path}")
            return config

    logger.warning("sources_config.json not found — using defaults")
    return {
        "sources": {"reddit": {"enabled": True, "weight": 1.0}},
        "pre_filter": {"max_items_to_llm": 40},
        "scoring": {},
    }


def fetch_all_sources(config: dict) -> list[SourceItem]:
    """Instancia sources do config e faz fetch com graceful degradation."""
    logger.info("=" * 50)
    logger.info("PHASE 1: FETCH — collecting from all sources")
    logger.info("=" * 50)

    sources = SourceRegistry.create_sources(config)
    logger.info(f"Active sources: {[s.source_id for s in sources]}")

    all_items: list[SourceItem] = []
    source_stats: dict[str, int] = {}

    for source in sources:
        items = source.safe_fetch()
        source_stats[source.source_id] = len(items)
        all_items.extend(items)

    logger.info(f"Total raw items: {len(all_items)}")
    for sid, count in source_stats.items():
        logger.info(f"  {sid}: {count}")

    return all_items


def filter_items(items: list[SourceItem], config: dict) -> list[SourceItem]:
    """Aplica pre-filter layer: dedup, recency, scoring, token budget."""
    logger.info("=" * 50)
    logger.info("PHASE 2: PRE-FILTER — dedup, score, trim")
    logger.info("=" * 50)
    return run_pre_filter(items, config)


def _load_prompts() -> tuple[str, str]:
    """Carrega system instruction e curation template de arquivos em prompts/."""
    base = os.path.dirname(os.path.abspath(__file__))
    prompts_dir = os.path.join(base, "prompts")

    with open(os.path.join(prompts_dir, "system_instruction.txt"), encoding="utf-8") as f:
        system = f.read().rstrip("\n")

    with open(os.path.join(prompts_dir, "curation_template.txt"), encoding="utf-8") as f:
        template = f.read()

    return system, template


SYSTEM_INSTRUCTION, CURATION_PROMPT_TEMPLATE = _load_prompts()


def _validate_env() -> None:
    """Valida env vars obrigatórias. Fail fast."""
    missing = []
    if not LLM_API_KEY:
        missing.append("{% if cookiecutter.llm_provider == 'gemini' %}GEMINI_API_KEY{% else %}OPENAI_API_KEY{% endif %}")
    {% if cookiecutter.delivery_platform == 'buttondown' -%}
    if not DRY_RUN and not BUTTONDOWN_API_KEY:
        missing.append("BUTTONDOWN_API_KEY")
    {% endif -%}
    if missing:
        logger.error(f"ABORT: env vars obrigatórias ausentes: {', '.join(missing)}")
        sys.exit(1)
    logger.info(f"Env vars OK (DRY_RUN={DRY_RUN})")


HYPE_PATTERNS = re.compile(
    r"(revolucion|bombástic|game.?changer|disruptiv|choque|chocou|impressionant[e]|"
    r"massiv[oa]|enorme[s]?|pesad[oa]|ousad[oa]|incrível|surpreendent[e]|"
    r"grande alarde|aposta pesada|mudou o jogo|prometendo revolucionar)",
    re.IGNORECASE,
)


def validate_tone(content: dict) -> list[str]:
    """Checa heurísticas de sensacionalismo no output."""
    warnings = []

    def _check_text(text: str, field_name: str):
        matches = HYPE_PATTERNS.findall(text)
        for match in matches:
            warnings.append(f"[HYPE] '{match}' encontrado em {field_name}")

    mf = content.get("main_find", {})
    _check_text(mf.get("title", ""), "main_find.title")
    _check_text(mf.get("body", ""), "main_find.body")
    for i, bullet in enumerate(mf.get("bullets", [])):
        _check_text(bullet, f"main_find.bullets[{i}]")
    for i, qf in enumerate(content.get("quick_finds", [])):
        _check_text(qf.get("title", ""), f"quick_finds[{i}].title")
        _check_text(qf.get("signal", ""), f"quick_finds[{i}].signal")
    _check_text(content.get("correspondent_intro", ""), "correspondent_intro")

    return warnings


def curate_and_write(
    filtered_items: list[SourceItem],
    raw_count: int = 0,
    source_breakdown: dict[str, int] | None = None,
    max_retries: int = 5,
) -> dict:
    """Envia items pré-filtrados para o LLM e recebe curadoria estruturada."""
    {% if cookiecutter.llm_provider == 'gemini' -%}
    from google import genai
    from google.genai import types
    {% else -%}
    from openai import OpenAI
    {% endif %}

    logger.info("=" * 50)
    logger.info("PHASE 3: CURATE — LLM processing")
    logger.info("=" * 50)

    if not LLM_API_KEY:
        raise ValueError("LLM API key não configurada")

    {% if cookiecutter.llm_provider == 'gemini' -%}
    client = genai.Client(api_key=LLM_API_KEY)
    {% else -%}
    client = OpenAI(api_key=LLM_API_KEY)
    {% endif %}

    shuffled_items = list(filtered_items)
    random.shuffle(shuffled_items)
    logger.info(f"Shuffled {len(shuffled_items)} items to remove position bias")

    items_for_prompt = []
    for item in shuffled_items:
        entry = {
            "title": item.title[:200],
            "source": item.source_label,
            "score": item.raw_score,
            "comments": item.num_comments,
            "url": item.url,
        }
        if item.cross_source_count > 1:
            entry["also_trending_on"] = [
                sid for sid in item.cross_source_ids if sid != item.source_id
            ]
        items_for_prompt.append(entry)

    source_counts = Counter(item.source_id for item in shuffled_items)
    sources_in_input = ", ".join(f"{sid} ({cnt})" for sid, cnt in source_counts.items())

    if raw_count and source_breakdown:
        breakdown_str = ", ".join(f"{sid}: {cnt}" for sid, cnt in source_breakdown.items())
        context_block = (
            f"CONTEXTO: O pipeline coletou {raw_count} posts de "
            f"{len(source_breakdown)} fontes ({breakdown_str}). "
            f"Após pré-filtragem, você está recebendo os {len(shuffled_items)} "
            f"mais relevantes: {sources_in_input}. "
            f"Use o valor {raw_count} como total_analyzed no meta."
        )
    else:
        context_block = (
            f"CONTEXTO: Você está recebendo {len(shuffled_items)} posts "
            f"pré-filtrados de: {sources_in_input}."
        )

    user_prompt = CURATION_PROMPT_TEMPLATE.format(
        context_block=context_block
    ) + json.dumps(items_for_prompt, ensure_ascii=False, indent=2)

    for attempt in range(max_retries):
        try:
            logger.info(f"LLM attempt {attempt + 1}/{max_retries}...")
            {% if cookiecutter.llm_provider == 'gemini' -%}
            response = client.models.generate_content(
                model="{{ cookiecutter.llm_model }}",
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_INSTRUCTION,
                    response_mime_type="application/json",
                    response_schema=CurationOutput,
                    temperature=0.0,
                    max_output_tokens=16384,
                ),
            )
            finish_reason = None
            if response.candidates and response.candidates[0].finish_reason:
                finish_reason = response.candidates[0].finish_reason

            text = response.text.strip()
            logger.info(f"LLM returned {len(text)} chars (finish_reason={finish_reason})")

            if finish_reason and str(finish_reason) not in ("STOP", "FinishReason.STOP", "1"):
                raise ValueError(f"LLM output truncated (finish_reason={finish_reason})")
            {% else -%}
            response = client.chat.completions.create(
                model="{{ cookiecutter.llm_model }}",
                messages=[
                    {"role": "system", "content": SYSTEM_INSTRUCTION},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.0,
                max_tokens=8192,
            )
            text = response.choices[0].message.content.strip()
            logger.info(f"LLM returned {len(text)} chars")
            {% endif %}

            content = json.loads(text)

            if "main_find" not in content:
                raise ValueError("JSON sem 'main_find'")
            if "title" not in content["main_find"]:
                raise ValueError("main_find sem 'title'")

            mf = content["main_find"]
            mf.setdefault("body", "")
            mf.setdefault("bullets", [])
            mf.setdefault("url", "")
            mf.setdefault("display_url", "")
            mf.setdefault("source", "")

            for qf in content.get("quick_finds", []):
                qf.setdefault("signal", "")
                qf.setdefault("url", "")
                qf.setdefault("display_url", "")
                qf.setdefault("source", "")

            if not content.get("quick_finds"):
                if attempt < max_retries - 1:
                    raise ValueError("LLM returned empty quick_finds — retrying")
                else:
                    content["quick_finds"] = []

            tone_warnings = validate_tone(content)
            if tone_warnings:
                for w in tone_warnings:
                    logger.warning(w)
                if attempt < max_retries - 1:
                    logger.warning(f"Tone check failed — retrying (attempt {attempt + 1})")
                    time.sleep(2**attempt)
                    continue

            if "radar" not in content:
                content["radar"] = []

            reasoning = content.get("reasoning", {})
            if reasoning:
                logger.info(f"[REASONING] Gate passed: {len(reasoning.get('ai_gate_passed', []))} items")
                logger.info(f"  [RATIONALE] {reasoning.get('main_find_rationale', '')}")

            logger.info(f"Curation OK: '{content['main_find']['title']}'")
            logger.info(f"Quick finds: {len(content.get('quick_finds', []))}")
            logger.info(f"Radar items: {len(content.get('radar', []))}")
            return content

        except json.JSONDecodeError as e:
            logger.warning(f"Attempt {attempt + 1}: invalid JSON — {e}")
            if attempt < max_retries - 1:
                time.sleep(2**attempt + random.uniform(0, 1))
        except Exception as e:
            err_str = str(e).lower()
            is_rate_limit = any(
                k in err_str for k in ("429", "resource exhausted", "quota", "rate limit")
            )
            sleep_secs = 60 + random.uniform(0, 15) if is_rate_limit else 2**attempt + random.uniform(0, 1)
            logger.warning(f"Attempt {attempt + 1}: {'rate limit' if is_rate_limit else 'error'} — {e}")
            if attempt < max_retries - 1:
                time.sleep(sleep_secs)

    raise CurationError(f"LLM failed after {max_retries} attempts")


def render_email(
    content: dict,
    raw_count: int,
    filtered_count: int,
    active_sources: list[str],
    runtime: str,
) -> str:
    """Renderiza o template HTML com o conteúdo curado."""
    logger.info("=" * 50)
    logger.info("PHASE 4: RENDER — building email HTML")
    logger.info("=" * 50)

    template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")
    if not os.path.exists(template_dir):
        template_dir = "templates"

    env = Environment(loader=FileSystemLoader(template_dir), autoescape=True)
    template = env.get_template("email.html")

    brt = timezone(timedelta(hours=-3))
    now_brt = datetime.now(brt)

    quick_finds = content.get("quick_finds", [])
    radar = content.get("radar", [])
    meta = content.get("meta", {})
    sources_detail = " + ".join(s.replace("_", " ").title() for s in active_sources)
    total_finds = len(quick_finds) + 1 + len(radar)

    html = template.render(
        correspondent_intro=content.get("correspondent_intro", ""),
        main_find=content["main_find"],
        quick_finds=quick_finds,
        radar=radar,
        edition_number=EDITION_NUMBER,
        date=now_brt.strftime("%d/%m/%Y"),
        sources_count=raw_count,
        finds_count=total_finds,
        sources_detail=sources_detail,
        active_sources=active_sources,
        num_sources=len(active_sources),
        posts_analyzed=meta.get("total_analyzed", filtered_count),
        signal_ratio=f"{total_finds}/{meta.get('total_analyzed', filtered_count)}",
        runtime=runtime,
        feedback_base_url=FEEDBACK_BASE_URL,
        aya_avatar_url=CORRESPONDENT_AVATAR_URL,
        newsletter_name="{{ cookiecutter.project_name }}",
        correspondent_name="{{ cookiecutter.correspondent_name }}",
    )

    logger.info(f"HTML rendered: {len(html)} chars")
    return html


def run_pipeline():
    """Executa o pipeline completo: Config → Fetch → Pre-Filter → Curate → Render → Send."""
    start_time = time.time()

    logger.info("╔══════════════════════════════════════════════════╗")
    logger.info(f"║  {{ cookiecutter.project_name.upper() }} — PIPELINE")
    logger.info(f"║  Correspondente: {{ cookiecutter.correspondent_name }}")
    logger.info(f"║  Tema: {{ cookiecutter.newsletter_topic }}")
    logger.info("╚══════════════════════════════════════════════════╝")

    _validate_env()

    try:
        config = load_config()
        active_sources = [
            sid for sid, conf in config.get("sources", {}).items()
            if isinstance(conf, dict) and conf.get("enabled", True)
            and not sid.startswith("_")
        ]
        logger.info(f"Config: {len(active_sources)} sources: {active_sources}")

        raw_items = fetch_all_sources(config)
        if not raw_items:
            raise FetchError("Nenhuma fonte respondeu.")

        filtered_items = filter_items(raw_items, config)
        if not filtered_items:
            raise FetchError("Pré-filtro descartou todos os items.")

        source_breakdown = {}
        for item in raw_items:
            source_breakdown[item.source_id] = source_breakdown.get(item.source_id, 0) + 1

        content = curate_and_write(
            filtered_items,
            raw_count=len(raw_items),
            source_breakdown=source_breakdown,
        )

        if DEBUG_SAVE:
            debug_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "debug")
            os.makedirs(debug_dir, exist_ok=True)
            with open(os.path.join(debug_dir, f"edition_{EDITION_NUMBER}_curation.json"), "w", encoding="utf-8") as f:
                json.dump(content, f, ensure_ascii=False, indent=2)

        elapsed = f"{time.time() - start_time:.1f}s"
        html = render_email(
            content,
            raw_count=len(raw_items),
            filtered_count=len(filtered_items),
            active_sources=active_sources,
            runtime=elapsed,
        )

        output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, f"edition_{EDITION_NUMBER}.html")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)
        logger.info(f"HTML saved: {output_path}")

        subject = f"{{ cookiecutter.correspondent_name }} #{EDITION_NUMBER} — {content['main_find']['title']}"
        if DRY_RUN:
            logger.info("DRY_RUN=true — skipping delivery")
        {% if cookiecutter.delivery_platform == 'buttondown' -%}
        else:
            success = send_via_buttondown(subject, html)
            if not success:
                raise DeliveryError("Buttondown delivery failed — HTML saved as artifact")
        {% else -%}
        else:
            logger.info("No delivery platform configured — HTML saved locally only")
        {% endif %}

        {% if cookiecutter.social_linkedin == 'yes' -%}
        if SOCIAL_ENABLED:
            try:
                from social.content_adapter import adapt_for_linkedin, save_social_artifacts
                linkedin_data = adapt_for_linkedin(content)
                save_social_artifacts(linkedin_data, EDITION_NUMBER)
                logger.info("Social content ready for posting")
            except Exception as social_err:
                logger.warning(f"Social generation failed (non-blocking): {social_err}")
        {% endif %}

        total_time = f"{time.time() - start_time:.1f}s"
        logger.info(f"PIPELINE COMPLETE — Runtime: {total_time}")
        logger.info(f"  Main find: {content['main_find']['title']}")
        logger.info(f"  Quick finds: {len(content.get('quick_finds', []))}")

    except (FetchError, CurationError) as e:
        logger.error(f"{type(e).__name__}: {e}")
        try:
            send_fallback(str(e))
        except Exception as fallback_err:
            logger.error(f"Fallback also failed: {fallback_err}")
        sys.exit(1)

    except DeliveryError as e:
        logger.warning(f"DeliveryError: {e}")

    except Exception as e:
        logger.error(f"PIPELINE FAILED (unexpected): {e}", exc_info=True)
        try:
            send_fallback(str(e))
        except Exception as fallback_err:
            logger.error(f"Fallback also failed: {fallback_err}")
        sys.exit(1)


if __name__ == "__main__":
    run_pipeline()
