"""
Domain layer – pure Python dataclasses, no I/O dependencies.
These are the canonical data contracts used across all layers.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class NewsCategory(str, Enum):
    """Six stable dashboard-friendly news categories."""

    GEOPOLITICS = "Geopolitics & Conflict"
    ECONOMY = "Global Economy & Financial Stability"
    TECH_AI = "Tech & AI Power Shifts"
    CLIMATE = "Climate & Energy"
    HEALTH = "Public Health & Demographics"
    CANADA = "Canada-Specific"
    UNKNOWN = "Unknown"


class Sentiment(str, Enum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


@dataclass
class RawArticle:
    """
    Immutable raw article as ingested from an RSS/API source.
    All fields are optional except url and source_name.
    """

    url: str
    source_name: str
    title: Optional[str] = None
    summary: Optional[str] = None
    published_raw: Optional[str] = None
    author: Optional[str] = None
    tags: list[str] = field(default_factory=list)
    guid: Optional[str] = None

    @property
    def content_hash(self) -> str:
        """Stable deduplication key derived from URL."""
        return hashlib.sha256(self.url.encode()).hexdigest()


@dataclass
class Article:
    """
    Cleaned, normalised article ready for enrichment.
    Published datetime is always UTC-aware, then localised to America/Montreal.
    """

    content_hash: str
    url: str
    source_name: str
    title: str
    summary: str
    published_utc: datetime
    author: str
    raw_tags: list[str] = field(default_factory=list)

    # Enrichment fields (filled by NLP pipeline)
    category: NewsCategory = NewsCategory.UNKNOWN
    category_confidence: float = 0.0
    sentiment: Sentiment = Sentiment.NEUTRAL
    sentiment_score: float = 0.0
    entities: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    is_enriched: bool = False


@dataclass
class PipelineRun:
    """Lightweight audit record for each pipeline execution."""

    run_id: str
    started_at: datetime
    stage: str
    articles_processed: int = 0
    articles_failed: int = 0
    finished_at: Optional[datetime] = None
    error: Optional[str] = None
