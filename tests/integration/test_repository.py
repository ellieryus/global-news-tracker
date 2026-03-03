"""
Integration test: DuckDB repository with a temporary database.
"""
from __future__ import annotations

import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.domain.models import Article, NewsCategory, Sentiment
from src.infrastructure.storage.duckdb_repo import DuckDBArticleRepository


def make_article(suffix: str = "1") -> Article:
    return Article(
        content_hash=f"hash_{suffix}",
        url=f"https://example.com/article-{suffix}",
        source_name="TestSource",
        title=f"Test Article {suffix}",
        summary="A test summary",
        published_utc=datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc),
        author="Test Author",
        category=NewsCategory.ECONOMY,
        category_confidence=0.85,
        sentiment=Sentiment.NEUTRAL,
        sentiment_score=0.0,
        entities=["Fed", "Jerome Powell"],
        keywords=["rate", "economy"],
        is_enriched=True,
    )


@pytest.fixture
def repo():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.duckdb"
        yield DuckDBArticleRepository(db_path)


class TestDuckDBRepo:
    def test_save_and_exists(self, repo):
        article = make_article("1")
        repo.save(article)
        assert repo.exists("hash_1")

    def test_not_exists(self, repo):
        assert not repo.exists("nonexistent_hash")

    def test_duplicate_ignored(self, repo):
        a = make_article("dup")
        repo.save(a)
        repo.save(a)  # Should not raise
        articles = repo.get_all()
        assert len([x for x in articles if x.content_hash == "hash_dup"]) == 1

    def test_get_all_returns_saved(self, repo):
        for i in range(5):
            repo.save(make_article(str(i)))
        results = repo.get_all()
        assert len(results) == 5

    def test_get_unenriched(self, repo):
        a = make_article("unenriched")
        a.is_enriched = False
        repo.save(a)
        unenriched = repo.get_unenriched()
        assert any(x.content_hash == "hash_unenriched" for x in unenriched)

    def test_update_enrichment(self, repo):
        a = make_article("upd")
        a.is_enriched = False
        repo.save(a)

        a.is_enriched = True
        a.category = NewsCategory.TECH_AI
        a.sentiment = Sentiment.POSITIVE
        repo.update_enrichment(a)

        results = repo.get_all()
        updated = next(x for x in results if x.content_hash == "hash_upd")
        assert updated.is_enriched
        assert updated.category == NewsCategory.TECH_AI

    def test_count_by_category(self, repo):
        for i in range(3):
            repo.save(make_article(str(i)))
        counts = repo.count_by_category()
        assert "Global Economy & Financial Stability" in counts
        assert counts["Global Economy & Financial Stability"] == 3

    def test_distinct_sources(self, repo):
        repo.save(make_article("a"))
        sources = repo.distinct_sources()
        assert "TestSource" in sources
