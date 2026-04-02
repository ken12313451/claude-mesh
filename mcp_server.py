"""MCP Server for claude-mesh.

Each Claude Code session runs this as an MCP server (stdio transport).
Communicates with the local Mesh Broker via HTTP on localhost:7901.
"""

import asyncio
import json
import os
import sys
import uuid
from http.client import HTTPConnection
from pathlib import Path


# Broker API endpoint
BROKER_HOST = "127.0.0.1"
BROKER_PORT = int(os.environ.get("CLAUDE_MESH_BROKER_PORT", "7901"))

# This session's identity
PEER_ID = str(uuid.uuid4())
SESSION_DIR = os.getcwd()


def broker_request(method: str, path: str, body: dict | None = None) -> dict:
    """Make a request to the local Mesh Broker API."""
    conn = HTTPConnection(BROKER_HOST, BROKER_PORT, timeout=5)
    try:
        if body is not None:
            data = json.dumps(body).encode()
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


def register():
    """Register this session with the broker."""
    return broker_request("POST", "/register", {
        "peer_id": PEER_ID,
        "session_dir": SESSION_DIR,
        "summary": "",
    })


def unregister():
    """Unregister this session."""
    return broker_request("POST", "/unregister", {"peer_id": PEER_ID})


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
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "claude-mesh", "version": "0.1.0"},
            },
        }

    elif method == "notifications/initialized":
        # Register with broker on init
        register()
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
    import atexit
    atexit.register(unregister)

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
            response = handle_jsonrpc(request)
            if response is not None:
                sys.stdout.write(json.dumps(response) + "\n")
                sys.stdout.flush()
        except json.JSONDecodeError:
            pass
        except Exception as e:
            error_resp = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32603, "message": str(e)},
            }
            sys.stdout.write(json.dumps(error_resp) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
