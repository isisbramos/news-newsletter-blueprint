"""
Reddit RSS Source — busca top posts de subreddits via RSS (zero auth).
"""
from __future__ import annotations

import calendar
import time
import logging
import feedparser

from sources.base import BaseSource, SourceItem, SourceRegistry

logger = logging.getLogger("daily-scout")

DEFAULT_SUBREDDITS = [
    "artificial", "MachineLearning", "ChatGPT", "LocalLLaMA",
    "technology", "programming", "opensource", "singularity",
    "techNews", "ArtificialIntelligence", "compsci",
    "startups", "SideProject",
]


@SourceRegistry.register
class RedditSource(BaseSource):
    source_id = "reddit"
    source_name = "Reddit"

    def __init__(self, config: dict | None = None):
        super().__init__(config)
        self.subreddits = self.config.get("subreddits", DEFAULT_SUBREDDITS)
        self.limit_per_sub = self.config.get("limit_per_sub", 10)
        self.rate_limit_delay = self.config.get("rate_limit_delay", 0.5)

    def fetch(self) -> list[SourceItem]:
        items = []
        for sub in self.subreddits:
            url = f"https://www.reddit.com/r/{sub}/hot.rss?limit={self.limit_per_sub}"
            try:
                feed = feedparser.parse(url)
                if feed.bozo and not feed.entries:
                    logger.debug(f"    r/{sub}: RSS parse error")
                    continue
                for entry in feed.entries:
                    ts = 0.0
                    if entry.get("published_parsed"):
                        ts = calendar.timegm(entry["published_parsed"])

                    items.append(SourceItem(
                        title=entry.get("title", ""),
                        url=entry.get("link", ""),
                        source_id=self.source_id,
                        source_label=f"r/{sub}",
                        timestamp=ts,
                        raw_score=0,  # RSS não retorna score
                        num_comments=0,
                        category=_categorize_subreddit(sub),
                    ))
                logger.debug(f"    r/{sub}: {len(feed.entries)} posts")
            except Exception as e:
                logger.debug(f"    r/{sub}: erro — {e}")
            time.sleep(self.rate_limit_delay)
        return items


def _categorize_subreddit(sub: str) -> str:
    """Mapeia subreddit para categoria editorial."""
    categories = {
        "artificial": "ai",
        "MachineLearning": "ai",
        "ChatGPT": "ai",
        "LocalLLaMA": "ai",
        "ArtificialIntelligence": "ai",
        "technology": "tech",
        "programming": "dev",
        "opensource": "opensource",
        "singularity": "ai",
        "techNews": "tech",
        "compsci": "dev",
        "startups": "startup",
        "SideProject": "startup",
    }
    return categories.get(sub, "tech")
