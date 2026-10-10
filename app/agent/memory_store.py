"""Long-term memory for the agent: a small history of what happened for each user.

Stored in a SQLite file (default data/agent_memory.db, change with env MEMORY_DB), so it survives between
runs: the agent can later see that a user had the same problem before. Short-term memory (the conversation
itself) is handled separately, in gateway_agent.py.
"""
import os
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

class MemoryStore:
    def __init__(self, path=None):
        self.path = Path(path or os.getenv("MEMORY_DB", "data/agent_memory.db"))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(str(self.path))) as db:
            db.execute("""CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, subject TEXT NOT NULL,
                category TEXT, event TEXT NOT NULL, ticket_ref TEXT, detail TEXT, outcome TEXT)""")
            db.commit()

    def record(self, subject, category, event, ticket_ref="", detail="", outcome=""):
        with closing(sqlite3.connect(str(self.path))) as db:
            db.execute("INSERT INTO events (ts, subject, category, event, ticket_ref, detail, outcome) VALUES (?,?,?,?,?,?,?)",
                       (datetime.now().isoformat(timespec="seconds"), str(subject).strip().lower(), category, event,
                        ticket_ref, detail, outcome))
            db.commit()

    def history(self, subject, limit=10):
        """The most recent events for one user, newest first."""
        with closing(sqlite3.connect(str(self.path))) as db:
            db.row_factory = sqlite3.Row
            rows = db.execute("SELECT ts, subject, category, event, ticket_ref, detail, outcome FROM events "
                              "WHERE subject = ? ORDER BY id DESC LIMIT ?",
                              (str(subject).strip().lower(), int(limit))).fetchall()
        return [dict(r) for r in rows]

    def clear(self):
        with closing(sqlite3.connect(str(self.path))) as db:
            db.execute("DELETE FROM events")
            db.commit()
