"""会話ログをkaiwa.mdに追記するスクリプト。

Usage:
    python kaiwa_logger.py <nickname> <message>
    python kaiwa_logger.py --init          # kaiwa.mdを初期化
    python kaiwa_logger.py --dump          # DB内の会話を出力（デバッグ用）

各Claude sessionがsend_message前後にこのスクリプトを呼び出して会話を記録する。
ファイルロック付きで並行書き込みに対応。
"""

import sys
import os
import time
import msvcrt
from datetime import datetime
from pathlib import Path

KAIWA_FILE = Path(__file__).parent / "kaiwa.md"


def init_kaiwa():
    """kaiwa.mdを初期化"""
    header = f"""# 会話ログ — 3AI寄れば文殊の知恵

**お題**: 雨の日の家族レジャー（2026/04/04）
**参加者**: Pixel, Bree, Titan
**開始時刻**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---

"""
    with open(KAIWA_FILE, "w", encoding="utf-8") as f:
        f.write(header)
    print(f"Initialized: {KAIWA_FILE}")


def log_message(nickname, message):
    """kaiwa.mdにメッセージを追記（ファイルロック付き）"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    entry = f"\n### {nickname} ({timestamp})\n{message}\n"

    with open(KAIWA_FILE, "a", encoding="utf-8") as f:
        msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1)
        try:
            f.write(entry)
            f.flush()
        finally:
            try:
                msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
            except OSError:
                pass

    print(f"Logged: {nickname} at {timestamp}")


def dump_db():
    """DB内のメッセージを表示（デバッグ用）"""
    import sqlite3
    db_path = Path.home() / ".claude-mesh.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    # Get peer nicknames
    peers = {}
    for row in conn.execute("SELECT peer_id, nickname FROM peers"):
        peers[row["peer_id"]] = row["nickname"]

    # Get recent messages
    rows = conn.execute(
        "SELECT * FROM messages ORDER BY timestamp DESC LIMIT 50"
    ).fetchall()

    for r in rows:
        from_name = peers.get(r["from_peer"], r["from_peer"][:8])
        to_name = peers.get(r["to_peer"], r["to_peer"][:8])
        print(f"[{r['timestamp']}] {from_name} → {to_name}: {r['content'][:80]}")

    conn.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python kaiwa_logger.py <nickname> <message>")
        print("       python kaiwa_logger.py --init")
        print("       python kaiwa_logger.py --dump")
        sys.exit(1)

    if sys.argv[1] == "--init":
        init_kaiwa()
    elif sys.argv[1] == "--dump":
        dump_db()
    elif len(sys.argv) >= 3:
        log_message(sys.argv[1], " ".join(sys.argv[2:]))
    else:
        print("Usage: python kaiwa_logger.py <nickname> <message>")
        sys.exit(1)
