"""Mesh Broker — central coordinator on each machine.

Manages local peer registry, syncs with remote brokers via Transport,
and exposes a local HTTP API for MCP servers to interact with.
"""

import asyncio
import json
import logging
import os
import sys

# Ensure UTF-8 for all I/O on Windows
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stderr.encoding != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8")

from config import MeshConfig
from registry import PeerRegistry
from transport.direct import DirectTransport

logger = logging.getLogger("claude-mesh.broker")


class MeshBroker:
    def __init__(self, config: MeshConfig):
        self.config = config
        self.registry = PeerRegistry()
        self.transport = DirectTransport(
            machine_id=config.machine_id,
            listen_port=config.mesh_port,
            known_peers=config.known_peers,
            auth_key=config.auth_key,
        )
        self.transport.on_message(self._handle_remote_message)

    async def start(self):
        logger.info(f"Starting Mesh Broker: {self.config.machine_name} ({self.config.machine_id})")

        # Start transport (broker-to-broker)
        await self.transport.start()

        # Start local HTTP API (MCP servers talk to this)
        api_server = await asyncio.start_server(
            self._handle_local_api,
            "127.0.0.1", self.config.local_api_port,
        )
        logger.info(f"Local API on http://127.0.0.1:{self.config.local_api_port}")

        # Start peer sync loop
        asyncio.create_task(self._sync_loop())

        # Run until cancelled
        async with api_server:
            await api_server.serve_forever()

    # --- Remote broker communication ---

    async def _sync_loop(self):
        """Periodically broadcast local peer info and clean up stale peers."""
        while True:
            try:
                # Clean up stale peers first
                self.registry.cleanup_stale_peers()

                local_peers = self.registry.get_local_peers_for_sync()
                await self.transport.broadcast({
                    "type": "peer_sync",
                    "machine_id": self.config.machine_id,
                    "machine_name": self.config.machine_name,
                    "peers": local_peers,
                })
            except Exception as e:
                logger.error(f"Sync error: {e}")
            await asyncio.sleep(30)

    async def _handle_remote_message(self, from_machine: str, message: dict):
        msg_type = message.get("type")

        if msg_type == "peer_sync":
            self.registry.update_remote_peers(
                message["machine_id"],
                message.get("machine_name", ""),
                message.get("peers", []),
            )
            logger.info(
                f"Synced {len(message.get('peers', []))} peers from {message.get('machine_name', from_machine)}"
            )

        elif msg_type == "message":
            self.registry.store_message(
                message["from"], message["to"], message["content"],
            )
            logger.info(f"Message from {message['from']} to {message['to']}")

        elif msg_type == "message_remote":
            # A message destined for a local peer, forwarded by a remote broker
            self.registry.store_message(
                message["from"], message["to"], message["content"],
            )
            logger.info(f"Remote message received: {message['from']} -> {message['to']}")

    # --- Local HTTP API (simple line-based protocol) ---

    async def _handle_local_api(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """Simple HTTP-like API for MCP servers."""
        try:
            request_line = await asyncio.wait_for(reader.readline(), timeout=5)
            if not request_line:
                writer.close()
                return

            request = request_line.decode().strip()

            # Read headers
            content_length = 0
            while True:
                line = await reader.readline()
                if line == b"\r\n" or line == b"\n" or not line:
                    break
                if line.lower().startswith(b"content-length:"):
                    content_length = int(line.split(b":")[1].strip())

            # Read body
            body = None
            if content_length > 0:
                body = await reader.read(content_length)
                body = json.loads(body.decode())

            # Route
            method, path, *_ = request.split(" ")
            response = await self._route(method, path, body)

            # Send response
            response_body = json.dumps(response, ensure_ascii=False).encode()
            writer.write(b"HTTP/1.1 200 OK\r\n")
            writer.write(b"Content-Type: application/json\r\n")
            writer.write(f"Content-Length: {len(response_body)}\r\n".encode())
            writer.write(b"\r\n")
            writer.write(response_body)
            await writer.drain()

        except Exception as e:
            logger.error(f"API error: {e}")
        finally:
            writer.close()

    async def _route(self, method: str, path: str, body: dict | None) -> dict:
        if method == "POST" and path == "/register":
            nickname = self.registry.register(
                peer_id=body["peer_id"],
                machine_id=self.config.machine_id,
                machine_name=self.config.machine_name,
                session_dir=body.get("session_dir", ""),
                summary=body.get("summary", ""),
            )
            return {"status": "ok", "nickname": nickname}

        elif method == "POST" and path == "/unregister":
            self.registry.unregister(body["peer_id"])
            return {"status": "ok"}

        elif method == "POST" and path in ("/summary", "/set_summary"):
            self.registry.set_summary(body["peer_id"], body["summary"])
            return {"status": "ok"}

        elif method == "POST" and path == "/nickname":
            self.registry.set_nickname(body["peer_id"], body["nickname"])
            return {"status": "ok"}

        elif method == "POST" and path == "/heartbeat":
            self.registry.heartbeat(
                body["peer_id"],
                machine_id=self.config.machine_id,
                machine_name=self.config.machine_name,
                session_dir=body.get("session_dir", ""),
            )
            return {"status": "ok"}

        elif method == "GET" and path.startswith("/peers"):
            # Parse scope from query: /peers?scope=all
            scope = "all"
            if "?" in path:
                params = dict(p.split("=") for p in path.split("?")[1].split("&") if "=" in p)
                scope = params.get("scope", "all")
            peers = self.registry.list_peers(scope)
            return {"peers": peers}

        elif method == "POST" and path == "/send":
            from_peer = body["from"]
            to_query = body["to"]
            content = body["content"]

            target = self.registry.find_peer(to_query)
            if not target:
                return {"status": "error", "message": f"Peer not found: {to_query}"}

            if target["is_local"]:
                # Local delivery
                self.registry.store_message(from_peer, target["peer_id"], content)
            else:
                # Remote delivery via transport
                sent = await self.transport.send(target["machine_id"], {
                    "type": "message_remote",
                    "from": from_peer,
                    "to": target["peer_id"],
                    "content": content,
                })
                if not sent:
                    return {"status": "error", "message": f"Failed to send to remote broker {target['machine_id']}"}

            return {"status": "ok", "delivered_to": target["peer_id"]}

        elif method == "GET" and path.startswith("/messages"):
            # /messages?peer_id=xxx&mark_read=true (default: true)
            params = {}
            if "?" in path:
                params = dict(p.split("=") for p in path.split("?")[1].split("&") if "=" in p)
            peer_id = params.get("peer_id", "")
            mark_read = params.get("mark_read", "true").lower() != "false"
            messages = self.registry.get_messages(peer_id)
            if mark_read:
                msg_ids = [m["id"] for m in messages]
                self.registry.mark_read(msg_ids)
            return {"messages": messages}

        elif method == "GET" and path == "/status":
            return {
                "machine_id": self.config.machine_id,
                "machine_name": self.config.machine_name,
                "local_peers": len(self.registry.list_peers("local")),
                "remote_peers": len(self.registry.list_peers("remote")),
                "connected_brokers": self.transport.connected_peers(),
            }

        return {"status": "error", "message": f"Unknown route: {method} {path}"}


def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )


async def main():
    setup_logging()
    config = MeshConfig()

    if not config.path.exists():
        config.save()
        logger.info(f"Created default config at {config.path}")
        logger.info("Edit machine_name, known_peers, and auth_key, then restart.")
        return

    broker = MeshBroker(config)
    try:
        await broker.start()
    except KeyboardInterrupt:
        logger.info("Shutting down")
    finally:
        await broker.transport.stop()
        broker.registry.close()


if __name__ == "__main__":
    asyncio.run(main())
