"""Conversation model-config values at the compression tip."""


from __future__ import annotations
import json
from typing import Any, Callable, Optional
from persistence.sqlite._schema_ddl import _sql_json_extract
from persistence.sqlite.conversation._store.compression import _compression_tip_on


def update_conversation_model_config_value(db, session_id: str, key: str,
                                           update: Callable[[Any], Any]) -> Optional[str]:
    """Read a conversation-wide ``key`` at *session_id*'s compression tip and write ``update(value)``
    back, in one write transaction: a concurrent writer of the key cannot be overwritten with a stale
    copy, and a rotation cannot publish between finding the tip and writing it (the child would keep
    the old copy). ``update`` may run more than once (lock retry) and must be pure; returning None
    removes the key. Returns the id written, None when the row does not exist."""
    from persistence.sqlite.conversation._store.sessions import _parse_model_config

    def _do(conn) -> Optional[str]:
        tip = _compression_tip_on(db, conn, session_id)
        row = conn.execute("SELECT model_config FROM sessions WHERE id = ?", (tip,)).fetchone()
        if row is None:
            return None
        config = _parse_model_config(row[0])
        if (value := update(config.get(key))) is None:
            config.pop(key, None)
        else:
            config[key] = value
        conn.execute("UPDATE sessions SET model_config = ? WHERE id = ?", (json.dumps(config), tip))
        return tip
    return db._execute_write(_do)


def session_ids_with_model_config_key(db, key: str) -> list[str]:
    """Ids of the sessions whose model_config carries ``key``, newest first."""
    with db._read_ctx() as conn:
        rows = conn.execute(
            f"SELECT id FROM sessions WHERE {_sql_json_extract('model_config', '$.' + key)} IS NOT NULL "
            "ORDER BY started_at DESC").fetchall()
    return [row["id"] for row in rows]


def recent_model_config_key_ids(db, key: str, limit: int) -> list[str]:
    """The newest *limit* LIVE sessions whose model_config carries ``key``.

    "Live" excludes a compressed root: its continuation child holds the conversation and the rotation
    copies the key forward, so the root would otherwise be listed as a second, stale copy of the same
    item. The bounded form exists because a listing keyed on a JSON marker grows with history: the
    partial index ``idx_sessions_model_config_key_live`` makes this a walk over the keyed rows only,
    and ``LIMIT`` keeps the transfer to one page.
    """
    if limit <= 0:
        return []
    with db._read_ctx() as conn:
        rows = conn.execute(
            f"SELECT id FROM sessions WHERE {_sql_json_extract('model_config', '$.' + key)} IS NOT NULL "
            "AND COALESCE(end_reason, '') != 'compression' "
            "ORDER BY started_at DESC LIMIT ?", (int(limit),)).fetchall()
    return [row["id"] for row in rows]
