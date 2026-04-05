"""Run all SQL migrations against the database.

All migrations use IF NOT EXISTS / IF NOT EXISTS patterns,
so they are safe to run repeatedly (idempotent).
"""

import asyncio
import glob
import os

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


async def run_migrations():
    # Build database URL same way as app.database
    database_url = os.environ.get("DATABASE_URL", "")
    supabase_url = os.environ.get("SUPABASE_URL", "")

    if database_url:
        url = database_url
    elif supabase_url:
        project_ref = supabase_url.replace("https://", "").split(".")[0]
        url = f"postgresql+asyncpg://postgres.{project_ref}:postgres@aws-0-ap-southeast-2.pooler.supabase.com:6543/postgres"
    else:
        print("No DATABASE_URL or SUPABASE_URL set, skipping migrations")
        return

    connect_args = {}
    if "pooler.supabase.com" in url:
        connect_args["statement_cache_size"] = 0
        connect_args["prepared_statement_cache_size"] = 0

    engine = create_async_engine(url, connect_args=connect_args)

    migrations_dir = os.path.join(os.path.dirname(__file__), "alembic", "versions")
    sql_files = sorted(glob.glob(os.path.join(migrations_dir, "*.sql")))

    print(f"Running {len(sql_files)} migrations...")

    async with engine.begin() as conn:
        for sql_file in sql_files:
            name = os.path.basename(sql_file)
            with open(sql_file) as f:
                sql = f.read().strip()
            if sql:
                # asyncpg doesn't support multiple statements in one execute,
                # so split on semicolons and run each statement separately
                for statement in sql.split(";"):
                    statement = statement.strip()
                    if statement:
                        await conn.execute(text(statement))
                print(f"  ✓ {name}")

    await engine.dispose()
    print("Migrations complete.")


if __name__ == "__main__":
    asyncio.run(run_migrations())
