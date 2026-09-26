from __future__ import annotations

from sqlalchemy.orm import Session as OrmSession

from ..models import SessionIngestionState
from ..util import utcnow


def get_state(db: OrmSession, session_id: int) -> SessionIngestionState:
    st = db.get(SessionIngestionState, session_id)
    if st is None:
        st = SessionIngestionState(session_id=session_id)
        db.add(st)
        db.flush()
    return st


def mark(db: OrmSession, session_id: int, stage: str, done: bool = True, error: str | None = None) -> None:
    st = get_state(db, session_id)
    setattr(st, f"{stage}_done", done)
    setattr(st, f"{stage}_at", utcnow())
    st.last_error = error
    # transforms depend on raw data; invalidate when raw data changes
    if stage in ("results", "details") and done:
        st.transforms_done = False
