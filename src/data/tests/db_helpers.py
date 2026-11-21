"""Helpers for the throwaway-database fixtures (research R10).

A session template database is built once from `src/data/db/init/*.sql` (in file order) plus the
reference tables; each test module gets `CREATE DATABASE ... TEMPLATE <template>` and
drops it at teardown. The compose database is never written to by tests.
"""
from __future__ import annotations

import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo

INIT_DIR = Path(__file__).resolve().parents[1] / "db" / "init"


def _admin(dsn: str) -> psycopg.Connection:
    """Autocommit connection to the server's maintenance database (CREATE/DROP DATABASE)."""
    return psycopg.connect(make_conninfo(dsn, dbname="postgres"), autocommit=True)


def dsn_for(dsn: str, dbname: str) -> str:
    return make_conninfo(dsn, dbname=dbname)


def db_exists(dsn: str, dbname: str) -> bool:
    with _admin(dsn) as conn:
        return conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (dbname,)).fetchone() is not None


def drop_database(dsn: str, dbname: str) -> None:
    with _admin(dsn) as conn:
        conn.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(dbname)))


def build_template(dsn: str) -> str:
    """Create the template database, apply src/data/db/init/*.sql in order, load reference tables."""
    name = f"pf_tpl_{uuid.uuid4().hex[:12]}"
    with _admin(dsn) as conn:
        conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    try:
        with psycopg.connect(dsn_for(dsn, name)) as conn:
            for script in sorted(INIT_DIR.glob("*.sql")):
                conn.execute(script.read_text(encoding="utf-8"))
            conn.commit()
            _load_reference(conn)
    except BaseException:
        drop_database(dsn, name)
        raise
    return name


def _load_reference(conn: psycopg.Connection) -> None:
    from src.data.pipeline.reference import load_reference

    load_reference(conn)


@contextmanager
def throwaway_database(dsn: str, template: str) -> Iterator[str]:
    """Yield the DSN of a fresh database cloned from `template`; drop it on exit."""
    name = f"pf_test_{uuid.uuid4().hex[:12]}"
    with _admin(dsn) as conn:
        conn.execute(sql.SQL("CREATE DATABASE {} TEMPLATE {}").format(sql.Identifier(name), sql.Identifier(template)))
    try:
        yield dsn_for(dsn, name)
    finally:
        drop_database(dsn, name)
