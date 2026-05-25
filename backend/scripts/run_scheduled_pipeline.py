"""Standalone runner for the daily scheduled pipeline.

Runs the same four-stage job as POST
/api/v1/admin/pipeline/run-scheduled (discovery → news → cross-links →
digest) without the HTTP/streaming wrapper. Intended for use as a Render
Cron Job so the heavy work no longer runs inside the single-uvicorn-worker
web service.

Usage:
    cd backend
    python -m scripts.run_scheduled_pipeline
"""

import asyncio
import json
import logging
import sys


def configure_logging() -> None:
    logging.basicConfig(
        stream=sys.stdout,
        level=logging.INFO,
        format="%(levelname)s:%(name)s: %(message)s",
        force=True,
    )
    logging.getLogger("app.pipeline").setLevel(logging.INFO)
    logging.getLogger("app.services").setLevel(logging.INFO)


async def main() -> int:
    configure_logging()
    logger = logging.getLogger(__name__)

    from app import database as db_module
    from app.routers.admin import _run_full_scheduled_job

    db_module.init_db()

    logger.info("Starting scheduled pipeline run")
    result = await _run_full_scheduled_job()
    print(json.dumps(result, default=str, indent=2))

    pipeline_status = result.get("pipeline", {}).get("status")
    return 0 if pipeline_status != "failed" else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
