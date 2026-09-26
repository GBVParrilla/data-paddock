"""Engine + session factory + generic upsert helper."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterable, Iterator, Sequence

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from .config import DATABASE_URL, PROJECT_ROOT

_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        if DATABASE_URL.startswith("sqlite"):
            (PROJECT_ROOT / "data").mkdir(exist_ok=True)
            _engine = create_engine(DATABASE_URL, future=True, connect_args={"check_same_thread": False, "timeout": 60})

            @event.listens_for(_engine, "connect")
            def _sqlite_pragmas(dbapi_conn, _):  # pragma: no cover - trivial
                cur = dbapi_conn.cursor()
                cur.execute("PRAGMA foreign_keys=ON")
                cur.execute("PRAGMA journal_mode=WAL")
                cur.close()
        else:
            _engine = create_engine(DATABASE_URL, future=True, pool_pre_ping=True)
    return _engine


def get_sessionmaker() -> sessionmaker[Session]:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), expire_on_commit=False, future=True)
    return _SessionLocal


@contextmanager
def db_session() -> Iterator[Session]:
    s = get_sessionmaker()()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def init_db() -> None:
    from . import models  # noqa: F401  (registers tables)

    models.Base.metadata.create_all(get_engine())


def upsert(session: Session, model: Any, rows: Sequence[dict], conflict_cols: Iterable[str], chunk: int = 500) -> int:
    """Insert-or-update rows keyed on conflict_cols.

    Works on SQLite and Postgres (both support ON CONFLICT DO UPDATE), so the
    transforms/ingestion are safe to re-run - the seam live mode will rely on.
    Returns the number of rows sent.
    """
    if not rows:
        return 0
    conflict_cols = list(conflict_cols)
    dialect = session.get_bind().dialect.name
    if dialect == "postgresql":
        from sqlalchemy.dialects.postgresql import insert as dialect_insert
    else:
        from sqlalchemy.dialects.sqlite import insert as dialect_insert

    table = model.__table__
    total = 0
    for i in range(0, len(rows), chunk):
        batch = rows[i : i + chunk]
        stmt = dialect_insert(table).values(batch)
        update_cols = {c.name: getattr(stmt.excluded, c.name) for c in table.columns if c.name not in conflict_cols and c.name != "id"}
        if update_cols:
            stmt = stmt.on_conflict_do_update(index_elements=conflict_cols, set_=update_cols)
        else:
            stmt = stmt.on_conflict_do_nothing(index_elements=conflict_cols)
        session.execute(stmt)
        total += len(batch)
    return total
