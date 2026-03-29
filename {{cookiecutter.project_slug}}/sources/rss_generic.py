"""
Generic RSS Source — reusável para qualquer feed RSS.
Usado para AI lab blogs (Anthropic, OpenAI, DeepMind) e fontes geográficas (SCMP, Rest of World).
Config-driven: cada instância é definida no sources_config.json.
"""
from __future__ import annotations

import calendar
import logging
import time

import feedparser

from sources.base import BaseSource, SourceItem, SourceRegistry

logger = logging.getLogger("daily-scout")


# ── AI Lab Blogs ─────────────────────────────────────────────────────

@SourceRegistry.register
class AnthropicBlogSource(BaseSource):
    source_id = "anthropic_blog"
    source_name = "Anthropic Blog"

    def __init__(self, config: dict | None = None):
        super().__init__(config)
        self.limit = self.config.get("limit", 15)
        self.feed_url = self.config.get(
            "rss_url", "https://www.anthropic.com/feed"
        )

    def fetch(self) -> list[SourceItem]:
        return _fetch_rss(
            feed_url=self.feed_url,
            source_id=self.source_id,
            source_label="Anthropic Blog",
            limit=self.limit,
            default_category="ai",
        )


@SourceRegistry.register
class OpenAIBlogSource(BaseSource):
    source_id = "openai_blog"
    source_name = "OpenAI Blog"

    def __init__(self, config: dict | None = None):
        super().__init__(config)
        self.limit = self.config.get("limit", 15)
        self.feed_url = self.config.get(
            "rss_url", "https://openai.com/blog/rss.xml"
        )

    def fetch(self) -> list[SourceItem]:
        return _fetch_rss(
            feed_url=self.feed_url,
            source_id=self.source_id,
            source_label="OpenAI Blog",
            limit=self.limit,
            default_category="ai",
        )


@SourceRegistry.register
class DeepMindBlogSource(BaseSource):
    source_id = "deepmind_blog"
    source_name = "Google DeepMind Blog"

    def __init__(self, config: dict | None = None):
        super().__init__(config)
        self.limit = self.config.get("limit", 15)
        self.feed_url = self.config.get(
            "rss_url", "https://deepmind.google/blog/rss.xml"
        )

    def fetch(self) -> list[SourceItem]:
        return _fetch_rss(
            feed_url=self.feed_url,
            source_id=self.source_id,
            source_label="Google DeepMind Blog",
            limit=self.limit,
            default_category="ai",
        )


# ── Geographic Diversity Sources ─────────────────────────────────────

@SourceRegistry.register
class SCMPTechSource(BaseSource):
    source_id = "scmp_tech"
    source_name = "South China Morning Post — Tech"

    def __init__(self, config: dict | None = None):
        super().__init__(config)
        self.limit = self.config.get("limit", 15)
        self.feed_url = self.config.get(
            "rss_url", "https://www.scmp.com/rss/36/feed"
        )

    def fetch(self) -> list[SourceItem]:
        return _fetch_rss(
            feed_url=self.feed_url,
            source_id=self.source_id,
            source_label="SCMP Tech",
            limit=self.limit,
            default_category="tech",
        )


@SourceRegistry.register
class RestOfWorldSource(BaseSource):
    source_id = "rest_of_world"
    source_name = "Rest of World"

    def __init__(self, config: dict | None = None):
        super().__init__(config)
        self.limit = self.config.get("limit", 15)
        self.feed_url = self.config.get(
            "rss_url", "https://restofworld.org/feed/"
        )

    def fetch(self) -> list[SourceItem]:
        return _fetch_rss(
            feed_url=self.feed_url,
            source_id=self.source_id,
            source_label="Rest of World",
            limit=self.limit,
            default_category="tech",
        )


@SourceRegistry.register
class TechNodeSource(BaseSource):
    source_id = "technode"
    source_name = "TechNode"

    def __init__(self, config: dict | None = None):
        super().__init__(config)
        self.limit = self.config.get("limit", 15)
        self.feed_url = self.config.get(
            "rss_url", "https://technode.com/feed/"
        )

    def fetch(self) -> list[SourceItem]:
        return _fetch_rss(
            feed_url=self.feed_url,
            source_id=self.source_id,
            source_label="TechNode",
            limit=self.limit,
            default_category="tech",
        )


# ── Shared RSS fetch logic ───────────────────────────────────────────

def _fetch_rss(
    feed_url: str,
    source_id: str,
    source_label: str,
    limit: int = 15,
    default_category: str = "tech",
) -> list[SourceItem]:
    """Fetch genérico de RSS feed. Retorna SourceItems normalizados."""
    items = []

    try:
        feed = feedparser.parse(feed_url)
        if feed.bozo and not feed.entries:
            logger.debug(f"    {source_label}: RSS parse error — {feed.bozo_exception}")
            return []

        for entry in feed.entries[:limit]:
            ts = 0.0
            if entry.get("published_parsed"):
                ts = calendar.timegm(entry["published_parsed"])
            elif entry.get("updated_parsed"):
                ts = calendar.timegm(entry["updated_parsed"])

            # Tenta extrair categorias/tags
            categories = [
                tag.get("term", "")
                for tag in entry.get("tags", [])
            ]

            # Categorização básica via keywords no título
            title = entry.get("title", "")
            category = _categorize_by_title(title, categories, default_category)

            items.append(SourceItem(
                title=title,
                url=entry.get("link", ""),
                source_id=source_id,
                source_label=source_label,
                timestamp=ts,
                raw_score=0,  # RSS feeds não têm engagement data
                num_comments=0,
                category=category,
                extra={"rss_categories": categories},
            ))

        logger.debug(f"    {source_label}: {len(items)} posts fetched")

    except Exception as e:
        logger.debug(f"    {source_label}: fetch error — {e}")

    return items


def _categorize_by_title(
    title: str, categories: list[str], default: str
) -> str:
    """Categoriza post baseado no título e tags RSS."""
    text = " ".join(categories).lower() + " " + title.lower()

    if any(w in text for w in [
        "ai", "artificial intelligence", "machine learning", "llm",
        "openai", "anthropic", "deepmind", "gemini", "gpt", "claude",
        "deep learning", "neural", "transformer", "diffusion",
        "chatbot", "copilot", "midjourney", "stable diffusion",
    ]):
        return "ai"
    if any(w in text for w in [
        "funding", "series", "raised", "valuation", "ipo",
        "acquisition", "acquire",
    ]):
        return "startup"
    if any(w in text for w in ["open source", "github", "apache", "license"]):
        return "opensource"
    if any(w in text for w in [
        "regulation", "law", "ban", "policy", "gdpr", "ai act",
        "antitrust", "compliance",
    ]):
        return "regulation"
    if any(w in text for w in [
        "developer", "api", "sdk", "programming", "rust", "python",
    ]):
        return "dev"

    return default
