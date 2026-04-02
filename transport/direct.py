"""Direct WebSocket transport for broker-to-broker communication."""

import asyncio
import json
import logging
from typing import Any, Callable

import websockets

from .base import Transport

logger = logging.getLogger("claude-mesh.transport")


class DirectTransport(Transport):
    """Broker-to-broker communication via direct WebSocket connections.

    Each broker both listens (server) and connects to known peers (client).
    Suitable for Tailscale, LAN, or any environment with direct IP reachability.
    """

    def __init__(self, machine_id: str, listen_port: int = 7900,
                 known_peers: list[str] | None = None, auth_key: str = ""):
        self.machine_id = machine_id
        self.listen_port = listen_port
        self.known_peers = known_peers or []  # ["100.83.52.116:7900", ...]
        self.auth_key = auth_key
        self._connections: dict[str, websockets.WebSocketServerProtocol] = {}
        self._callbacks: list[Callable] = []
        self._server = None
        self._connect_tasks: list[asyncio.Task] = []

    def on_message(self, callback: Callable[[str, dict], Any]):
        self._callbacks.append(callback)

    def connected_peers(self) -> list[str]:
        return list(self._connections.keys())

    async def start(self):
        # Start WebSocket server
        self._server = await websockets.serve(
            self._handle_incoming, "0.0.0.0", self.listen_port,
            ping_interval=60, ping_timeout=30,
        )
        logger.info(f"Transport listening on port {self.listen_port}")

        # Connect to known peers
        for addr in self.known_peers:
            task = asyncio.create_task(self._connect_to_peer(addr))
            self._connect_tasks.append(task)

    async def stop(self):
        for task in self._connect_tasks:
            task.cancel()
        for ws in self._connections.values():
            await ws.close()
        if self._server:
            self._server.close()
            await self._server.wait_closed()

    async def send(self, machine_id: str, message: dict):
        ws = self._connections.get(machine_id)
        if not ws:
            logger.warning(f"No connection to {machine_id}")
            return False
        try:
            await ws.send(json.dumps(message))
            return True
        except Exception as e:
            logger.error(f"Send to {machine_id} failed: {e}")
            self._connections.pop(machine_id, None)
            return False

    async def broadcast(self, message: dict):
        data = json.dumps(message)
        dead = []
        for mid, ws in self._connections.items():
            try:
                await ws.send(data)
            except Exception:
                dead.append(mid)
        for mid in dead:
            self._connections.pop(mid, None)

    # --- Internal ---

    async def _handle_incoming(self, websocket):
        """Handle a new incoming connection from a remote broker."""
        remote_id = None
        try:
            # Expect auth + identify message first
            raw = await asyncio.wait_for(websocket.recv(), timeout=10)
            msg = json.loads(raw)
            if msg.get("type") != "hello" or msg.get("auth_key") != self.auth_key:
                await websocket.close(1008, "Auth failed")
                return
            remote_id = msg["machine_id"]

            # Reject if already connected (avoid dual connections)
            if remote_id in self._connections:
                logger.info(f"Already connected to {remote_id}, rejecting incoming")
                await websocket.close(1000, "Already connected")
                return

            logger.info(f"Incoming connection from {remote_id}")

            # Send our hello back
            await websocket.send(json.dumps({
                "type": "hello_ack",
                "machine_id": self.machine_id,
            }))

            self._connections[remote_id] = websocket

            async for raw in websocket:
                try:
                    data = json.loads(raw)
                    for cb in self._callbacks:
                        await cb(remote_id, data)
                except json.JSONDecodeError:
                    pass
        except (asyncio.TimeoutError, websockets.exceptions.ConnectionClosed):
            pass
        finally:
            if remote_id:
                self._connections.pop(remote_id, None)
                logger.info(f"Connection from {remote_id} closed")

    async def _connect_to_peer(self, address: str):
        """Maintain a persistent connection to a known peer."""
        while True:
            # If already connected via incoming, wait and check periodically
            connected_ids = [mid for mid, ws in self._connections.items()
                            if not ws.closed]
            if connected_ids:
                await asyncio.sleep(10)
                continue

            try:
                uri = f"ws://{address}"
                async with websockets.connect(
                    uri, ping_interval=60, ping_timeout=30,
                ) as ws:
                    # Send hello
                    await ws.send(json.dumps({
                        "type": "hello",
                        "machine_id": self.machine_id,
                        "auth_key": self.auth_key,
                    }))

                    # Wait for ack
                    raw = await asyncio.wait_for(ws.recv(), timeout=10)
                    msg = json.loads(raw)
                    if msg.get("type") != "hello_ack":
                        logger.warning(f"Unexpected ack from {address}: {msg}")
                        continue

                    remote_id = msg["machine_id"]

                    # If incoming connection appeared while we were connecting
                    if remote_id in self._connections:
                        logger.info(f"Already connected to {remote_id}, closing outgoing")
                        continue

                    logger.info(f"Connected to {remote_id} at {address}")
                    self._connections[remote_id] = ws

                    async for raw in ws:
                        try:
                            data = json.loads(raw)
                            for cb in self._callbacks:
                                await cb(remote_id, data)
                        except json.JSONDecodeError:
                            pass

            except (ConnectionRefusedError, OSError, websockets.exceptions.ConnectionClosed) as e:
                logger.debug(f"Connection to {address} failed: {e}")
            except asyncio.CancelledError:
                return

            # Reconnect after delay
            await asyncio.sleep(5)
