"""Configuration management for claude-mesh."""

import json
import uuid
from pathlib import Path


DEFAULT_CONFIG_PATH = Path.home() / ".claude-mesh.json"


class MeshConfig:
    def __init__(self, config_path=None):
        self.path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
        self._data = self._load()

    def _load(self):
        if self.path.exists():
            return json.loads(self.path.read_text(encoding="utf-8"))
        # Generate default config
        return {
            "machine_id": str(uuid.uuid4())[:8],
            "machine_name": "",
            "transport": "direct",
            "mesh_port": 7900,
            "local_api_port": 7901,
            "known_peers": [],
            "auth_key": "",
        }

    def save(self):
        self.path.write_text(
            json.dumps(self._data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    @property
    def machine_id(self) -> str:
        return self._data["machine_id"]

    @property
    def machine_name(self) -> str:
        return self._data.get("machine_name", self.machine_id)

    @property
    def transport(self) -> str:
        return self._data.get("transport", "direct")

    @property
    def mesh_port(self) -> int:
        return self._data.get("mesh_port", 7900)

    @property
    def local_api_port(self) -> int:
        return self._data.get("local_api_port", 7901)

    @property
    def known_peers(self) -> dict[str, str]:
        """Return known peers as {machine_id: address}.

        Supports both formats:
        - New: {"home-pc": "100.83.52.116:7900"}
        - Legacy: ["100.83.52.116:7900"] (treated as unknown machine_id)
        """
        raw = self._data.get("known_peers", {})
        if isinstance(raw, list):
            return {f"unknown-{i}": addr for i, addr in enumerate(raw)}
        return raw

    @property
    def auth_key(self) -> str:
        return self._data.get("auth_key", "")
