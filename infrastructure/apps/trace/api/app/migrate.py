import logging
import os
from pathlib import Path

import asyncpg

log = logging.getLogger("trace.migrate")


async def run_migrations(conn: asyncpg.Connection, migrations_dir: str) -> None:
    """Apply every *.sql file in migrations_dir whose version is not already in
    core.schema_migrations. Files are sorted by name (e.g. 0001_init.sql)."""
    path = Path(migrations_dir)
    if not path.is_dir():
        log.warning("migrations dir not found: %s", migrations_dir)
        return

    # Bootstrap: schema_migrations may not exist yet on a fresh DB.
    await conn.execute(
        """
        CREATE SCHEMA IF NOT EXISTS core;
        CREATE TABLE IF NOT EXISTS core.schema_migrations (
            version    TEXT PRIMARY KEY,
            applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        """
    )

    applied = {
        r["version"]
        for r in await conn.fetch("SELECT version FROM core.schema_migrations")
    }

    files = sorted(p for p in path.iterdir() if p.suffix == ".sql")
    for f in files:
        version = f.stem
        if version in applied:
            continue
        sql = f.read_text()
        log.info("applying migration %s", version)
        async with conn.transaction():
            await conn.execute(sql)
            # Some migrations insert their own marker row; ignore if present.
            await conn.execute(
                "INSERT INTO core.schema_migrations(version) VALUES($1) "
                "ON CONFLICT (version) DO NOTHING",
                version,
            )
        log.info("migration %s applied", version)


async def migrate_with_pool(pool: asyncpg.Pool) -> None:
    async with pool.acquire() as conn:
        await run_migrations(conn, os.environ.get("MIGRATIONS_DIR", "/migrations"))
