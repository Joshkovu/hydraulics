"""Optional Neon persistence for calculation history.

The web calculator remains usable without a database. When DATABASE_URL is set,
one process-local connection is reused and history is stored as JSONB so the
calculation contract can evolve without destructive migrations.
"""

import json
import os
import threading

import psycopg


_connection = None
_lock = threading.Lock()


def configured():
    return bool(os.getenv("DATABASE_URL"))


def _get_connection():
    global _connection
    if not configured():
        return None
    if _connection is None or _connection.closed:
        _connection = psycopg.connect(os.environ["DATABASE_URL"], autocommit=True)
        with _connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS calculation_history (
                    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    shape TEXT NOT NULL,
                    category TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    request JSONB NOT NULL,
                    result JSONB NOT NULL
                )
                """
            )
    return _connection


def record(request, result):
    """Persist a successful calculation without making the API depend on Neon."""
    if not configured():
        return False
    with _lock:
        try:
            connection = _get_connection()
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO calculation_history (shape, category, operation, request, result)
                    VALUES (%s, %s, %s, %s::jsonb, %s::jsonb)
                    """,
                    (
                        request["shape"],
                        request["category"],
                        request["operation"],
                        json.dumps(request),
                        json.dumps(result),
                    ),
                )
            return True
        except psycopg.Error:
            _reset_connection()
            return False


def recent(limit=20):
    """Return the newest records using an indexed primary-key order."""
    if not configured():
        return []
    safe_limit = max(1, min(int(limit), 100))
    with _lock:
        try:
            connection = _get_connection()
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, created_at, shape, category, operation, result
                    FROM calculation_history
                    ORDER BY id DESC
                    LIMIT %s
                    """,
                    (safe_limit,),
                )
                return [
                    {
                        "id": row[0],
                        "created_at": row[1].isoformat(),
                        "shape": row[2],
                        "category": row[3],
                        "operation": row[4],
                        "result": row[5],
                    }
                    for row in cursor.fetchall()
                ]
        except psycopg.Error:
            _reset_connection()
            return []


def _reset_connection():
    global _connection
    if _connection is not None and not _connection.closed:
        _connection.close()
    _connection = None