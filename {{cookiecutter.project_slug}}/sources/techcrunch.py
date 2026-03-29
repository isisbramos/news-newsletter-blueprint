"""
TechCrunch RSS Source — busca posts via RSS feed público (zero auth).
Valor: funding rounds, launches, industry moves — signal que HN/Reddit não cobrem bem.
"""
from __future__ import annotations

import calendar
import time
import logging
import feedparser

from sources.base import BaseSource, SourceItem, SourceRegistry

logger = logging.getLogger("daily-scout")

TECHCRUNCH_FEEDS = {
    "main": "https://techcrunch.com/feed/",
}


@SourceRegistry.register
class TechCrunchSource(BaseSource):
    source_id = "techcrunch"
    source_name = "TechCrunch"

    def __init__(self, config: dict | None = None):
        super().__init__(config)
        self.limit = self.config.get("limit", 20)
        self.feeds = self.config.get("feeds", TECHCRUNCH_FEEDS)

    def fetch(self) -> list[SourceItem]:
        items = []

        for feed_name, feed_url in self.feeds.items():
            try:
                feed = feedparser.parse(feed_url)
                if feed.bozo and not feed.entries:
                    logger.debug(f"    TechCrunch/{feed_name}: RSS parse error")
                    continue

                for entry in feed.entries[:self.limit]:
                    ts = 0.0
                    if entry.get("published_parsed"):
                        ts = calendar.timegm(entry["published_parsed"])

                    # TechCrunch tem tags/categories nos entries
                    categories = [
                        tag.get("term", "")
                        for tag in entry.get("tags", [])
                    ]

                    items.append(SourceItem(
                        title=entry.get("title", ""),
                        url=entry.get("link", ""),
                        source_id=self.source_id,
                        source_label="TechCrunch",
                        timestamp=ts,
                        raw_score=0,  # RSS não tem engagement score
                        num_comments=0,
                        category=_categorize_tc(categories, entry.get("title", "")),
                        extra={"tc_categories": categories},
                    ))
                logger.debug(
                    f"    TechCrunch/{feed_name}: {min(len(feed.entries), self.limit)} posts"
                )
            except Exception as e:
                logger.debug(f"    TechCrunch/{feed_name}: erro — {e}")

        return items


def _categorize_tc(categories: list[str], title: str) -> str:
    """Categoriza post do TechCrunch baseado nas tags e título."""
    text = " ".join(categories).lower() + " " + title.lower()
    if any(w in text for w in ["ai", "artificial intelligence", "machine learning", "llm", "openai", "anthropic"]):
        return "ai"
    if any(w in text for w in ["funding", "series", "raised", "valuation", "ipo", "acquisition"]):
        return "startup"
    if any(w in text for w in ["open source", "github"]):
        return "opensource"
    if any(w in text for w in ["developer", "api", "sdk", "programming"]):
        return "dev"
    return "tech"
