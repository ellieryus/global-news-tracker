"""
Application layer – use cases that orchestrate the pipeline stages.
Depends only on domain interfaces; infrastructure is injected.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import List

from src.domain.interfaces import ArticleRepository, NLPEnricher, RawFeedSource
from src.domain.models import Article, PipelineRun

logger = logging.getLogger(__name__)


class IngestRawUseCase:
    """
    Stage 1 – Ingest raw: fetch from all sources, deduplicate, store cleaned articles.
    """

    def __init__(
        self,
        sources: List[RawFeedSource],
        repository: ArticleRepository,
        cleaner: "ArticleCleaner",
    ) -> None:
        self._sources = sources
        self._repo = repository
        self._cleaner = cleaner

    def execute(self) -> PipelineRun:
        run = PipelineRun(
            run_id=str(uuid.uuid4()),
            started_at=datetime.now(timezone.utc),
            stage="ingest_raw",
        )
        for source in self._sources:
            logger.info("Fetching from source: %s", source.source_name)
            try:
                for raw in source.fetch():
                    try:
                        article = self._cleaner.clean(raw)
                        if self._repo.exists(article.content_hash):
                            logger.debug("Duplicate skipped: %s", article.url)
                            continue
                        self._repo.save(article)
                        run.articles_processed += 1
                    except Exception as exc:
                        logger.warning("Failed to clean article %s: %s", raw.url, exc)
                        run.articles_failed += 1
            except Exception as exc:
                logger.error("Source %s failed: %s", source.source_name, exc)
                run.articles_failed += 1

        run.finished_at = datetime.now(timezone.utc)
        logger.info(
            "IngestRaw complete – processed=%d failed=%d",
            run.articles_processed,
            run.articles_failed,
        )
        return run


class EnrichNLPUseCase:
    """
    Stage 2 – NLP enrichment: classify topics, score sentiment, extract entities.
    Processes articles that have not yet been enriched.
    """

    def __init__(self, repository: ArticleRepository, enricher: NLPEnricher) -> None:
        self._repo = repository
        self._enricher = enricher

    def execute(self, batch_size: int = 200) -> PipelineRun:
        run = PipelineRun(
            run_id=str(uuid.uuid4()),
            started_at=datetime.now(timezone.utc),
            stage="enrich_nlp",
        )
        articles = self._repo.get_unenriched(limit=batch_size)
        logger.info("Enriching %d articles", len(articles))
        for article in articles:
            try:
                enriched = self._enricher.enrich(article)
                self._repo.update_enrichment(enriched)
                run.articles_processed += 1
            except Exception as exc:
                logger.warning("Enrichment failed for %s: %s", article.url, exc)
                run.articles_failed += 1

        run.finished_at = datetime.now(timezone.utc)
        logger.info(
            "EnrichNLP complete – processed=%d failed=%d",
            run.articles_processed,
            run.articles_failed,
        )
        return run
