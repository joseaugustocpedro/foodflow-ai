"""Local persistence; ticket, outbox and audit share a transaction."""
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class ClosingConnection(sqlite3.Connection):
    def __exit__(self, *args):
        try:
            return super().__exit__(*args)
        finally:
            self.close()


def now():
    return datetime.now(timezone.utc).isoformat()


def connect():
    path = Path(os.getenv('FOODFLOW_DB_PATH', str(ROOT / 'backend/foodflow_v2.sqlite3')))
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path, timeout=10, factory=ClosingConnection)
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA foreign_keys=ON')
    return con


def init_db():
    with connect() as con:
        con.executescript('''
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS sessions(id TEXT PRIMARY KEY, customer_id TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS events(
          event_id TEXT PRIMARY KEY, name TEXT NOT NULL, request_id TEXT,
          session_id TEXT, run_id TEXT, scenario_id TEXT, requested_mode TEXT,
          effective_mode TEXT, outcome TEXT, duration_ms REAL, ticket_id TEXT,
          tool TEXT, created_at TEXT NOT NULL, version TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS event_request ON events(request_id);
        CREATE TABLE IF NOT EXISTS actions(
          id TEXT PRIMARY KEY, token TEXT NOT NULL, session_id TEXT NOT NULL,
          customer_id TEXT NOT NULL, order_id TEXT NOT NULL, reason TEXT NOT NULL,
          request_id TEXT NOT NULL, expires REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS tickets(
          ticket_id TEXT PRIMARY KEY, customer_id TEXT NOT NULL, order_id TEXT NOT NULL,
          reason TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'open', created_at TEXT NOT NULL,
          request_id TEXT NOT NULL);
        CREATE UNIQUE INDEX IF NOT EXISTS open_incident ON tickets(customer_id,order_id,reason) WHERE status='open';
        CREATE TABLE IF NOT EXISTS idempotency(
          customer_id TEXT, key TEXT, fingerprint TEXT NOT NULL, ticket_id TEXT NOT NULL,
          PRIMARY KEY(customer_id,key));
        CREATE TABLE IF NOT EXISTS outbox(
          event_id TEXT PRIMARY KEY, ticket_id TEXT UNIQUE NOT NULL REFERENCES tickets(ticket_id),
          payload TEXT NOT NULL, state TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
          next_at REAL NOT NULL DEFAULT 0, lease_until REAL NOT NULL DEFAULT 0,
          lease_token TEXT, error TEXT, ack TEXT, retry_cycles INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS inbox(
          event_id TEXT PRIMARY KEY, ticket_id TEXT UNIQUE NOT NULL, payload TEXT NOT NULL,
          record_id TEXT NOT NULL, received_at TEXT NOT NULL);
        ''')
        # Additive migration: preserve prior local tickets and idempotency records.
        additions = {'sessions': {'last_order_id':'TEXT'},
                     'actions': {'valid':'INTEGER NOT NULL DEFAULT 1','invalid_reason':'TEXT','confirmed_ticket':'TEXT'},
                     'events': {'tool_call_id':'TEXT','operation_id':'TEXT','attempt_id':'TEXT','metadata':'TEXT'}}
        for table, columns in additions.items():
            present = {r['name'] for r in con.execute(f'PRAGMA table_info({table})')}
            for name, kind in columns.items():
                if name not in present:
                    con.execute(f'ALTER TABLE {table} ADD COLUMN {name} {kind}')
        con.execute('CREATE TABLE IF NOT EXISTS runtime_state(name TEXT PRIMARY KEY, value TEXT NOT NULL)')


def event(name, ctx=None, con=None, **fields):
    data = {k: (ctx or {}).get(k) for k in (
        'request_id', 'session_id', 'run_id', 'scenario_id', 'requested_mode', 'effective_mode')}
    data.update(fields)
    data.update(event_id=str(uuid.uuid4()), name=name, created_at=now(), version='demo-2.0')
    sql = f"INSERT INTO events({','.join(data)}) VALUES({','.join('?' for _ in data)})"
    if con is not None:
        con.execute(sql, tuple(data.values()))
    else:
        with connect() as connection:
            connection.execute(sql, tuple(data.values()))


def dump_events():
    with connect() as con:
        return [dict(r) for r in con.execute('SELECT * FROM events ORDER BY created_at,event_id')]
