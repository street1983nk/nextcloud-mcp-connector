"""Single-process SQLite outbox; encrypted callback material, bounded retention."""

import json
import sqlite3
from pathlib import Path

from ..oauth.crypto import decrypt, encrypt


class EventStore:
    def __init__(self, path: Path, key: bytes):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.key = key
        self.db.executescript("""
          PRAGMA foreign_keys=ON;
          PRAGMA journal_mode=WAL;
          CREATE TABLE IF NOT EXISTS subscriptions (
            id TEXT PRIMARY KEY, auth TEXT NOT NULL, principal TEXT NOT NULL,
            room TEXT NOT NULL, sealed BLOB NOT NULL, expires REAL NOT NULL);
          CREATE TABLE IF NOT EXISTS deliveries (
            id TEXT PRIMARY KEY, sub TEXT NOT NULL REFERENCES subscriptions(id) ON DELETE CASCADE,
            message TEXT NOT NULL, actor TEXT NOT NULL, created REAL NOT NULL,
            due REAL NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
            state TEXT NOT NULL DEFAULT 'pending', status INTEGER);
          CREATE INDEX IF NOT EXISTS due_events ON deliveries(state,due);
        """)
        self.db.commit()

    def close(self):
        self.db.close()

    def prune(self, now: float):
        self.db.execute("DELETE FROM subscriptions WHERE expires<=?", (now,))
        self.db.execute("DELETE FROM deliveries WHERE created<?", (now - 86400,))
        self.db.commit()

    def get(self, sid: str):
        row = self.db.execute("SELECT * FROM subscriptions WHERE id=?", (sid,)).fetchone()
        if row is None:
            return None
        result = dict(row)
        result.update(json.loads(decrypt(self.key, row["sealed"], aad="talk-event:" + sid)))
        return result

    def put(self, sid: str, auth: str, principal: str, room: str, expires: float, material: dict):
        sealed = encrypt(self.key, json.dumps(material).encode(), aad="talk-event:" + sid)
        self.db.execute(
            """INSERT INTO subscriptions VALUES (?,?,?,?,?,?)
          ON CONFLICT(id) DO UPDATE SET sealed=excluded.sealed, expires=excluded.expires""",
            (sid, auth, principal, room, sealed, expires),
        )
        self.db.commit()

    def remove(self, sid: str):
        self.db.execute("DELETE FROM subscriptions WHERE id=?", (sid,))
        self.db.commit()

    def enqueue(self, room: str, mid: str, actor: str, now: float):
        from .protocol import stable_id

        subs = self.db.execute(
            "SELECT id FROM subscriptions WHERE room=? AND principal<>? AND expires>?",
            (room, actor, now),
        ).fetchall()
        if self.db.execute("SELECT count(*) FROM deliveries").fetchone()[0] + len(subs) > 10000:
            raise OverflowError("Outbox full")
        for sub in subs:
            self.db.execute(
                "INSERT OR IGNORE INTO deliveries(id,sub,message,actor,created,due) "
                "VALUES (?,?,?,?,?,?)",
                (stable_id(sub["id"], room, mid), sub["id"], mid, actor, now, now),
            )
        self.db.commit()

    def next(self, now: float):
        return self.db.execute(
            "SELECT * FROM deliveries WHERE state='pending' AND due<=? ORDER BY due LIMIT 1", (now,)
        ).fetchone()

    def finish(self, eid: str, attempts: int, state: str, status: int, due: float):
        self.db.execute(
            "UPDATE deliveries SET attempts=?,state=?,status=?,due=? WHERE id=?",
            (attempts, state, status, due, eid),
        )
        self.db.commit()
