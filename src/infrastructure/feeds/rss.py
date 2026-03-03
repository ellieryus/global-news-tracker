"""
Infrastructure: RSS feed adapter using feedparser.
Implements the RawFeedSource port.
"""
from __future__ import annotations

import logging
import time
from typing import Iterator

import feedparser
import requests

from src.domain.interfaces import RawFeedSource
from src.domain.models import RawArticle

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 15
_RATE_LIMIT_DELAY = 1.0  # seconds between requests


class RSSFeedSource(RawFeedSource):
    """
    Fetches articles from a single RSS feed URL.

    Args:
        url: The RSS feed URL.
        name: Human-readable source name.
        timeout: HTTP request timeout in seconds.
    """

    def __init__(self, url: str, name: str, timeout: int = _DEFAULT_TIMEOUT) -> None:
        self._url = url
        self._name = name
        self._timeout = timeout

    @property
    def source_name(self) -> str:
        return self._name

    def fetch(self) -> Iterator[RawArticle]:
        """Fetch and yield RawArticle objects from the RSS feed."""
        logger.info("Fetching RSS feed: %s (%s)", self._name, self._url)
        try:
            response = requests.get(
                self._url,
                timeout=self._timeout,
                headers={"User-Agent": "NewsIntelligenceDashboard/1.0"},
            )
            response.raise_for_status()
            feed = feedparser.parse(response.content)
        except requests.RequestException as exc:
            logger.error("HTTP error fetching %s: %s", self._url, exc)
            return
        except Exception as exc:
            logger.error("Unexpected error fetching %s: %s", self._url, exc)
            return

        entries = feed.get("entries", [])
        logger.info("Parsed %d entries from %s", len(entries), self._name)

        for entry in entries:
            url = entry.get("link", "")
            if not url:
                continue
            tags = [t.get("term", "") for t in entry.get("tags", []) if t.get("term")]
            yield RawArticle(
                url=url,
                source_name=self._name,
                title=entry.get("title"),
                summary=entry.get("summary") or entry.get("description"),
                published_raw=entry.get("published") or entry.get("updated"),
                author=entry.get("author"),
                tags=tags,
                guid=entry.get("id") or url,
            )
        time.sleep(_RATE_LIMIT_DELAY)


class NewsAPISource(RawFeedSource):
    """
    Optional adapter for NewsAPI.org.
    Requires NEWSAPI_KEY env var / config to be set.

    Args:
        api_key: NewsAPI.org API key.
        query: Search query string.
        page_size: Number of articles per request (max 100).
    """

    BASE_URL = "https://newsapi.org/v2/top-headlines"

    def __init__(self, api_key: str, query: str = "", page_size: int = 50) -> None:
        self._api_key = api_key
        self._query = query
        self._page_size = page_size

    @property
    def source_name(self) -> str:
        return "NewsAPI"

    def fetch(self) -> Iterator[RawArticle]:
        """Fetch top headlines from NewsAPI."""
        params: dict = {
            "apiKey": self._api_key,
            "pageSize": self._page_size,
            "language": "en",
        }
        if self._query:
            params["q"] = self._query

        try:
            resp = requests.get(self.BASE_URL, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.error("NewsAPI fetch failed: %s", exc)
            return

        for item in data.get("articles", []):
            url = item.get("url", "")
            if not url:
                continue
            yield RawArticle(
                url=url,
                source_name=item.get("source", {}).get("name", "NewsAPI"),
                title=item.get("title"),
                summary=item.get("description"),
                published_raw=item.get("publishedAt"),
                author=item.get("author"),
            )
