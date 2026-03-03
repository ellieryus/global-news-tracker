"""
Dependency injection container.
Wires all infrastructure adapters to application use-cases.
Single place to change implementations without touching business logic.
"""
from __future__ import annotations

from pathlib import Path

from src.application.cleaner import ArticleCleaner
from src.application.config import Settings
from src.application.trainer import ModelTrainer
from src.application.use_cases import EnrichNLPUseCase, IngestRawUseCase
from src.domain.interfaces import ArticleRepository
from src.infrastructure.feeds.rss import NewsAPISource, RSSFeedSource
from src.infrastructure.nlp.enricher import CompositeNLPEnricher, MLClassifier
from src.infrastructure.storage.duckdb_repo import DuckDBArticleRepository


class Container:
    """
    Builds and exposes all application services.

    Usage::

        container = Container.from_settings(settings)
        container.ingest_use_case.execute()
        container.enrich_use_case.execute()
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        settings.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Infrastructure
        self.repository: ArticleRepository = DuckDBArticleRepository(settings.db_path)
        self._ml_classifier = MLClassifier(settings.model_path)
        self._enricher = CompositeNLPEnricher(ml_classifier=self._ml_classifier)
        self._cleaner = ArticleCleaner()

        # Feed sources
        sources = [
            RSSFeedSource(url=f.url, name=f.name)
            for f in settings.feeds
            if f.enabled
        ]
        if settings.newsapi_key:
            sources.append(NewsAPISource(api_key=settings.newsapi_key))

        # Use cases
        self.ingest_use_case = IngestRawUseCase(
            sources=sources,
            repository=self.repository,
            cleaner=self._cleaner,
        )
        self.enrich_use_case = EnrichNLPUseCase(
            repository=self.repository,
            enricher=self._enricher,
        )
        self.trainer = ModelTrainer(
            repository=self.repository,
            model_path=settings.model_path,
        )

    @classmethod
    def from_settings(cls, settings: Settings) -> "Container":
        return cls(settings)
