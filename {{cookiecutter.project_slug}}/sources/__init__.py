"""
Daily Scout — Source Abstraction Layer
Cada fonte é um módulo independente com interface comum: fetch() → list[SourceItem]
"""

from sources.base import BaseSource, SourceItem, SourceRegistry
from sources.reddit import RedditSource
from sources.hackernews import HackerNewsSource
from sources.techcrunch import TechCrunchSource
from sources.lobsters import LobstersSource

__all__ = [
    "BaseSource",
    "SourceItem",
    "SourceRegistry",
    "RedditSource",
    "HackerNewsSource",
    "TechCrunchSource",
    "LobstersSource",
]
