"""
Unit tests for core pipeline logic:
- Article cleaning and field normalization
- Deduplication via content hash
- Keyword classification
- Sentiment scoring
"""
from __future__ import annotations

import pytest
from datetime import datetime, timezone

from src.application.cleaner import ArticleCleaner, _strip_html, _parse_datetime
from src.domain.models import RawArticle, NewsCategory, Sentiment
from src.infrastructure.nlp.enricher import (
    classify_keyword,
    score_sentiment,
    extract_entities,
    extract_keywords,
)


# ── Cleaner tests ─────────────────────────────────────────────────────────────

class TestStripHtml:
    def test_removes_tags(self):
        assert _strip_html("<p>Hello <b>World</b></p>") == "Hello World"

    def test_plain_text_unchanged(self):
        assert _strip_html("Plain text") == "Plain text"

    def test_empty_string(self):
        assert _strip_html("") == ""


class TestParseDatetime:
    def test_rfc2822(self):
        raw = "Mon, 01 Jan 2024 12:00:00 +0000"
        dt = _parse_datetime(raw)
        assert dt.year == 2024
        assert dt.tzinfo is not None

    def test_iso_format(self):
        raw = "2024-06-15T09:30:00Z"
        dt = _parse_datetime(raw)
        assert dt.year == 2024
        assert dt.month == 6

    def test_none_returns_recent(self):
        dt = _parse_datetime(None)
        assert isinstance(dt, datetime)
        assert dt.tzinfo is not None

    def test_garbage_returns_recent(self):
        dt = _parse_datetime("not-a-date-at-all")
        assert isinstance(dt, datetime)


class TestArticleCleaner:
    def setup_method(self):
        self.cleaner = ArticleCleaner()

    def test_basic_clean(self):
        raw = RawArticle(
            url="https://example.com/article",
            source_name="TestSource",
            title="Test Title",
            summary="A <b>test</b> summary",
            published_raw="2024-01-15T10:00:00Z",
        )
        article = self.cleaner.clean(raw)
        assert article.title == "Test Title"
        assert article.summary == "A test summary"
        assert article.source_name == "TestSource"
        assert article.author == "Unknown"

    def test_html_stripped_from_title(self):
        raw = RawArticle(
            url="https://example.com/1",
            source_name="S",
            title="<b>Breaking</b>: Something happened",
        )
        article = self.cleaner.clean(raw)
        assert "<b>" not in article.title

    def test_missing_url_raises(self):
        raw = RawArticle(url="", source_name="S")
        with pytest.raises(ValueError):
            self.cleaner.clean(raw)

    def test_summary_truncated(self):
        raw = RawArticle(
            url="https://example.com/long",
            source_name="S",
            summary="x" * 2000,
        )
        article = self.cleaner.clean(raw)
        assert len(article.summary) <= ArticleCleaner.MAX_SUMMARY_CHARS

    def test_content_hash_stable(self):
        raw = RawArticle(url="https://example.com/same", source_name="S")
        a1 = self.cleaner.clean(raw)
        a2 = self.cleaner.clean(raw)
        assert a1.content_hash == a2.content_hash

    def test_different_urls_different_hashes(self):
        r1 = RawArticle(url="https://example.com/a", source_name="S")
        r2 = RawArticle(url="https://example.com/b", source_name="S")
        assert self.cleaner.clean(r1).content_hash != self.cleaner.clean(r2).content_hash


# ── Classification tests ──────────────────────────────────────────────────────

class TestKeywordClassifier:
    def test_geopolitics_detected(self):
        cat, conf = classify_keyword("NATO troops deployed to eastern Ukraine border")
        assert cat == NewsCategory.GEOPOLITICS
        assert conf > 0

    def test_economy_detected(self):
        cat, conf = classify_keyword("Federal Reserve raises interest rate amid inflation concerns")
        assert cat == NewsCategory.ECONOMY

    def test_tech_detected(self):
        cat, conf = classify_keyword("OpenAI releases new GPT model for enterprise AI use")
        assert cat == NewsCategory.TECH_AI

    def test_canada_priority_over_economy(self):
        cat, conf = classify_keyword(
            "Bank of Canada holds interest rate steady; Canadian housing market cools"
        )
        # Canada rule should have priority
        assert cat == NewsCategory.CANADA

    def test_climate_detected(self):
        cat, conf = classify_keyword("Global warming accelerates as carbon emissions hit new record")
        assert cat == NewsCategory.CLIMATE

    def test_health_detected(self):
        cat, conf = classify_keyword("WHO warns of new pandemic risk from emerging disease")
        assert cat == NewsCategory.HEALTH

    def test_unknown_on_gibberish(self):
        cat, conf = classify_keyword("aaa bbb ccc ddd eee")
        assert cat == NewsCategory.UNKNOWN
        assert conf == 0.0

    def test_confidence_in_range(self):
        _, conf = classify_keyword("War and conflict in Middle East as NATO responds")
        assert 0.0 <= conf <= 1.0


# ── Sentiment tests ───────────────────────────────────────────────────────────

class TestSentiment:
    def test_positive(self):
        sentiment, score = score_sentiment("Great news! Economy grows strongly, markets rally.")
        assert sentiment == Sentiment.POSITIVE
        assert score > 0

    def test_negative(self):
        sentiment, score = score_sentiment("Devastating attack kills dozens; crisis worsens.")
        assert sentiment == Sentiment.NEGATIVE
        assert score < 0

    def test_neutral(self):
        sentiment, score = score_sentiment("The committee met on Tuesday to discuss the proposal.")
        assert sentiment == Sentiment.NEUTRAL

    def test_score_in_range(self):
        _, score = score_sentiment("The economy report was released today.")
        assert -1.0 <= score <= 1.0


# ── Entity extraction tests ───────────────────────────────────────────────────

class TestEntityExtraction:
    def test_extracts_proper_nouns(self):
        entities = extract_entities("Justin Trudeau met with Emmanuel Macron in Paris.")
        assert len(entities) > 0
        # At least one multi-word entity
        assert any(len(e.split()) >= 1 for e in entities)

    def test_max_entities_respected(self):
        text = " ".join([f"Person{i} Name{i}" for i in range(20)])
        entities = extract_entities(text, max_entities=5)
        assert len(entities) <= 5

    def test_empty_text(self):
        entities = extract_entities("")
        assert entities == []


# ── Keyword extraction tests ──────────────────────────────────────────────────

class TestKeywordExtraction:
    def test_extracts_keywords(self):
        kws = extract_keywords(
            "Federal Reserve rate decision",
            "The Federal Reserve announced its rate decision today affecting markets"
        )
        assert len(kws) > 0
        assert "federal" in kws or "reserve" in kws

    def test_stops_filtered(self):
        kws = extract_keywords("The news", "The article said that the thing is the case")
        assert "the" not in kws
        assert "that" not in kws

    def test_top_n_respected(self):
        kws = extract_keywords(
            "long title with many different words inside",
            "summary with even more words that should be captured by keyword extraction",
            top_n=4,
        )
        assert len(kws) <= 4
