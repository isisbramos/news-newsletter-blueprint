"""
BaseSource ABC + SourceItem dataclass + SourceRegistry
Arquitetura plugável: cada source implementa fetch() e retorna list[SourceItem].
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from typing import Any

logger = logging.getLogger("daily-scout")


@dataclass
class SourceItem:
    """Item normalizado de qualquer fonte. Contrato comum cross-source."""

    title: str
    url: str
    source_id: str  # e.g., "reddit", "hackernews", "techcrunch"
    source_label: str  # e.g., "r/MachineLearning", "HackerNews", "TechCrunch"
    timestamp: float = 0.0  # Unix timestamp (UTC)
    raw_score: int = 0  # Upvotes, stars, points — raw engagement
    num_comments: int = 0
    category: str = ""  # e.g., "ai", "startup", "opensource"
    extra: dict = field(default_factory=dict)  # Source-specific metadata
    # v5: cross-source signal — quantas sources mencionaram o mesmo tema
    cross_source_count: int = 1
    cross_source_ids: list = field(default_factory=list)  # ["hackernews", "reddit"]

    def to_dict(self) -> dict:
        return asdict(self)


class BaseSource(ABC):
    """Interface comum para todas as fontes do Daily Scout."""

    # Subclasses MUST define these
    source_id: str = ""
    source_name: str = ""

    def __init__(self, config: dict | None = None):
        self.config = config or {}
        self.enabled = self.config.get("enabled", True)

    @abstractmethod
    def fetch(self) -> list[SourceItem]:
        """Busca itens da fonte. Retorna lista normalizada."""
        ...

    def safe_fetch(self) -> list[SourceItem]:
        """Wrapper com graceful degradation — nunca derruba o pipeline."""
        if not self.enabled:
            logger.info(f"  [{self.source_id}] SKIP — disabled in config")
            return []

        try:
            start = time.time()
            items = self.fetch()
            elapsed = time.time() - start
            logger.info(
                f"  [{self.source_id}] OK — {len(items)} items in {elapsed:.1f}s"
            )
            return items
        except Exception as e:
            logger.warning(f"  [{self.source_id}] FAIL — {e}")
            return []


class SourceRegistry:
    """Registry de sources disponíveis. Config-driven: liga/desliga via JSON."""

    # All known source classes (register at import time)
    _source_classes: dict[str, type[BaseSource]] = {}

    @classmethod
    def register(cls, source_class: type[BaseSource]) -> type[BaseSource]:
        """Decorator ou chamada direta pra registrar uma source class."""
        cls._source_classes[source_class.source_id] = source_class
        return source_class

    @classmethod
    def create_sources(cls, config: dict) -> list[BaseSource]:
        """Instancia sources habilitadas baseado no config JSON."""
        sources = []
        sources_config = config.get("sources", {})

        for source_id, source_conf in sources_config.items():
            if not isinstance(source_conf, dict):
                continue  # skip _comment keys
            if not source_conf.get("enabled", True):
                logger.info(f"  [{source_id}] disabled in config")
                continue

            if source_id in cls._source_classes:
                source = cls._source_classes[source_id](source_conf)
                sources.append(source)
            else:
                logger.warning(f"  [{source_id}] unknown source — skipping")

        return sources

    @classmethod
    def available_sources(cls) -> list[str]:
        return list(cls._source_classes.keys())
