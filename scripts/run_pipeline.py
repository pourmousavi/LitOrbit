#!/usr/bin/env python3
"""CLI entry point for the LitOrbit paper discovery pipeline.

Usage:
    python scripts/run_pipeline.py
"""
import asyncio
import logging
import sys
import os

# Add the backend directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "backend", ".env"))

from app import database as db_module
from app.database import init_db
from app.pipeline.runner import run_discovery_pipeline
from app.services.digest_runner import run_digests
from app.services.discovery.journals_seed import JOURNALS_SEED
from app.models.journal_config import JournalConfig

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def seed_journals_if_empty(db):
    """Seed journal_config table if it has no entries."""
    from sqlalchemy import select, func

    result = await db.execute(select(func.count()).select_from(JournalConfig))
    count = result.scalar()
    if count == 0:
        logger.info("Seeding journal_config with 13 journals...")
        for j in JOURNALS_SEED:
            db.add(JournalConfig(**j))
        await db.commit()
        logger.info("Journal seeding complete")


async def main():
    logger.info("Starting LitOrbit pipeline...")
    init_db()

    async with db_module.async_session_factory() as db:
        await seed_journals_if_empty(db)
        result = await run_discovery_pipeline(db)

    if result["status"] == "success":
        logger.info(f"Pipeline succeeded: {result}")
    else:
        logger.error(f"Pipeline failed: {result}")
        sys.exit(1)

    # Send digest emails after successful pipeline run
    skip_digest = os.environ.get("SKIP_DIGEST", "").lower() in ("1", "true", "yes")
    if not skip_digest:
        logger.info("Running digest emails...")
        async with db_module.async_session_factory() as db:
            digest_results = await run_digests(db)
            sent = sum(1 for r in digest_results if r.get("sent"))
            logger.info(f"Digest complete: {sent}/{len(digest_results)} emails sent")


if __name__ == "__main__":
    asyncio.run(main())
