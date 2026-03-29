"""
HackerNews API Source — busca top stories via Firebase API (zero auth).
"""
from __future__ import annotations

import logging
import requests

from sources.base import BaseSource, SourceItem, SourceRegistry

logger = logging.getLogger("daily-scout")

HN_BASE_URL = "https://hacker-news.firebaseio.com/v0"


@SourceRegistry.register
class HackerNewsSource(BaseSource):
    source_id = "hackernews"
    source_name = "HackerNews"

    def __init__(self, config: dict | None = None):
        super().__init__(config)
        self.limit = self.config.get("limit", 30)
        self.timeout = self.config.get("timeout", 15)

    def fetch(self) -> list[SourceItem]:
        items = []

        resp = requests.get(f"{HN_BASE_URL}/topstories.json", timeout=self.timeout)
        resp.raise_for_status()
        story_ids = resp.json()[:self.limit]

        for sid in story_ids:
            try:
                sr = requests.get(
                    f"{HN_BASE_URL}/item/{sid}.json", timeout=self.timeout
                )
                if sr.status_code != 200:
                    continue
                story = sr.json()
                if not story or not story.get("title"):
                    continue

                items.append(SourceItem(
                    title=story.get("title", ""),
                    url=story.get("url", f"https://news.ycombinator.com/item?id={sid}"),
                    source_id=self.source_id,
                    source_label="HackerNews",
                    timestamp=float(story.get("time", 0)),
                    raw_score=story.get("score", 0),
                    num_comments=story.get("descendants", 0),
                    category=_guess_hn_category(story),
                ))
            except Exception:
                continue

        return items


def _guess_hn_category(story: dict) -> str:
    """Heurística simples pra categorizar HN stories."""
    title = (story.get("title", "") + " " + story.get("url", "")).lower()
    if any(w in title for w in ["ai", "llm", "gpt", "claude", "gemini", "openai", "anthropic", "ml", "neural"]):
        return "ai"
    if any(w in title for w in ["startup", "funding", "ycombinator", "series-", "raise"]):
        return "startup"
    if any(w in title for w in ["github", "open source", "opensource", "repo"]):
        return "opensource"
    if any(w in title for w in ["rust", "python", "javascript", "golang", "compiler"]):
        return "dev"
    return "tech"
