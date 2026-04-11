"""Run all SQL migrations against the database.

All migrations use IF NOT EXISTS / IF NOT EXISTS patterns,
so they are safe to run repeatedly (idempotent).
"""

import asyncio
import glob
import os

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


def split_sql_statements(sql: str) -> list[str]:
    """Split SQL into individual statements on top-level semicolons.

    asyncpg can't execute multi-statement strings, so we have to split,
    but a naive ``sql.split(';')`` shreds ``DO $$ ... $$`` blocks whose
    bodies contain semicolons. This walker tracks dollar-quoted regions
    (both anonymous ``$$`` and tagged ``$tag$``) and only splits on
    semicolons that are NOT inside one.
    """
    import re

    statements: list[str] = []
    current: list[str] = []
    i = 0
    n = len(sql)
    dollar_tag: str | None = None  # None when outside a $...$ block, else the open tag including $

    tag_re = re.compile(r"\$[A-Za-z_][A-Za-z0-9_]*\$|\$\$")

    while i < n:
        if dollar_tag is None:
            m = tag_re.match(sql, i)
            if m:
                dollar_tag = m.group(0)
                current.append(dollar_tag)
                i = m.end()
                continue
            ch = sql[i]
            if ch == ";":
                stmt = "".join(current).strip()
                if stmt:
                    statements.append(stmt)
                current = []
                i += 1
                continue
            current.append(ch)
            i += 1
        else:
            # Inside a dollar-quoted block — look for the matching close tag.
            close_idx = sql.find(dollar_tag, i)
            if close_idx == -1:
                # Unbalanced; bail out and append the rest verbatim.
                current.append(sql[i:])
                i = n
                dollar_tag = None
                break
            current.append(sql[i:close_idx + len(dollar_tag)])
            i = close_idx + len(dollar_tag)
            dollar_tag = None

    tail = "".join(current).strip()
    if tail:
        statements.append(tail)
    return statements


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
        # Extend statement timeout for migrations (Supabase pooler default is often too short)
        # Use SET LOCAL so it works with PgBouncer in transaction mode
        await conn.execute(text("SET LOCAL statement_timeout = '120s'"))

        for sql_file in sql_files:
            name = os.path.basename(sql_file)
            with open(sql_file) as f:
                sql = f.read().strip()
            if sql:
                # asyncpg doesn't support multiple statements per execute,
                # so split on top-level semicolons (preserving $$...$$ blocks)
                # and run each statement separately.
                for statement in split_sql_statements(sql):
                    await conn.execute(text(statement))
                print(f"  ✓ {name}")

    await engine.dispose()
    print("Migrations complete.")


if __name__ == "__main__":
    asyncio.run(run_migrations())
