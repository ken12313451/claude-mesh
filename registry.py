"""Peer Registry — SQLite-based peer and message storage."""

import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_DB_PATH = Path.home() / ".claude-mesh.db"


class PeerRegistry:
    def __init__(self, db_path=None):
        self.db_path = db_path or DEFAULT_DB_PATH
        self.db = sqlite3.connect(str(self.db_path))
        self.db.row_factory = sqlite3.Row
        self._init_tables()

    def _init_tables(self):
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS peers (
                peer_id TEXT PRIMARY KEY,
                machine_id TEXT NOT NULL,
                machine_name TEXT,
                session_dir TEXT,
                summary TEXT DEFAULT '',
                is_local BOOLEAN DEFAULT 1,
                last_seen TEXT,
                status TEXT DEFAULT 'online'
            );
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_peer TEXT NOT NULL,
                to_peer TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                read BOOLEAN DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_messages_to ON messages(to_peer, read);
            CREATE INDEX IF NOT EXISTS idx_peers_machine ON peers(machine_id);
        """)
        self.db.commit()

    def register(self, peer_id, machine_id, machine_name="", session_dir="", summary=""):
        now = datetime.now(timezone.utc).isoformat()
        self.db.execute(
            """INSERT OR REPLACE INTO peers
               (peer_id, machine_id, machine_name, session_dir, summary, is_local, last_seen, status)
               VALUES (?, ?, ?, ?, ?, 1, ?, 'online')""",
            (peer_id, machine_id, machine_name, session_dir, summary, now),
        )
        self.db.commit()

    def unregister(self, peer_id):
        self.db.execute("UPDATE peers SET status='offline' WHERE peer_id=?", (peer_id,))
        self.db.commit()

    def set_summary(self, peer_id, summary):
        self.db.execute("UPDATE peers SET summary=? WHERE peer_id=?", (summary, peer_id))
        self.db.commit()

    def heartbeat(self, peer_id):
        now = datetime.now(timezone.utc).isoformat()
        self.db.execute(
            "UPDATE peers SET last_seen=?, status='online' WHERE peer_id=?",
            (now, peer_id),
        )
        self.db.commit()

    def update_remote_peers(self, machine_id, machine_name, peers):
        """Replace all remote peers for a given machine with fresh data."""
        now = datetime.now(timezone.utc).isoformat()
        self.db.execute(
            "DELETE FROM peers WHERE machine_id=? AND is_local=0",
            (machine_id,),
        )
        for p in peers:
            self.db.execute(
                """INSERT OR REPLACE INTO peers
                   (peer_id, machine_id, machine_name, session_dir, summary, is_local, last_seen, status)
                   VALUES (?, ?, ?, ?, ?, 0, ?, ?)""",
                (
                    p["peer_id"], machine_id, machine_name,
                    p.get("session_dir", ""), p.get("summary", ""),
                    now, p.get("status", "online"),
                ),
            )
        self.db.commit()

    def list_peers(self, scope="all"):
        if scope == "local":
            rows = self.db.execute("SELECT * FROM peers WHERE is_local=1").fetchall()
        elif scope == "remote":
            rows = self.db.execute("SELECT * FROM peers WHERE is_local=0").fetchall()
        else:
            rows = self.db.execute("SELECT * FROM peers").fetchall()
        return [dict(r) for r in rows]

    def find_peer(self, query):
        """Find a peer by id, summary substring, or machine_name:summary pattern."""
        if ":" in query:
            machine, summary = query.split(":", 1)
            row = self.db.execute(
                "SELECT * FROM peers WHERE machine_name LIKE ? AND summary LIKE ? AND status='online' LIMIT 1",
                (f"%{machine}%", f"%{summary}%"),
            ).fetchone()
        else:
            row = self.db.execute(
                "SELECT * FROM peers WHERE peer_id=? OR summary LIKE ?",
                (query, f"%{query}%"),
            ).fetchone()
        return dict(row) if row else None

    def store_message(self, from_peer, to_peer, content):
        now = datetime.now(timezone.utc).isoformat()
        self.db.execute(
            "INSERT INTO messages (from_peer, to_peer, content, timestamp) VALUES (?, ?, ?, ?)",
            (from_peer, to_peer, content, now),
        )
        self.db.commit()

    def get_messages(self, peer_id, unread_only=True):
        if unread_only:
            rows = self.db.execute(
                "SELECT * FROM messages WHERE to_peer=? AND read=0 ORDER BY timestamp",
                (peer_id,),
            ).fetchall()
        else:
            rows = self.db.execute(
                "SELECT * FROM messages WHERE to_peer=? ORDER BY timestamp",
                (peer_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def mark_read(self, message_ids):
        if not message_ids:
            return
        placeholders = ",".join("?" * len(message_ids))
        self.db.execute(
            f"UPDATE messages SET read=1 WHERE id IN ({placeholders})",
            message_ids,
        )
        self.db.commit()

    def get_local_peers_for_sync(self):
        """Get local peer data formatted for remote sync."""
        rows = self.db.execute(
            "SELECT peer_id, session_dir, summary, status FROM peers WHERE is_local=1"
        ).fetchall()
        return [dict(r) for r in rows]

    def close(self):
        self.db.close()
