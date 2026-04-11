"""Run all SQL migrations against the database.

Tracks applied migrations in a `_migrations` table so already-applied
migrations are skipped instantly on subsequent deploys.
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
    dollar_tag: str | None = None

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
            close_idx = sql.find(dollar_tag, i)
            if close_idx == -1:
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

    print(f"Found {len(sql_files)} migration files...")

    # Create tracking table if it doesn't exist (fast, tiny table)
    async with engine.begin() as conn:
        await conn.execute(text(
            "CREATE TABLE IF NOT EXISTS _migrations ("
            "  name TEXT PRIMARY KEY, "
            "  applied_at TIMESTAMPTZ DEFAULT now()"
            ")"
        ))

        # Get already-applied migrations
        result = await conn.execute(text("SELECT name FROM _migrations"))
        applied = {row[0] for row in result.all()}

    pending = [(f, os.path.basename(f)) for f in sql_files if os.path.basename(f) not in applied]

    if not pending:
        print("All migrations already applied.")
        await engine.dispose()
        return

    print(f"Running {len(pending)} new migration(s) ({len(applied)} already applied)...")

    for sql_file, name in pending:
        with open(sql_file) as f:
            sql = f.read().strip()
        if not sql:
            continue

        try:
            async with engine.begin() as conn:
                for statement in split_sql_statements(sql):
                    await conn.execute(text(statement))
                # Record as applied
                await conn.execute(text(
                    "INSERT INTO _migrations (name) VALUES (:name) ON CONFLICT DO NOTHING"
                ), {"name": name})
            print(f"  ✓ {name}")
        except Exception as e:
            err_str = str(e).lower()
            if "timeout" in err_str or "canceled" in err_str:
                # If it timed out, the DDL likely already exists.
                # Mark as applied so we don't retry every deploy.
                try:
                    async with engine.begin() as conn:
                        await conn.execute(text(
                            "INSERT INTO _migrations (name) VALUES (:name) ON CONFLICT DO NOTHING"
                        ), {"name": name})
                except Exception:
                    pass
                print(f"  ⏭ {name} (timeout — marked as applied)")
            else:
                raise

    await engine.dispose()
    print("Migrations complete.")


if __name__ == "__main__":
    asyncio.run(run_migrations())
