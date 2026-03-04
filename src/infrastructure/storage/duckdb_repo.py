"""
Infrastructure: DuckDB-backed ArticleRepository.

Why DuckDB over SQLite?
- Columnar storage excels at analytical queries (GROUP BY, date range scans)
  that power dashboard aggregations.
- First-class Python API; no external server required.
- Significantly faster for the "count by category / trend over time" queries
  the dashboard runs on every render.
"""
from __future__ import annotations

import logging
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator, Optional

import duckdb

from src.domain.interfaces import ArticleRepository
from src.domain.models import Article, NewsCategory, Sentiment

logger = logging.getLogger(__name__)

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS articles (
    content_hash    TEXT PRIMARY KEY,
    url             TEXT NOT NULL,
    source_name     TEXT NOT NULL,
    title           TEXT NOT NULL,
    summary         TEXT,
    published_utc   TIMESTAMP WITH TIME ZONE NOT NULL,
    author          TEXT,
    raw_tags        TEXT,          -- JSON array stored as text
    category        TEXT DEFAULT 'Unknown',
    category_conf   DOUBLE DEFAULT 0.0,
    sentiment       TEXT DEFAULT 'neutral',
    sentiment_score DOUBLE DEFAULT 0.0,
    entities        TEXT,          -- JSON array stored as text
    keywords        TEXT,          -- JSON array stored as text
    is_enriched     BOOLEAN DEFAULT FALSE,
    inserted_at     TIMESTAMP WITH TIME ZONE DEFAULT now()
);
"""


def _row_to_article(row: tuple) -> Article:
    import json

    (
        content_hash, url, source_name, title, summary,
        published_utc, author, raw_tags_json, category,
        category_conf, sentiment, sentiment_score,
        entities_json, keywords_json, is_enriched, _inserted_at,
    ) = row

    return Article(
        content_hash=content_hash,
        url=url,
        source_name=source_name,
        title=title,
        summary=summary or "",
        published_utc=published_utc if published_utc.tzinfo else
            published_utc.replace(tzinfo=timezone.utc),
        author=author or "Unknown",
        raw_tags=json.loads(raw_tags_json or "[]"),
        category=NewsCategory(category) if category else NewsCategory.UNKNOWN,
        category_confidence=float(category_conf or 0.0),
        sentiment=Sentiment(sentiment) if sentiment else Sentiment.NEUTRAL,
        sentiment_score=float(sentiment_score or 0.0),
        entities=json.loads(entities_json or "[]"),
        keywords=json.loads(keywords_json or "[]"),
        is_enriched=bool(is_enriched),
    )


class DuckDBArticleRepository(ArticleRepository):
    """
    Thread-safe DuckDB-backed repository.
    Uses a single file database; thread safety via per-operation connections.

    Args:
        db_path: Path to the DuckDB database file.
    """

    def __init__(self, db_path: Path) -> None:
        self._db_path = str(db_path)
        self._init_schema()

    @contextmanager
    def _conn(self) -> Generator[duckdb.DuckDBPyConnection, None, None]:
        conn = duckdb.connect(self._db_path)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._conn() as conn:
            conn.execute(_CREATE_TABLE)
        logger.info("DuckDB schema initialised at %s", self._db_path)

    def save(self, article: Article) -> None:
        import json

        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO articles (
                    content_hash, url, source_name, title, summary,
                    published_utc, author, raw_tags, category, category_conf,
                    sentiment, sentiment_score, entities, keywords, is_enriched
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT (content_hash) DO NOTHING
                """,
                [
                    article.content_hash,
                    article.url,
                    article.source_name,
                    article.title,
                    article.summary,
                    article.published_utc,
                    article.author,
                    json.dumps(article.raw_tags),
                    article.category.value,
                    article.category_confidence,
                    article.sentiment.value,
                    article.sentiment_score,
                    json.dumps(article.entities),
                    json.dumps(article.keywords),
                    article.is_enriched,
                ],
            )

    def exists(self, content_hash: str) -> bool:
        with self._conn() as conn:
            result = conn.execute(
                "SELECT 1 FROM articles WHERE content_hash = ?", [content_hash]
            ).fetchone()
        return result is not None

    def get_all(
        self,
        category: Optional[NewsCategory] = None,
        since: Optional[datetime] = None,
        source: Optional[str] = None,
        limit: int = 500,
    ) -> list[Article]:
        clauses, params = [], []
        if category:
            clauses.append("category = ?")
            params.append(category.value)
        if since:
            clauses.append("published_utc >= ?")
            params.append(since)
        if source:
            clauses.append("source_name = ?")
            params.append(source)

        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        sql = f"""
            SELECT content_hash, url, source_name, title, summary,
                   published_utc, author, raw_tags, category, category_conf,
                   sentiment, sentiment_score, entities, keywords, is_enriched,
                   inserted_at
            FROM articles {where}
            ORDER BY published_utc DESC
            LIMIT ?
        """
        params.append(limit)
        with self._conn() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [_row_to_article(r) for r in rows]

    def get_unenriched(self, limit: int = 200) -> list[Article]:
        sql = """
            SELECT content_hash, url, source_name, title, summary,
                   published_utc, author, raw_tags, category, category_conf,
                   sentiment, sentiment_score, entities, keywords, is_enriched,
                   inserted_at
            FROM articles
            WHERE is_enriched = FALSE
            ORDER BY published_utc DESC
            LIMIT ?
        """
        with self._conn() as conn:
            rows = conn.execute(sql, [limit]).fetchall()
        return [_row_to_article(r) for r in rows]

    def update_enrichment(self, article: Article) -> None:
        import json

        with self._conn() as conn:
            conn.execute(
                """
                UPDATE articles SET
                    category        = ?,
                    category_conf   = ?,
                    sentiment       = ?,
                    sentiment_score = ?,
                    entities        = ?,
                    keywords        = ?,
                    is_enriched     = TRUE
                WHERE content_hash = ?
                """,
                [
                    article.category.value,
                    article.category_confidence,
                    article.sentiment.value,
                    article.sentiment_score,
                    json.dumps(article.entities),
                    json.dumps(article.keywords),
                    article.content_hash,
                ],
            )

    def count_by_category(self, since: Optional[datetime] = None) -> dict[str, int]:
        clause = "WHERE published_utc >= ?" if since else ""
        params = [since] if since else []
        sql = f"""
            SELECT category, COUNT(*) as n
            FROM articles {clause}
            GROUP BY category
            ORDER BY n DESC
        """
        with self._conn() as conn:
            rows = conn.execute(sql, params).fetchall()
        return {row[0]: row[1] for row in rows}

    def distinct_sources(self) -> list[str]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT DISTINCT source_name FROM articles ORDER BY source_name"
            ).fetchall()
        return [r[0] for r in rows]

    def trend_data(self, days: int = 7) -> list[tuple]:
        """Return (date, category, count) for trend charts."""
        # DuckDB does not support ? placeholder inside INTERVAL — interpolate directly.
        sql = f"""
            SELECT
                CAST(published_utc AS DATE) AS pub_date,
                category,
                COUNT(*) AS n
            FROM articles
            WHERE published_utc >= now() - INTERVAL '{days} days'
            GROUP BY pub_date, category
            ORDER BY pub_date, category
        """
        with self._conn() as conn:
            return conn.execute(sql).fetchall()

    def category_sentiment_summary(self) -> list[tuple]:
        """Return (category, avg_sentiment_score, count) for monitoring page."""
        sql = """
            SELECT category,
                   AVG(sentiment_score) AS avg_score,
                   COUNT(*) AS n
            FROM articles
            WHERE is_enriched = TRUE
            GROUP BY category
            ORDER BY category
        """
        with self._conn() as conn:
            return conn.execute(sql).fetchall()