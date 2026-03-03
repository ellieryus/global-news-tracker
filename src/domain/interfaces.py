"""
Domain interfaces (Ports) – abstract contracts that infrastructure must implement.
Business logic depends only on these abstractions, never on concrete adapters.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Iterator, Optional

from .models import Article, NewsCategory, RawArticle


class ArticleRepository(ABC):
    """Port: persistence for cleaned & enriched articles."""

    @abstractmethod
    def save(self, article: Article) -> None: ...

    @abstractmethod
    def exists(self, content_hash: str) -> bool: ...

    @abstractmethod
    def get_all(
        self,
        category: Optional[NewsCategory] = None,
        since: Optional[datetime] = None,
        source: Optional[str] = None,
        limit: int = 500,
    ) -> list[Article]: ...

    @abstractmethod
    def get_unenriched(self, limit: int = 200) -> list[Article]: ...

    @abstractmethod
    def update_enrichment(self, article: Article) -> None: ...

    @abstractmethod
    def count_by_category(self, since: Optional[datetime] = None) -> dict[str, int]: ...

    @abstractmethod
    def distinct_sources(self) -> list[str]: ...


class RawFeedSource(ABC):
    """Port: any source that yields raw articles (RSS, API, etc.)."""

    @abstractmethod
    def fetch(self) -> Iterator[RawArticle]: ...

    @property
    @abstractmethod
    def source_name(self) -> str: ...


class NLPEnricher(ABC):
    """Port: enriches an article with category, sentiment, entities."""

    @abstractmethod
    def enrich(self, article: Article) -> Article: ...
