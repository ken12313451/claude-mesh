"""MCP Server for claude-mesh.

Each Claude Code session runs this as an MCP server (stdio transport).
Communicates with the local Mesh Broker via HTTP on localhost:7901.
Auto-starts the broker if not running.
Polls for new messages and delivers them as MCP notifications.
"""

import atexit
import json
import os
import subprocess
import sys
import threading
import time
import uuid

# Ensure UTF-8 for all I/O on Windows
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")
if hasattr(sys.stdin, "reconfigure"):
    sys.stdin.reconfigure(encoding="utf-8")
from http.client import HTTPConnection
from pathlib import Path

# Nickname file: maps cwd -> nickname for statusline integration
NICK_FILE = Path.home() / ".claude-mesh-nick"


_RAINBOW_COLORS = [196, 208, 226, 46, 51, 129]  # red, orange, yellow, green, cyan, purple


def _rainbow(text: str) -> str:
    """Apply rainbow ANSI colors to text."""
    result = ""
    for i, ch in enumerate(text):
        c = _RAINBOW_COLORS[i % len(_RAINBOW_COLORS)]
        result += f"\x1b[38;5;{c}m{ch}"
    return result + "\x1b[0m"


def _normalize_path(p: str) -> str:
    """Normalize path for cross-format comparison (Git Bash vs Windows)."""
    return p.replace("\\", "/").lower().rstrip("/")


def _save_nickname(nickname: str):
    """Save this session's nickname to the shared nick file, keyed by peer_id."""
    try:
        data = {}
        if NICK_FILE.exists():
            data = json.loads(NICK_FILE.read_text(encoding="utf-8"))
        data[PEER_ID] = {
            "nickname": nickname,
            "project_dir": _normalize_path(SESSION_DIR),
            "registered_at": time.time(),
        }
        NICK_FILE.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def _remove_nickname():
    """Remove this session's entry from the nick file on exit."""
    try:
        if NICK_FILE.exists():
            data = json.loads(NICK_FILE.read_text(encoding="utf-8"))
            data.pop(PEER_ID, None)
            NICK_FILE.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


# Broker API endpoint
BROKER_HOST = "127.0.0.1"
BROKER_PORT = int(os.environ.get("CLAUDE_MESH_BROKER_PORT", "7901"))

# Path to broker.py (same directory as this file)
BROKER_SCRIPT = Path(__file__).parent / "broker.py"

# This session's identity
PEER_ID = str(uuid.uuid4())
SESSION_DIR = os.getcwd()

# Message polling interval (seconds)
POLL_INTERVAL = 3

# Broker subprocess (if we started it)
_broker_process = None

# Lock for stdout (MCP stdio is single-threaded but we have a poller thread)
_stdout_lock = threading.Lock()



def _sanitize_surrogates(s: str) -> str:
    """Remove surrogate characters that break UTF-8 encoding on Windows."""
    return s.encode("utf-8", errors="replace").decode("utf-8")


def broker_request(method: str, path: str, body: dict | None = None) -> dict:
    """Make a request to the local Mesh Broker API."""
    conn = HTTPConnection(BROKER_HOST, BROKER_PORT, timeout=5)
    try:
        if body is not None:
            raw = json.dumps(body, ensure_ascii=False)
            data = _sanitize_surrogates(raw).encode("utf-8")
            conn.request(method, path, body=data,
                         headers={"Content-Type": "application/json",
                                  "Content-Length": str(len(data))})
        else:
            conn.request(method, path)
        resp = conn.getresponse()
        return json.loads(resp.read().decode())
    except Exception as e:
        return {"status": "error", "message": str(e)}
    finally:
        conn.close()


def is_broker_running() -> bool:
    """Check if broker is responding."""
    try:
        result = broker_request("GET", "/status")
        return result.get("machine_id") is not None
    except Exception:
        return False


def ensure_broker():
    """Start broker as subprocess if not already running."""
    global _broker_process
    if is_broker_running():
        return

    _broker_process = subprocess.Popen(
        [sys.executable, str(BROKER_SCRIPT)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )

    # Wait for broker to be ready
    for _ in range(20):
        time.sleep(0.5)
        if is_broker_running():
            return
    # If still not ready, continue anyway — tools will report errors


def stop_broker():
    """Stop broker if we started it."""
    global _broker_process
    if _broker_process:
        _broker_process.terminate()
        _broker_process = None


def register():
    """Register this session with the broker. Auto-generates summary from machine + directory."""
    # Auto summary: last directory component
    dir_name = Path(SESSION_DIR).name or "home"
    result = broker_request("POST", "/register", {
        "peer_id": PEER_ID,
        "session_dir": SESSION_DIR,
        "summary": dir_name,
    })
    # Save nickname for statusline
    nickname = result.get("nickname")
    if nickname:
        _save_nickname(nickname)
    return result


def unregister():
    """Unregister this session."""
    broker_request("POST", "/unregister", {"peer_id": PEER_ID})
    _remove_nickname()


def send_mcp_notification(method: str, params: dict):
    """Send a JSON-RPC notification to Claude Code via stdout."""
    notification = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params,
    }
    with _stdout_lock:
        sys.stdout.write(json.dumps(notification, ensure_ascii=False) + "\n")
        sys.stdout.flush()


def message_poller():
    """Background thread: heartbeat, message polling, and channel push.

    - Sends heartbeat every cycle to keep peer alive in registry
    - Polls for new messages with mark_read=false
    - Pushes via notifications/claude/channel for real-time delivery
    """
    notified_ids = set()
    heartbeat_counter = 0
    while True:
        try:
            # Heartbeat every 30 seconds (10 cycles * 3s interval)
            heartbeat_counter += 1
            if heartbeat_counter >= 10:
                broker_request("POST", "/heartbeat", {
                    "peer_id": PEER_ID,
                    "session_dir": SESSION_DIR,
                })
                heartbeat_counter = 0

            # Poll for messages
            result = broker_request("GET", f"/messages?peer_id={PEER_ID}&mark_read=false")
            messages = result.get("messages", [])
            for m in messages:
                msg_id = m.get("id")
                if msg_id not in notified_ids:
                    notified_ids.add(msg_id)
                    from_nick = m.get("from_nickname", "")
                    from_label = from_nick or m["from_peer"][:8]
                    colored_name = _rainbow(from_label)
                    # Send header line
                    BG = "\x1b[40m\x1b[37m"  # black bg, white fg
                    RST = "\x1b[0m"
                    colored_header = _rainbow(f"━━━ {from_label} ━━━")
                    send_mcp_notification("notifications/claude/channel", {
                        "content": f"{BG}{colored_header}{RST}",
                        "meta": {"from_id": "system", "from_summary": "", "sent_at": ""},
                    })
                    # Send each line of the message separately
                    lines = m["content"].split("\n")
                    for line in lines:
                        send_mcp_notification("notifications/claude/channel", {
                            "content": f"{BG}  {line}{RST}",
                            "meta": {"from_id": "system", "from_summary": "", "sent_at": ""},
                        })
                    # Send footer (with full meta for AI context)
                    send_mcp_notification("notifications/claude/channel", {
                        "content": f"{BG}{colored_header}{RST}",
                        "meta": {
                            "from_id": m["from_peer"],
                            "from_nickname": from_nick,
                            "from_summary": m.get("from_summary", ""),
                            "from_cwd": m.get("from_cwd", ""),
                            "sent_at": m.get("timestamp", ""),
                        },
                    })
        except Exception:
            pass
        time.sleep(POLL_INTERVAL)


# --- MCP Tool implementations ---

def tool_list_peers(scope: str = "all") -> str:
    result = broker_request("GET", f"/peers?scope={scope}")
    peers = result.get("peers", [])
    if not peers:
        return "No peers found."
    lines = []
    for p in peers:
        location = "local" if p.get("is_local") else f"remote ({p.get('machine_name', '?')})"
        nickname = p.get("nickname", "") or "?"
        summary = p.get("summary", "") or "(no summary)"
        status = p.get("status", "?")
        me = " ← YOU" if p["peer_id"] == PEER_ID else ""
        lines.append(f"- [{status}] {nickname} | {summary} @ {location} (id: {p['peer_id'][:8]}){me}")
    return "\n".join(lines)


def tool_send_message(to: str, message: str) -> str:
    # Phase 10: broadcast to all peers
    if to.lower() == "all":
        peers = broker_request("GET", "/peers?scope=all").get("peers", [])
        targets = [p for p in peers if p["peer_id"] != PEER_ID and p.get("status") == "online"]
        if not targets:
            return "No online peers to send to."
        results = []
        for p in targets:
            r = broker_request("POST", "/send", {
                "from": PEER_ID,
                "to": p["peer_id"],
                "content": message,
            })
            label = p.get("nickname") or p["peer_id"][:8]
            results.append(f"{label}: {'ok' if r.get('status') == 'ok' else 'failed'}")
        return f"Broadcast to {len(targets)} peers: " + ", ".join(results)

    # Phase 9: multicast to comma-separated targets
    if "," in to:
        targets = [t.strip() for t in to.split(",") if t.strip()]
        results = []
        for t in targets:
            r = broker_request("POST", "/send", {
                "from": PEER_ID,
                "to": t,
                "content": message,
            })
            if r.get("status") == "ok":
                results.append(f"{r.get('delivered_to', t)}: ok")
            else:
                results.append(f"{t}: failed ({r.get('message', '?')})")
        return f"Sent to {len(targets)} peers: " + ", ".join(results)

    # Single target (existing behavior)
    result = broker_request("POST", "/send", {
        "from": PEER_ID,
        "to": to,
        "content": message,
    })
    if result.get("status") == "ok":
        delivered = result.get("delivered_to", to)
        SEND_BG = "\x1b[41m\x1b[37m"  # red bg, white fg
        RST = "\x1b[0m"
        header = _rainbow(f"━━━ → {delivered} ━━━")
        return f"{SEND_BG}{header}\n{message}\n{header}{RST}\nMessage sent to {delivered}"
    return f"Failed: {result.get('message', 'unknown error')}"


def tool_check_messages() -> str:
    result = broker_request("GET", f"/messages?peer_id={PEER_ID}")
    messages = result.get("messages", [])
    if not messages:
        return "No new messages."
    lines = []
    for m in messages:
        lines.append(f"From {m['from_peer'][:8]} ({m['timestamp']}):\n{m['content']}\n")
    return "\n---\n".join(lines)


def tool_set_summary(summary: str) -> str:
    broker_request("POST", "/summary", {
        "peer_id": PEER_ID,
        "summary": summary,
    })
    return f"Summary set to: {summary}"


def tool_set_nickname(nickname: str) -> str:
    broker_request("POST", "/nickname", {
        "peer_id": PEER_ID,
        "nickname": nickname,
    })
    _save_nickname(nickname)
    return f"Nickname set to: {nickname}"


def tool_status() -> str:
    result = broker_request("GET", "/status")
    # Add own peer info
    peers = broker_request("GET", "/peers?scope=local")
    for p in peers.get("peers", []):
        if p["peer_id"] == PEER_ID:
            result["my_peer_id"] = PEER_ID
            result["my_nickname"] = p.get("nickname", "?")
            result["my_summary"] = p.get("summary", "")
            break
    return json.dumps(result, indent=2, ensure_ascii=False)


# --- MCP stdio protocol ---

TOOLS = {
    "list_peers": {
        "description": "List available Claude Code sessions (peers). Scope: local, remote, or all.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "scope": {
                    "type": "string",
                    "enum": ["local", "remote", "all"],
                    "default": "all",
                    "description": "Filter peers by location",
                }
            },
        },
        "handler": lambda args: tool_list_peers(args.get("scope", "all")),
    },
    "send_message": {
        "description": "Send a message to Claude Code sessions. Supports: single target (nickname/peer_id/summary), multiple targets (comma-separated, e.g. 'Cubby,Star'), or broadcast ('all').",
        "inputSchema": {
            "type": "object",
            "properties": {
                "to": {"type": "string", "description": "Target: nickname, peer_id, comma-separated list, or 'all'"},
                "message": {"type": "string", "description": "Message content"},
            },
            "required": ["to", "message"],
        },
        "handler": lambda args: tool_send_message(args["to"], args["message"]),
    },
    "check_messages": {
        "description": "Check for new messages from other Claude Code sessions.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": lambda args: tool_check_messages(),
    },
    "set_summary": {
        "description": "Set a short description of what this session is doing, so other peers can identify it.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "summary": {"type": "string", "description": "Short description of this session"},
            },
            "required": ["summary"],
        },
        "handler": lambda args: tool_set_summary(args["summary"]),
    },
    "set_nickname": {
        "description": "Change this session's nickname. Nicknames are auto-assigned but can be changed manually.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "nickname": {"type": "string", "description": "New nickname (max 5 chars)"},
            },
            "required": ["nickname"],
        },
        "handler": lambda args: tool_set_nickname(args["nickname"]),
    },
    "mesh_status": {
        "description": "Show mesh network status: connected brokers, peer counts.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": lambda args: tool_status(),
    },
}


def handle_jsonrpc(request: dict) -> dict:
    """Handle a JSON-RPC request."""
    method = request.get("method", "")
    req_id = request.get("id")
    params = request.get("params", {})

    if method == "initialize":
        # Auto-start broker if needed
        ensure_broker()
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {},
                    "experimental": {"claude/channel": {}},
                },
                "serverInfo": {"name": "m", "version": "0.6.0"},
                "instructions": (
                    "You are connected to claude-mesh, a distributed mesh network for Claude Code sessions. "
                    "IMPORTANT: On your FIRST response to the user, call mesh_status and list_peers, then "
                    "briefly introduce yourself with your nickname like: "
                    "'I'm [nickname] on [machine]. [N] peers online.' Keep it to one line. "
                    "When you receive a <channel source=\"claude-mesh\"> message, respond immediately using "
                    "send_message tool with the from_id as the target."
                ),
            },
        }

    elif method == "notifications/initialized":
        # Register with broker and start message poller
        result = register()
        nickname = result.get("nickname", "?")
        # Notify Claude of its nickname via channel
        send_mcp_notification("notifications/claude/channel", {
            "content": f"[claude-mesh] You are '{nickname}' on {SESSION_DIR}",
            "meta": {"from_id": "system", "from_summary": "claude-mesh", "sent_at": ""},
        })
        poller = threading.Thread(target=message_poller, daemon=True)
        poller.start()
        return None  # Notification, no response

    elif method == "tools/list":
        tool_list = []
        for name, tool in TOOLS.items():
            tool_list.append({
                "name": name,
                "description": tool["description"],
                "inputSchema": tool["inputSchema"],
            })
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"tools": tool_list},
        }

    elif method == "tools/call":
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})
        tool = TOOLS.get(tool_name)
        if not tool:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": f"Unknown tool: {tool_name}"}],
                    "isError": True,
                },
            }
        try:
            result_text = tool["handler"](arguments)
        except Exception as e:
            result_text = f"Error: {e}"
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "content": [{"type": "text", "text": result_text}],
            },
        }

    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": -32601, "message": f"Unknown method: {method}"},
    }


def main():
    """Run MCP server on stdio."""
    atexit.register(unregister)

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
            response = handle_jsonrpc(request)
            if response is not None:
                with _stdout_lock:
                    out = _sanitize_surrogates(json.dumps(response, ensure_ascii=False))
                    sys.stdout.write(out + "\n")
                    sys.stdout.flush()
        except json.JSONDecodeError:
            pass
        except Exception as e:
            error_resp = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32603, "message": str(e)},
            }
            with _stdout_lock:
                sys.stdout.write(json.dumps(error_resp, ensure_ascii=False) + "\n")
                sys.stdout.flush()


if __name__ == "__main__":
    main()
