"""
Pipeline CLI entrypoint.
Run with: python -m scripts.run_pipeline [--stage ingest|enrich|all|train]

This is the script invoked by the cron job every 30 minutes:
    */30 * * * * cd /path/to/project && python -m scripts.run_pipeline --stage all
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure project root is on PYTHONPATH when run as a script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.application.config import Settings
from src.container import Container
from src.infrastructure.logging_config import setup_logging


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="World News Intelligence Pipeline"
    )
    parser.add_argument(
        "--stage",
        choices=["ingest", "enrich", "all", "train"],
        default="all",
        help="Pipeline stage to run (default: all)",
    )
    parser.add_argument(
        "--config",
        default="config/settings.yaml",
        help="Path to settings YAML (default: config/settings.yaml)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    try:
        settings = Settings.from_yaml(Path(args.config))
    except FileNotFoundError:
        print(f"Config file not found: {args.config}")
        sys.exit(1)

    setup_logging(level=settings.log_level, log_file=settings.log_file)

    import logging
    logger = logging.getLogger(__name__)
    logger.info("Starting pipeline – stage=%s", args.stage)

    container = Container.from_settings(settings)

    if args.stage in ("ingest", "all"):
        run = container.ingest_use_case.execute()
        logger.info(
            "Ingest complete: processed=%d failed=%d",
            run.articles_processed,
            run.articles_failed,
        )

    if args.stage in ("enrich", "all"):
        run = container.enrich_use_case.execute(batch_size=settings.enrich_batch_size)
        logger.info(
            "Enrich complete: processed=%d failed=%d",
            run.articles_processed,
            run.articles_failed,
        )

    if args.stage == "train":
        container.trainer.run()

    logger.info("Pipeline finished.")


if __name__ == "__main__":
    main()
