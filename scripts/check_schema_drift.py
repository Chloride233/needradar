"""Fail when Alembic migrations do not create every ORM table."""

from __future__ import annotations

import asyncio
import os
import sys

from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import create_async_engine

from needradar.core.config import settings
from needradar.models import Base


async def main() -> int:
    database_url = os.environ.get("NR_DATABASE_URL", settings.database_url)
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as conn:
            existing_tables, existing_columns = await conn.run_sync(_inspect_schema)
    finally:
        await engine.dispose()

    expected_tables = set(Base.metadata.tables)
    missing_tables = sorted(expected_tables - existing_tables)
    extra_tables = sorted(existing_tables - expected_tables - {"alembic_version"})
    missing_columns = {
        table_name: sorted(set(table.columns.keys()) - existing_columns.get(table_name, set()))
        for table_name, table in Base.metadata.tables.items()
        if table_name in existing_tables
        and set(table.columns.keys()) - existing_columns.get(table_name, set())
    }

    if missing_tables or missing_columns:
        if missing_tables:
            print("Alembic schema is missing ORM tables:")
        for table in missing_tables:
            print(f"  - {table}")
        if missing_columns:
            print("Alembic schema is missing ORM columns:")
            for table, columns in missing_columns.items():
                print(f"  - {table}: {', '.join(columns)}")
        return 1

    if extra_tables:
        print("Warning: Alembic schema has tables that are not mapped by ORM:")
        for table in extra_tables:
            print(f"  - {table}")

    print(f"Alembic schema contains all {len(expected_tables)} ORM tables.")
    return 0


def _inspect_schema(sync_conn):
    inspector = inspect(sync_conn)
    tables = set(inspector.get_table_names())
    columns = {
        table: {column["name"] for column in inspector.get_columns(table)}
        for table in tables
    }
    return tables, columns


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
