"""
Daily Scout — Social Content Adapter
Uses Gemini to adapt curated newsletter content for each social platform.
Currently supports: LinkedIn (text post).
Future: Instagram (carousel cards), Twitter/X.
"""

import json
import logging
import os
import time

logger = logging.getLogger("daily-scout.social-adapter")

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# ── LinkedIn Adaptation Prompt ───────────────────────────────────────

LINKEDIN_PROMPT = """Você é a AYA — correspondente de campo do Daily Scout, adaptando o conteúdo do dia para LinkedIn.

CONTEXTO: Você já escreveu a newsletter do dia com os achados abaixo. Agora precisa criar uma versão para LinkedIn que seja native ao formato da plataforma.

TOM LINKEDIN da AYA:
- Profissional mas não corporativo — a AYA é direta, tem ponto de vista, não é genérica
- Primeira pessoa, como se estivesse compartilhando um insight pessoal da cobertura do dia
- Sem buzzwords vazios (nada de "disruptivo", "game-changer", "revolucionário" sem substância)
- Pode usar termos tech em inglês naturalmente (LLM, open source, funding, etc.)
- Hook forte na PRIMEIRA LINHA — no LinkedIn, só as 2-3 primeiras linhas aparecem antes do "ver mais"
- Use line breaks estratégicos pra readability (LinkedIn renderiza bem posts espaçados)

ESTRUTURA DO POST:
1. HOOK (1 linha) — a frase que faz a pessoa clicar "ver mais". Pode ser provocativa, surpreendente, ou um dado concreto.
2. CONTEXTO (2-3 linhas) — o que a AYA encontrou em campo hoje, brevemente.
3. INSIGHTS (3-5 bullet points curtos) — os achados do dia, cada um com 1 linha de contexto. Use emoji bullets (🔍 ou → ou •).
4. TAKE da AYA (1-2 linhas) — opinião ou observação da correspondente sobre o padrão do dia.
5. CTA (1 linha) — convite pra newsletter. Ex: "Edição completa no Daily Scout — link nos comentários." ou "Newsletter completa com todos os links na bio."
6. HASHTAGS (3-5) — relevantes ao conteúdo, mix de broad (#AI #Tech) e specific (#OpenSource #LLMs)

REGRAS:
- Máximo 2500 caracteres (sweet spot do LinkedIn pra engagement)
- NÃO use markdown formatting (LinkedIn não renderiza bold/italic do markdown)
- Use CAPS sparingly pra ênfase, ou nada
- Emojis: use com parcimônia, max 5-6 no post todo. Prefira →, •, 🔍, 📡, ⚡ sobre emojis genéricos
- O post precisa funcionar standalone — quem não conhece o Daily Scout precisa entender o valor
- Mencione "Daily Scout" naturalmente, não como ad
- A AYA fala em PT-BR com termos tech em EN, igual na newsletter

CONTEÚDO CURADO DO DIA (da newsletter):
{content_json}

Retorne APENAS um JSON válido (sem markdown, sem ```):
{{
  "linkedin_post": "O texto completo do post LinkedIn, com line breaks como \\n",
  "hook_line": "A primeira linha isolada (pra validação)",
  "char_count": 1234,
  "hashtags": ["#AI", "#Tech", "#DailyScout"],
  "cta_type": "newsletter_link"
}}
"""


def adapt_for_linkedin(curated_content: dict, max_retries: int = 3) -> dict | None:
    """
    Takes the curated newsletter content and generates a LinkedIn-optimized post.

    Args:
        curated_content: The dict from Gemini curation (main_find, quick_finds, etc.)
        max_retries: Number of retry attempts for Gemini

    Returns:
        dict with linkedin_post, hook_line, char_count, hashtags, cta_type
        or None if adaptation fails
    """
    from google import genai

    if not GEMINI_API_KEY:
        logger.error("GEMINI_API_KEY not configured — cannot adapt content")
        return None

    client = genai.Client(api_key=GEMINI_API_KEY)

    # Prepare content summary for the prompt
    content_summary = {
        "correspondent_intro": curated_content.get("correspondent_intro", ""),
        "main_find": curated_content.get("main_find", {}),
        "quick_finds": curated_content.get("quick_finds", []),
        "meta": curated_content.get("meta", {}),
    }

    prompt = LINKEDIN_PROMPT.format(
        content_json=json.dumps(content_summary, ensure_ascii=False, indent=2)
    )

    for attempt in range(max_retries):
        try:
            logger.info(f"LinkedIn adaptation attempt {attempt + 1}/{max_retries}...")
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config={
                    "response_mime_type": "application/json",
                    "temperature": 0.5,  # slightly more creative than curation
                    "max_output_tokens": 4096,
                },
            )

            text = response.text.strip()
            logger.info(f"Gemini returned {len(text)} chars for LinkedIn adaptation")

            # Try to parse (reuse try_fix_json from pipeline)
            try:
                result = json.loads(text)
            except json.JSONDecodeError:
                # Simple fix: remove markdown fences if present
                clean = text
                if clean.startswith("```"):
                    clean = clean.split("\n", 1)[-1]
                if clean.endswith("```"):
                    clean = clean.rsplit("```", 1)[0]
                result = json.loads(clean.strip())

            # Validate
            if "linkedin_post" not in result:
                raise ValueError("Missing 'linkedin_post' in response")

            post_text = result["linkedin_post"]
            if len(post_text) < 50:
                raise ValueError(f"Post too short: {len(post_text)} chars")

            # Update char count
            result["char_count"] = len(post_text)

            logger.info(f"LinkedIn post adapted: {result['char_count']} chars")
            logger.info(f"Hook: {result.get('hook_line', 'N/A')[:100]}")
            return result

        except json.JSONDecodeError as e:
            logger.warning(f"Attempt {attempt + 1}: invalid JSON — {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
        except Exception as e:
            logger.warning(f"Attempt {attempt + 1}: error — {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)

    logger.error(f"LinkedIn adaptation failed after {max_retries} attempts")
    return None


def save_social_artifacts(linkedin_data: dict | None, edition_number: str,
                          output_dir: str = "output") -> str | None:
    """
    Save social content as JSON artifacts for the delayed posting workflow.

    Args:
        linkedin_data: The adapted LinkedIn content dict
        edition_number: The edition number string (e.g., "003")
        output_dir: Directory to save artifacts

    Returns:
        Path to the saved artifact file, or None if nothing to save
    """
    if not linkedin_data:
        logger.warning("No social content to save")
        return None

    import os
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    artifact_dir = os.path.join(base_dir, output_dir, "social")
    os.makedirs(artifact_dir, exist_ok=True)

    artifact = {
        "edition": edition_number,
        "generated_at": _now_brt_iso(),
        "platforms": {},
    }

    if linkedin_data:
        artifact["platforms"]["linkedin"] = {
            "status": "pending",  # pending → posted | failed | skipped
            "content": linkedin_data,
        }

    artifact_path = os.path.join(artifact_dir, f"social_{edition_number}.json")
    with open(artifact_path, "w", encoding="utf-8") as f:
        json.dump(artifact, f, ensure_ascii=False, indent=2)

    logger.info(f"Social artifact saved: {artifact_path}")
    return artifact_path


def load_social_artifact(edition_number: str, output_dir: str = "output") -> dict | None:
    """Load a previously saved social artifact for the posting step."""
    import os
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    artifact_path = os.path.join(base_dir, output_dir, "social", f"social_{edition_number}.json")

    if not os.path.exists(artifact_path):
        logger.error(f"Social artifact not found: {artifact_path}")
        return None

    with open(artifact_path, "r", encoding="utf-8") as f:
        return json.load(f)


def update_social_artifact(edition_number: str, platform: str,
                           status: str, post_id: str | None = None,
                           error: str | None = None,
                           output_dir: str = "output") -> None:
    """Update the status of a platform in the social artifact after posting."""
    artifact = load_social_artifact(edition_number, output_dir)
    if not artifact:
        return

    if platform in artifact.get("platforms", {}):
        artifact["platforms"][platform]["status"] = status
        if post_id:
            artifact["platforms"][platform]["post_id"] = post_id
        if error:
            artifact["platforms"][platform]["error"] = error
        artifact["platforms"][platform]["posted_at"] = _now_brt_iso()

    import os
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    artifact_path = os.path.join(base_dir, output_dir, "social", f"social_{edition_number}.json")
    with open(artifact_path, "w", encoding="utf-8") as f:
        json.dump(artifact, f, ensure_ascii=False, indent=2)

    logger.info(f"Social artifact updated: {platform}={status}")


def _now_brt_iso() -> str:
    """Return current BRT timestamp as ISO string."""
    from datetime import datetime, timezone, timedelta
    brt = timezone(timedelta(hours=-3))
    return datetime.now(brt).isoformat()
