"""
Lobsters RSS Source — deep tech discussions com curadoria humana (zero auth).
Valor: alt-HN com invite-only community, menos noise, mais dev-centric.
"""
from __future__ import annotations

import calendar
import time
import logging
import feedparser

from sources.base import BaseSource, SourceItem, SourceRegistry

logger = logging.getLogger("daily-scout")

LOBSTERS_RSS_URL = "https://lobste.rs/rss"


@SourceRegistry.register
class LobstersSource(BaseSource):
    source_id = "lobsters"
    source_name = "Lobsters"

    def __init__(self, config: dict | None = None):
        super().__init__(config)
        self.limit = self.config.get("limit", 25)
        self.rss_url = self.config.get("rss_url", LOBSTERS_RSS_URL)

    def fetch(self) -> list[SourceItem]:
        items = []

        feed = feedparser.parse(self.rss_url)
        if feed.bozo and not feed.entries:
            raise RuntimeError(f"Lobsters RSS parse failed: {feed.bozo_exception}")

        for entry in feed.entries[:self.limit]:
            ts = 0.0
            if entry.get("published_parsed"):
                ts = calendar.timegm(entry["published_parsed"])

            # Lobsters tem tags nos entries
            tags = [tag.get("term", "") for tag in entry.get("tags", [])]

            # Lobsters comments URL é diferente da URL do artigo
            comments_url = entry.get("comments", "")

            items.append(SourceItem(
                title=entry.get("title", ""),
                url=entry.get("link", ""),
                source_id=self.source_id,
                source_label="Lobsters",
                timestamp=ts,
                raw_score=0,  # RSS não tem score
                num_comments=0,
                category=_categorize_lobsters(tags, entry.get("title", "")),
                extra={"tags": tags, "comments_url": comments_url},
            ))

        return items


def _categorize_lobsters(tags: list[str], title: str) -> str:
    """Categoriza post do Lobsters baseado nas tags."""
    text = " ".join(tags).lower() + " " + title.lower()
    if any(w in text for w in ["ai", "ml", "machine-learning", "llm", "neural"]):
        return "ai"
    if any(w in text for w in ["rust", "python", "javascript", "go", "haskell", "programming", "compilers"]):
        return "dev"
    if any(w in text for w in ["linux", "unix", "security", "networking", "devops"]):
        return "infra"
    if any(w in text for w in ["opensource", "open-source"]):
        return "opensource"
    return "tech"
