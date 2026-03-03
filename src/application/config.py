"""
Configuration management.
Loads settings from config/settings.yaml, with env-var overrides.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml


@dataclass
class FeedConfig:
    name: str
    url: str
    enabled: bool = True


@dataclass
class Settings:
    # Paths
    db_path: Path = Path("data/processed/news.duckdb")
    model_path: Path = Path("data/processed/classifier.pkl")
    log_level: str = "INFO"
    log_file: str = "logs/pipeline.log"

    # Pipeline
    ingest_batch_size: int = 200
    enrich_batch_size: int = 200

    # Dashboard
    dashboard_port: int = 8501
    timezone: str = "America/Montreal"
    trend_days: int = 7

    # Optional API key
    newsapi_key: Optional[str] = None

    # Feeds (populated from YAML)
    feeds: list[FeedConfig] = field(default_factory=list)

    @classmethod
    def from_yaml(cls, path: Path = Path("config/settings.yaml")) -> "Settings":
        """Load settings from YAML file with environment variable overrides."""
        with open(path) as fh:
            raw = yaml.safe_load(fh) or {}

        s = cls()
        s.db_path = Path(raw.get("db_path", str(s.db_path)))
        s.model_path = Path(raw.get("model_path", str(s.model_path)))
        s.log_level = raw.get("log_level", s.log_level)
        s.log_file = raw.get("log_file", s.log_file)
        s.ingest_batch_size = raw.get("ingest_batch_size", s.ingest_batch_size)
        s.enrich_batch_size = raw.get("enrich_batch_size", s.enrich_batch_size)
        s.dashboard_port = raw.get("dashboard_port", s.dashboard_port)
        s.timezone = raw.get("timezone", s.timezone)
        s.trend_days = raw.get("trend_days", s.trend_days)

        # Env-var override for API key (never store secrets in YAML)
        s.newsapi_key = os.getenv("NEWSAPI_KEY") or raw.get("newsapi_key")

        s.feeds = [
            FeedConfig(
                name=f["name"],
                url=f["url"],
                enabled=f.get("enabled", True),
            )
            for f in raw.get("feeds", [])
        ]
        return s
