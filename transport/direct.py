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
                 known_peers: dict[str, str] | None = None, auth_key: str = ""):
        self.machine_id = machine_id
        self.listen_port = listen_port
        self.known_peers = known_peers or {}  # {"home-pc": "100.83.52.116:7900"}
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

        # Connect to known peers (only if we are the smaller machine_id = client role)
        for peer_id, addr in self.known_peers.items():
            if self.machine_id < peer_id:
                logger.info(f"Will connect to {peer_id} at {addr} (we are client)")
                task = asyncio.create_task(self._connect_to_peer(peer_id, addr))
                self._connect_tasks.append(task)
            else:
                logger.info(f"Waiting for {peer_id} to connect to us (they are client)")

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
            logger.warning(f"No connection to {machine_id}, available: {list(self._connections.keys())}")
            return False
        if ws.close_code is not None:
            logger.warning(f"Connection to {machine_id} is closed, removing")
            self._connections.pop(machine_id, None)
            return False
        try:
            data = json.dumps(message, ensure_ascii=False)
            await ws.send(data)
            logger.info(f"Sent {len(data)} bytes to {machine_id}")
            return True
        except Exception as e:
            logger.error(f"Send to {machine_id} failed: {e}")
            self._connections.pop(machine_id, None)
            return False

    async def broadcast(self, message: dict):
        data = json.dumps(message, ensure_ascii=False)
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
                        try:
                            await cb(remote_id, data)
                        except Exception as e:
                            logger.error(f"Callback error for {remote_id}: {e}")
                except json.JSONDecodeError:
                    pass
                except Exception as e:
                    logger.error(f"Message processing error from {remote_id}: {e}")
        except (asyncio.TimeoutError, websockets.exceptions.ConnectionClosed) as e:
            logger.info(f"Connection to {remote_id} ended: {e}")
        finally:
            if remote_id:
                self._connections.pop(remote_id, None)
                logger.info(f"Connection from {remote_id} closed")

    async def _connect_to_peer(self, peer_id: str, address: str):
        """Maintain a persistent outgoing connection to a known peer.

        Only called when we are the smaller machine_id (client role).
        """
        while True:
            # Skip if already connected
            if peer_id in self._connections and not self._connections[peer_id].closed:
                await asyncio.sleep(10)
                continue

            try:
                uri = f"ws://{address}"
                async with websockets.connect(
                    uri, ping_interval=60, ping_timeout=30,
                ) as ws:
                    await ws.send(json.dumps({
                        "type": "hello",
                        "machine_id": self.machine_id,
                        "auth_key": self.auth_key,
                    }))

                    raw = await asyncio.wait_for(ws.recv(), timeout=10)
                    msg = json.loads(raw)
                    if msg.get("type") != "hello_ack":
                        logger.warning(f"Unexpected ack from {address}: {msg}")
                        await asyncio.sleep(5)
                        continue

                    remote_id = msg["machine_id"]
                    logger.info(f"Connected to {remote_id} at {address}")
                    self._connections[remote_id] = ws

                    async for raw in ws:
                        try:
                            data = json.loads(raw)
                            for cb in self._callbacks:
                                try:
                                    await cb(remote_id, data)
                                except Exception as e:
                                    logger.error(f"Callback error for {remote_id}: {e}")
                        except json.JSONDecodeError:
                            pass
                        except Exception as e:
                            logger.error(f"Message processing error from {remote_id}: {e}")

            except (ConnectionRefusedError, OSError, websockets.exceptions.ConnectionClosed) as e:
                logger.info(f"Connection to {address} lost: {e}")
            except asyncio.CancelledError:
                return

            await asyncio.sleep(5)
