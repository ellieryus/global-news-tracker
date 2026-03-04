# World News Intelligence Dashboard

A **portfolio-grade, production-ready** data science project that ingests global news via RSS feeds, enriches articles with NLP (topic classification + sentiment), stores everything in DuckDB, and serves a 4-page interactive Streamlit dashboard.

Built following the full **Data Science Lifecycle**: problem framing → data acquisition → storage → cleaning → feature engineering → modelling → deployment → monitoring.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                        PRESENTATION LAYER                            │
│   Streamlit Dashboard (4 pages)                                      │
│   Page 1: Executive Overview  │  Page 2: Category Explorer           │
│   Page 3: Market Watchlist    │  Page 4: Model Monitoring            │
└───────────────────────────────┬──────────────────────────────────────┘
                                │ queries via Repository
┌───────────────────────────────▼──────────────────────────────────────┐
│                        APPLICATION LAYER                             │
│   IngestRawUseCase   EnrichNLPUseCase   ModelTrainer                 │
│   ArticleCleaner     Config (YAML)      Container (DI)               │
└────────┬─────────────────────┬──────────────────────────────────────-┘
         │ implements Port     │ implements Port
┌────────▼──────────┐  ┌───────▼──────────────────────────────────────┐
│  INFRASTRUCTURE   │  │  INFRASTRUCTURE                              │
│  feeds/           │  │  nlp/                    storage/            │
│  - RSSFeedSource  │  │  - CompositeNLPEnricher  - DuckDBArticleRepo │
│  - NewsAPISource  │  │  - MLClassifier (TF-IDF) - Schema/Migrations │
└────────┬──────────┘  │  - VADER sentiment                          │
         │             │  - Heuristic entity extractor               │
         │             └──────────────────────────────────────────────┘
         │
┌────────▼──────────────────────────────────────────────────────────-──┐
│                          DOMAIN LAYER                                │
│   Article  RawArticle  PipelineRun  NewsCategory  Sentiment          │
│   Interfaces: ArticleRepository  RawFeedSource  NLPEnricher          │
└──────────────────────────────────────────────────────────────────────┘
```

### Key Design Decisions

| Decision     | Choice                          | Rationale                                                                                                |
| ------------ | ------------------------------- | -------------------------------------------------------------------------------------------------------- |
| Storage      | **DuckDB**                      | Columnar OLAP – 10x faster for GROUP BY / date-range dashboard queries vs SQLite                         |
| Sentiment    | **VADER**                       | Designed for short news text; no runtime corpus download; compound score maps cleanly to pos/neg/neutral |
| NLP Baseline | **Keyword rules**               | Zero training data required; immediately useful                                                          |
| NLP Improved | **TF-IDF + LogisticRegression** | Lightweight ML; trains on weak labels from keyword baseline; ~1 MB model                                 |
| Dashboard    | **Streamlit**                   | Fastest path to interactive analytics; Python-native; easy deployment                                    |
| Architecture | **Layered + Ports/Adapters**    | Domain logic never imports infrastructure; fully testable; swappable components                          |

---

## Project Structure

```
news_dashboard/
├── config/
│   └── settings.yaml          # All configuration (feeds, paths, params)
├── data/
│   ├── raw/                   # Raw feed cache (gitignored)
│   └── processed/
│       ├── news.duckdb        # Main database (gitignored)
│       └── classifier.pkl     # Trained ML model (gitignored)
├── logs/                      # Rotating log files (gitignored)
├── notebooks/                 # EDA notebooks
├── scripts/
│   └── run_pipeline.py        # CLI entrypoint
├── src/
│   ├── domain/
│   │   ├── models.py          # Article, RawArticle, NewsCategory, Sentiment
│   │   └── interfaces.py      # Abstract ports (Repository, FeedSource, Enricher)
│   ├── application/
│   │   ├── cleaner.py         # Data cleaning & normalisation
│   │   ├── config.py          # Settings loader (YAML + env vars)
│   │   ├── trainer.py         # ML retraining service
│   │   └── use_cases.py       # IngestRaw, EnrichNLP orchestrators
│   ├── infrastructure/
│   │   ├── feeds/
│   │   │   └── rss.py         # RSS + NewsAPI adapters
│   │   ├── nlp/
│   │   │   └── enricher.py    # Keyword classifier, ML classifier, VADER, entities
│   │   ├── storage/
│   │   │   └── duckdb_repo.py # DuckDB repository implementation
│   │   └── logging_config.py  # Structured logging setup
│   ├── presentation/
│   │   └── dashboard.py       # Streamlit 4-page dashboard
│   └── container.py           # Dependency injection wiring
├── tests/
│   ├── unit/
│   │   └── test_pipeline.py   # Cleaner, classifier, sentiment, entities
│   └── integration/
│       └── test_repository.py # DuckDB CRUD operations
├── .gitignore
├── Makefile                   # All common commands
├── pyproject.toml             # Black + Ruff + pytest config
├── README.md
└── requirements.txt
```

---

## Quick Start

### Prerequisites

- Python 3.11+
- `pip`

### 1. Clone & Install

```bash
git clone https://github.com/yourname/news-dashboard.git
cd news-dashboard
make install
```

### 2. (Optional) Add NewsAPI Key

```bash
export NEWSAPI_KEY="your_key_here"   # free tier at newsapi.org
```

### 3. Run First Pipeline (fetch + enrich)

```bash
make run-pipeline
# Or equivalently:
python -m scripts.run_pipeline --stage all
```

### 4. Launch Dashboard

```bash
make run-dashboard
# Open: http://localhost:8501
```

---

## Automated Updates Every 30 Minutes

Install a cron job with one command:

```bash
make cron-install
```

This adds the following entry to your crontab:

```
*/30 * * * * cd /path/to/project && python -m scripts.run_pipeline --stage all >> logs/cron.log 2>&1
```

**Manage cron:**

```bash
make cron-status   # check if installed
make cron-remove   # remove it
```

**macOS alternative** (launchd) — see `scripts/` for a plist template.

---

## Pipeline Stages

```
ingest_raw → transform_clean → enrich_nlp → serve (dashboard)
```

| Stage        | What happens                                                                    |
| ------------ | ------------------------------------------------------------------------------- |
| `ingest_raw` | Fetch RSS feeds; deduplicate by URL hash; store cleaned articles                |
| `enrich_nlp` | Classify topic (keyword rules or ML), score sentiment (VADER), extract entities |
| `train`      | Retrain ML classifier on keyword-labelled corpus (run manually / weekly)        |

**Individual stage runs:**

```bash
make ingest-only    # just fetch + clean
make enrich-only    # just NLP enrichment
make train-model    # retrain ML classifier
```

---

## News Categories

| ID  | Category                             | Example Keywords                           |
| --- | ------------------------------------ | ------------------------------------------ |
| A   | Geopolitics & Conflict               | war, NATO, sanctions, ceasefire            |
| B   | Global Economy & Financial Stability | GDP, inflation, Federal Reserve, recession |
| C   | Tech & AI Power Shifts               | AI, LLM, OpenAI, semiconductor, antitrust  |
| D   | Climate & Energy                     | carbon, emissions, net zero, wildfire      |
| E   | Public Health & Demographics         | pandemic, WHO, vaccine, demographics       |
| F   | Canada-Specific                      | Bank of Canada, immigration, BoC, Quebec   |

---

## Dashboard Pages

| Page                       | Description                                                                    |
| -------------------------- | ------------------------------------------------------------------------------ |
| Executive Overview         | KPIs, article counts by category, trend lines, top sources, latest headlines   |
| Category Explorer          | Filter by category / source / date / sentiment; entity tag cloud               |
| Market & Policy Watchlist  | Keyword-signal alerts for BoC, Fed, inflation, tariffs, AI regulation, oil     |
| Model Quality & Monitoring | Confidence distribution, category drift, sentiment by category, retrain button |

---

## Adding RSS Sources

Edit `config/settings.yaml`:

```yaml
feeds:
  - name: My New Source
    url: https://example.com/rss
    enabled: true
```

---

## Running Tests

```bash
make test          # all tests
make test-cov      # with HTML coverage report (open htmlcov/index.html)
```

---

## Linting & Formatting

```bash
make lint          # ruff check
make format        # black + ruff --fix
```

---

## Monitoring & Retraining Plan

**Lightweight monitoring (built-in, Page 4):**

- Unknown category % – target < 15%
- Average confidence – target > 0.55
- Daily category distribution drift (area chart)
- Sentiment drift per category

**Retraining triggers:**

- Weekly scheduled (add `make train-model` to cron)
- On demand via dashboard button
- When UNKNOWN% > 20% or confidence < 0.5

---

## Roadmap

See [Next Improvements](#next-improvements) below.

---

## Next Improvements

### MLOps

- [ ] MLflow experiment tracking for classifier versions
- [ ] Automated retraining pipeline with performance regression gates
- [ ] A/B test keyword vs ML classifier on held-out labelled set

### Better Labelling

- [ ] Zero-shot classification via `facebook/bart-large-mnli` (no training data)
- [ ] Active learning loop: surface low-confidence articles for manual labelling
- [ ] LLM-based weak label generation (Claude API) for bootstrapping

### Source Quality

- [ ] Source credibility scoring (AllSides, Media Bias/Fact Check integration)
- [ ] Duplicate detection across sources using title semantic similarity
- [ ] Paywalled source handling (archive.ph fallback)

### Multilingual Support

- [ ] Francophone feeds (Le Monde, RFI) with language detection (langdetect)
- [ ] Translation pipeline for non-English articles before NLP

### Production

- [ ] Docker Compose deployment (pipeline + dashboard containers)
- [ ] PostgreSQL migration for multi-user / concurrent write scenarios
- [ ] Webhook alerts (Slack/email) on watchlist signal spikes
- [ ] Full-text search index (DuckDB FTS extension)
- [ ] API layer (FastAPI) to expose article data programmatically
