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
from http.client import HTTPConnection
from pathlib import Path


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


def broker_request(method: str, path: str, body: dict | None = None) -> dict:
    """Make a request to the local Mesh Broker API."""
    conn = HTTPConnection(BROKER_HOST, BROKER_PORT, timeout=5)
    try:
        if body is not None:
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
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
    """Register this session with the broker."""
    return broker_request("POST", "/register", {
        "peer_id": PEER_ID,
        "session_dir": SESSION_DIR,
        "summary": "",
    })


def unregister():
    """Unregister this session."""
    broker_request("POST", "/unregister", {"peer_id": PEER_ID})


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
                    send_mcp_notification("notifications/claude/channel", {
                        "content": m["content"],
                        "meta": {
                            "from_id": m["from_peer"],
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
        summary = p.get("summary", "") or "(no summary)"
        status = p.get("status", "?")
        lines.append(f"- [{status}] {summary} @ {location} (id: {p['peer_id'][:8]})")
    return "\n".join(lines)


def tool_send_message(to: str, message: str) -> str:
    result = broker_request("POST", "/send", {
        "from": PEER_ID,
        "to": to,
        "content": message,
    })
    if result.get("status") == "ok":
        return f"Message sent to {result.get('delivered_to', to)}"
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


def tool_status() -> str:
    result = broker_request("GET", "/status")
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
        "description": "Send a message to another Claude Code session. Use peer_id, summary text, or machine:summary pattern.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "to": {"type": "string", "description": "Target peer identifier"},
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
                "serverInfo": {"name": "claude-mesh", "version": "0.3.0"},
                "instructions": (
                    "You are connected to claude-mesh, a distributed mesh network for Claude Code sessions. "
                    "When you receive a <channel source=\"claude-mesh\"> message, respond immediately using "
                    "send_message tool with the from_id as the target. "
                    "On startup, call set_summary to identify yourself to other peers."
                ),
            },
        }

    elif method == "notifications/initialized":
        # Register with broker and start message poller
        register()
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
                    sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
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
