#!/usr/bin/env python3
"""claude-mesh setup and management CLI.

Subcommands:
  init       Interactive setup wizard. Generates ~/.claude-mesh.json.
  install    Register the MCP server with Claude Code and install statusline.
  status     Show current configuration and live broker/peer state.

Run `python cli.py <subcommand>` from the repository root.
"""
import argparse
import json
import os
import re
import secrets
import socket
import subprocess
import sys
import time
from http.client import HTTPConnection
from pathlib import Path


# --- Paths -------------------------------------------------------------------

REPO_ROOT = Path(__file__).parent.resolve()
MCP_SERVER = REPO_ROOT / "src" / "mcp_server.py"
CONFIG_PATH = Path.home() / ".claude-mesh.json"
STATUSLINE_PATH = Path.home() / ".claude" / "statusline.js"
SETTINGS_PATH = Path.home() / ".claude" / "settings.json"
BASHRC_PATH = Path.home() / ".bashrc"


# --- Tiny ANSI helpers -------------------------------------------------------

class C:
    R = "\x1b[0m"
    DIM = "\x1b[2m"
    BOLD = "\x1b[1m"
    GREEN = "\x1b[32m"
    YELLOW = "\x1b[33m"
    RED = "\x1b[31m"
    CYAN = "\x1b[36m"


def info(msg): print(f"{C.CYAN}{msg}{C.R}")
def ok(msg):   print(f"{C.GREEN}OK{C.R} {msg}")
def warn(msg): print(f"{C.YELLOW}!{C.R}  {msg}")
def err(msg):  print(f"{C.RED}x{C.R}  {msg}", file=sys.stderr)
def dim(msg):  print(f"{C.DIM}{msg}{C.R}")


# --- Statusline template (kept in sync with ~/.claude/statusline.js) ---------

STATUSLINE_JS = r'''#!/usr/bin/env node
const fs = require('fs');
const path = require('path');
let input = '';
process.stdin.on('data', chunk => input += chunk);
process.stdin.on('end', () => {
    const data = JSON.parse(input);
    const pct = Math.floor(data.context_window?.used_percentage || 0);

    // Try to read claude-mesh nickname
    let nick = '';
    try {
        const nickFile = path.join(process.env.HOME || process.env.USERPROFILE, '.claude-mesh-nick');
        const nicks = JSON.parse(fs.readFileSync(nickFile, 'utf-8'));
        const sessionId = data.session_id || '';

        // Match by session_id (set after first MCP tool call)
        if (sessionId) {
            for (const [pid, entry] of Object.entries(nicks)) {
                if (typeof entry === 'object' && entry.session_id === sessionId) {
                    nick = entry.nickname || '';
                    break;
                }
            }
        }
    } catch (e) {}

    if (nick) {
        // Rainbow colors for nickname
        const colors = [196, 208, 226, 46, 51, 129]; // red, orange, yellow, green, cyan, purple
        let rainbow = '';
        for (let i = 0; i < nick.length; i++) {
            const c = colors[i % colors.length];
            rainbow += `\x1b[38;5;${c}m${nick[i]}`;
        }
        rainbow += '\x1b[0m';
        console.log(`${rainbow} | context: ${pct}%`);
    } else {
        console.log(`---- | context: ${pct}%`);
    }
});
'''


# --- Config I/O --------------------------------------------------------------

def read_config():
    if not CONFIG_PATH.exists():
        return None
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def write_config(cfg):
    CONFIG_PATH.write_text(
        json.dumps(cfg, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


# --- Helpers -----------------------------------------------------------------

def suggest_machine_id():
    h = socket.gethostname().lower()
    m = re.match(r"[a-z0-9]+", h)
    return m.group(0) if m else "host"


def suggest_machine_name():
    return socket.gethostname()


def generate_auth_key():
    return secrets.token_urlsafe(32)


def port_available(port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        s.close()


def find_free_port(start, span=100):
    for p in range(start, start + span):
        if port_available(p):
            return p
    return start


def prompt(msg, default=""):
    full = f"{msg} [{default}]: " if default else f"{msg}: "
    try:
        ans = input(full).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        sys.exit(1)
    return ans or default


def confirm(msg, default=True):
    suffix = "[Y/n]" if default else "[y/N]"
    while True:
        try:
            ans = input(f"{msg} {suffix}: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            sys.exit(1)
        if not ans:
            return default
        if ans in ("y", "yes"):
            return True
        if ans in ("n", "no"):
            return False


def has_dev_channel_in_bashrc():
    """Detect ken1i's developer dogfooding setup so install does not double-register."""
    if not BASHRC_PATH.exists():
        return False
    try:
        content = BASHRC_PATH.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    return ("--dangerously-load-development-channels" in content
            and "claude-mesh" in content)


# --- init --------------------------------------------------------------------

def cmd_init(_args):
    print()
    info("=== claude-mesh init ===")
    print()
    print("This wizard will create your claude-mesh configuration.")
    print()

    existing = read_config()
    if existing:
        warn(f"Existing config found at {CONFIG_PATH}")
        choice = prompt("(u)pdate, (o)verwrite, or (a)bort?", "u").lower()
        if choice.startswith("a"):
            print("Aborted.")
            return
        if choice.startswith("o"):
            existing = None

    defaults = existing or {}

    machine_id = prompt(
        "Machine ID (short, alphanumeric, unique across mesh)",
        defaults.get("machine_id") or suggest_machine_id(),
    )
    machine_name = prompt(
        "Machine name (display)",
        defaults.get("machine_name") or suggest_machine_name(),
    )

    # Mesh port
    default_mesh = defaults.get("mesh_port", 7900)
    if not port_available(default_mesh) and not (existing and existing.get("mesh_port") == default_mesh):
        new_port = find_free_port(default_mesh + 1)
        warn(f"Port {default_mesh} is in use. Suggesting {new_port}.")
        mesh_port = int(prompt("Mesh port", str(new_port)))
    else:
        mesh_port = int(prompt("Mesh port", str(default_mesh)))

    # Local API port
    default_api = defaults.get("local_api_port", 7901)
    if not port_available(default_api) and not (existing and existing.get("local_api_port") == default_api):
        new_port = find_free_port(default_api + 1)
        warn(f"Port {default_api} is in use. Suggesting {new_port}.")
        local_api_port = int(prompt("Local API port", str(new_port)))
    else:
        local_api_port = int(prompt("Local API port", str(default_api)))

    # Auth key
    auth_key = defaults.get("auth_key")
    if not auth_key or auth_key == "mesh-test-key":
        auth_key = generate_auth_key()
        ok(f"Generated new auth_key (first 8 chars: {auth_key[:8]}...)")
    else:
        if not confirm("Keep existing auth_key?", default=True):
            auth_key = generate_auth_key()
            ok(f"Generated new auth_key (first 8 chars: {auth_key[:8]}...)")

    cfg = {
        "machine_id": machine_id,
        "machine_name": machine_name,
        "transport": "direct",
        "mesh_port": mesh_port,
        "local_api_port": local_api_port,
        "known_peers": defaults.get("known_peers", {}),
        "auth_key": auth_key,
    }
    write_config(cfg)
    print()
    ok(f"Wrote {CONFIG_PATH}")
    print()
    print(f"Next: {C.BOLD}python {Path(__file__).name} install{C.R}")
    print()


# --- install -----------------------------------------------------------------

def install_mcp_registration():
    """Register the MCP server with Claude Code (user scope, idempotent-ish)."""
    cmd = [
        "claude", "mcp", "add", "--scope", "user", "claude-mesh",
        "--", sys.executable, str(MCP_SERVER),
    ]
    dim(f"  $ {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except FileNotFoundError:
        warn("`claude` CLI not found in PATH.")
        print("  Install Claude Code first, then run this manually:")
        print(f"    {' '.join(cmd)}")
        return False
    except subprocess.TimeoutExpired:
        warn("MCP registration timed out.")
        print(f"  Run manually: {' '.join(cmd)}")
        return False

    if result.returncode == 0:
        ok("MCP server registered as 'claude-mesh' (user scope).")
        return True

    stderr = (result.stderr or "").strip()
    stdout = (result.stdout or "").strip()
    combined = (stderr + " " + stdout).lower()
    if "already exists" in combined or "already configured" in combined:
        ok("MCP server already registered.")
        return True

    warn(f"MCP registration failed: {stderr or stdout or '(no output)'}")
    print("  Run this command manually if needed:")
    print(f"    {' '.join(cmd)}")
    return False


def install_statusline():
    """Write claude-mesh statusline.js, backing up any pre-existing one."""
    STATUSLINE_PATH.parent.mkdir(parents=True, exist_ok=True)

    if STATUSLINE_PATH.exists():
        existing = STATUSLINE_PATH.read_text(encoding="utf-8", errors="replace")
        if "claude-mesh-nick" in existing:
            ok("Statusline already installed.")
        else:
            backup = STATUSLINE_PATH.with_suffix(f".js.bak.{int(time.time())}")
            STATUSLINE_PATH.rename(backup)
            ok(f"Backed up existing statusline -> {backup.name}")
            STATUSLINE_PATH.write_text(STATUSLINE_JS, encoding="utf-8")
            ok(f"Wrote {STATUSLINE_PATH}")
    else:
        STATUSLINE_PATH.write_text(STATUSLINE_JS, encoding="utf-8")
        ok(f"Wrote {STATUSLINE_PATH}")

    # Make sure settings.json points at it
    if not SETTINGS_PATH.exists():
        warn(f"{SETTINGS_PATH} not found. Add this manually:")
        print('    "statusLine": { "type": "command", "command": "node ~/.claude/statusline.js" }')
        return

    try:
        settings = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        warn(f"Could not parse {SETTINGS_PATH} (may contain comments). Add manually:")
        print('    "statusLine": { "type": "command", "command": "node ~/.claude/statusline.js" }')
        return

    if "statusLine" in settings:
        dim("  statusLine entry already present in settings.json")
        return

    settings["statusLine"] = {
        "type": "command",
        "command": "node ~/.claude/statusline.js",
    }
    SETTINGS_PATH.write_text(
        json.dumps(settings, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    ok("Added statusLine entry to ~/.claude/settings.json")


def cmd_install(_args):
    print()
    info("=== claude-mesh install ===")
    print()

    if not read_config():
        err("No config found. Run init first:")
        print(f"  python {Path(__file__).name} init")
        sys.exit(1)

    if not MCP_SERVER.exists():
        err(f"MCP server not found at {MCP_SERVER}")
        sys.exit(1)

    info("Step 1: MCP registration")
    if has_dev_channel_in_bashrc():
        warn("Detected dev channel in ~/.bashrc")
        warn("  Skipping MCP registration to avoid double-loading the server.")
        warn("  (Both a dev-channel attach and a user-scope MCP would each spawn")
        warn("   the MCP server, giving you two peers per Claude Code session.)")
        warn("  To use the standard registration instead, remove the")
        warn("  --dangerously-load-development-channels line from ~/.bashrc")
        warn("  and re-run install.")
    else:
        install_mcp_registration()

    print()
    info("Step 2: Statusline")
    install_statusline()

    print()
    ok("Install complete.")
    print()
    print(f"  Now launch Claude Code:")
    print(f"    {C.BOLD}claude{C.R}")
    print()
    print(f"  Watch the bottom of your terminal.")
    print(f"  Your Claude is about to receive a name.")
    print()


# --- status ------------------------------------------------------------------

def cmd_status(_args):
    print()
    info("=== claude-mesh status ===")
    print()

    cfg = read_config()
    if not cfg:
        err(f"No config at {CONFIG_PATH}")
        print(f"  Run: python {Path(__file__).name} init")
        return

    print(f"Config:        {CONFIG_PATH}")
    print(f"Machine ID:    {cfg.get('machine_id', '?')}")
    print(f"Machine name:  {cfg.get('machine_name', '?')}")
    print(f"Transport:     {cfg.get('transport', '?')}")
    print(f"Mesh port:     {cfg.get('mesh_port', '?')}")
    print(f"Local API:     {cfg.get('local_api_port', '?')}")
    auth = cfg.get("auth_key", "")
    auth_disp = f"{auth[:8]}..." if len(auth) > 12 else auth
    print(f"Auth key:      {auth_disp}")
    peers = cfg.get("known_peers", {})
    print(f"Known peers:   {len(peers)}")
    for name, addr in peers.items():
        print(f"  - {name}: {addr}")

    print()
    info("Broker:")
    local_port = cfg.get("local_api_port", 7901)
    try:
        conn = HTTPConnection("127.0.0.1", local_port, timeout=2)
        conn.request("GET", "/status")
        resp = conn.getresponse()
        data = json.loads(resp.read().decode())
        ok(f"Running on 127.0.0.1:{local_port}")
        brokers = data.get("connected_brokers") or []
        if brokers:
            print(f"  Connected: {', '.join(brokers)}")
        else:
            dim("  No remote brokers connected")
        conn.close()
    except (ConnectionRefusedError, OSError):
        warn("Not running. Will auto-start when Claude Code launches.")
    except Exception as e:
        warn(f"Could not query broker: {e}")

    print()
    info("Local peers:")
    try:
        conn = HTTPConnection("127.0.0.1", local_port, timeout=2)
        conn.request("GET", "/peers?scope=local")
        resp = conn.getresponse()
        data = json.loads(resp.read().decode())
        peers = data.get("peers", [])
        if not peers:
            dim("  (none)")
        for p in peers:
            nick = p.get("nickname") or "?"
            status = p.get("status", "?")
            session_dir = p.get("session_dir", "")
            print(f"  - {nick} [{status}] {session_dir}")
        conn.close()
    except Exception:
        dim("  (broker unavailable)")

    print()


# --- entry point -------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        prog="cli.py",
        description="claude-mesh setup and management",
    )
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("init", help="Interactive setup wizard")
    sub.add_parser("install", help="Register MCP server and install statusline")
    sub.add_parser("status", help="Show current configuration and broker state")
    args = parser.parse_args()

    if args.cmd == "init":
        cmd_init(args)
    elif args.cmd == "install":
        cmd_install(args)
    elif args.cmd == "status":
        cmd_status(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
