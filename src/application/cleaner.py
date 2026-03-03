"""
Application service: cleans and normalises a RawArticle into an Article.
All timezone handling, field defaults, and text scrubbing live here.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Optional

import pytz
from dateutil import parser as dateutil_parser

from src.domain.models import Article, RawArticle

logger = logging.getLogger(__name__)

MONTREAL_TZ = pytz.timezone("America/Montreal")
PLACEHOLDER_AUTHOR = "Unknown"
PLACEHOLDER_SUMMARY = ""
_HTML_RE = re.compile(r"<[^>]+>")


def _strip_html(text: str) -> str:
    return _HTML_RE.sub(" ", text).strip()


def _parse_datetime(raw: Optional[str]) -> datetime:
    """
    Parse a datetime string from various RSS/API formats.
    Falls back to current UTC time if parsing fails.
    """
    if not raw:
        return datetime.now(timezone.utc)
    try:
        return parsedate_to_datetime(raw).astimezone(timezone.utc)
    except Exception:
        pass
    try:
        dt = dateutil_parser.parse(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        logger.debug("Could not parse datetime: %r – using now()", raw)
        return datetime.now(timezone.utc)


class ArticleCleaner:
    """
    Transforms a RawArticle into a clean Article.

    Responsibilities:
    - Normalise datetime to UTC
    - Strip HTML from title/summary
    - Fill in missing fields with safe defaults
    - Truncate excessively long summaries
    """

    MAX_SUMMARY_CHARS = 1000

    def clean(self, raw: RawArticle) -> Article:
        """
        Clean and normalise a raw article.

        Args:
            raw: The raw article as ingested from a feed source.

        Returns:
            A normalised Article ready for enrichment.

        Raises:
            ValueError: If the URL is empty.
        """
        if not raw.url:
            raise ValueError("Article URL must not be empty")

        title = _strip_html(raw.title or "").strip() or "No title"
        summary = _strip_html(raw.summary or "").strip()
        summary = summary[: self.MAX_SUMMARY_CHARS]
        published_utc = _parse_datetime(raw.published_raw)
        author = (raw.author or PLACEHOLDER_AUTHOR).strip() or PLACEHOLDER_AUTHOR

        return Article(
            content_hash=raw.content_hash,
            url=raw.url,
            source_name=raw.source_name,
            title=title,
            summary=summary,
            published_utc=published_utc,
            author=author,
            raw_tags=raw.tags,
        )
