# claude-mesh

リモートマシン間で複数のClaude Codeセッションが相互に発見・通信できる分散メッシュネットワーク。

## 背景

[claude-peers-mcp](https://github.com/louislva/claude-peers-mcp) は同一マシン内のClaude Codeセッション間通信を実現するMCPサーバー。本プロジェクトはこれをリモートマシン間に拡張し、任意のClaude同士がネットワーク越しに対等に通信できる仕組みを構築する。

参考記事: [Claude Code同士が会話できるようになったらしいので試してみた（Zenn）](https://zenn.dev/acntechjp/articles/7bb9f418be6e68)

## 前身プロジェクト

[claude-pty-bridge](https://github.com/ken12313451/claude-pty-bridge) で、PTY常駐Claude + WebSocket中継 + ファイルベースリレーによるリモートClaude間通信を実現済み。ただしこれは特定のLC↔RCの1対1通信に限定されていた。claude-meshはこれをN対Nに拡張する。

## アーキテクチャ

```
Machine A                              Machine B
┌────────────────────────┐            ┌────────────────────────┐
│ Claude ─ MCP Server ─┐ │            │ Claude ─ MCP Server ─┐ │
│ Claude ─ MCP Server ─┤ │            │ Claude ─ MCP Server ─┤ │
│                       ▼ │            │                       ▼ │
│              Mesh Broker │            │              Mesh Broker │
│              (port 7900) │            │              (port 7900) │
│                 │        │            │                 │        │
│           ┌─────┴─────┐  │            │           ┌─────┴─────┐  │
│           │ Transport │  │            │           │ Transport │  │
│           └─────┬─────┘  │            └─────────────────┼────────┘
└─────────────────┼────────┘                              │
                  │                                       │
                  └───────── Network (何でもよい) ─────────┘
```

### 設計思想

- **Peer-to-Peer**: 中央サーバーなし。各マシンのbrokerが対等に相互接続
- **Transport抽象化**: 通信層を差し替え可能（Tailscale直接接続 / クラウドリレー / ngrok等）
- **MCP準拠**: Claude Codeの標準MCP機構でシームレスに統合

## コンポーネント構成

```
claude-mesh/
├── broker.py          # Mesh Broker本体（各マシンで1つ常駐）
├── transport/
│   ├── base.py        # Transport抽象インターフェース
│   ├── direct.py      # Tailscale/LAN直接接続
│   └── relay.py       # クラウドリレー経由
├── mcp_server.py      # MCP Server（Claude Codeとの接続点）
├── registry.py        # Peer Registry（SQLite）
├── config.py          # 設定管理
└── mesh.json          # 設定ファイル
```

### 各コンポーネントの役割

| コンポーネント | 役割 |
|--------------|------|
| **MCP Server** | Claude Codeセッションごとに起動。list_peers / send_message / check_messages 等のツールを提供 |
| **Mesh Broker** | 各マシンで1つ常駐。ローカルpeer管理 + リモートbrokerとのpeer同期・メッセージルーティング |
| **Transport** | broker間通信の抽象層。DirectTransport（Tailscale/LAN）またはRelayTransport（クラウド経由） |
| **Registry** | SQLiteでpeer情報とメッセージを管理。ローカル/リモートの区別あり |

## Transport層（通信の抽象化）

```python
class Transport(ABC):
    @abstractmethod
    async def start(self):
        """リッスン開始"""

    @abstractmethod
    async def connect(self, peer_address: str):
        """リモートbrokerに接続"""

    @abstractmethod
    async def send(self, peer_id: str, message: dict):
        """メッセージ送信"""

    @abstractmethod
    async def on_message(self, callback):
        """メッセージ受信コールバック登録"""

    @abstractmethod
    async def broadcast(self, message: dict):
        """全接続先に送信"""
```

### DirectTransport

Tailscale/LAN等で直接WebSocket接続。known_peersリストに接続先を記述。

### RelayTransport

クラウドリレーサーバー経由。NAT越えが必要な環境向け。全brokerがリレーサーバーにアウトバウンド接続するため、ポート開放不要。

## Peer Registry

```sql
-- peers テーブル
CREATE TABLE peers (
    peer_id TEXT PRIMARY KEY,
    machine_id TEXT,
    machine_name TEXT,
    session_dir TEXT,
    summary TEXT,
    is_local BOOLEAN,
    last_seen TIMESTAMP,
    status TEXT  -- online / offline
);

-- messages テーブル
CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_peer TEXT,
    to_peer TEXT,
    content TEXT,
    timestamp TIMESTAMP,
    read BOOLEAN DEFAULT 0
);
```

## MCP ツール

| ツール | 引数 | 説明 |
|--------|------|------|
| list_peers | scope: local/remote/all | 利用可能なpeerを一覧表示 |
| send_message | to, message | 指定peerにメッセージ送信（ローカル/リモート問わず） |
| check_messages | — | 自分宛の未読メッセージを取得 |
| set_summary | summary | 自セッションの概要を設定 |

## メッセージフロー

```
Claude@A14 → "Home-PCのRCにレビュー依頼"

1. Claude@A14 → MCP: send_message(to="home-pc:RC", message="...")
2. MCP Server → HTTP → Mesh Broker@A14 (localhost:7901)
3. Broker@A14 → Registry: to先はmachine_id="home-pc"
4. Broker@A14 → Transport.send("home-pc", message)
5.   [WebSocket: A14 → Home-PC (Tailscale経由)]
6. Broker@Home-PC → Registry.store_message
7. Claude@Home-PC → MCP: check_messages() → メッセージ受信
```

## 設定ファイル

```json
{
    "machine_id": "home-pc",
    "machine_name": "Home PC",
    "transport": "direct",
    "mesh_port": 7900,
    "known_peers": [
        "100.109.107.51:7900"
    ],
    "auth_key": "shared-secret-key"
}
```

## 実装ステップ

| Step | 内容 | 状態 |
|------|------|------|
| 1 | Transport抽象 + DirectTransport | 未着手 |
| 2 | PeerRegistry (SQLite) | 未着手 |
| 3 | Mesh Broker (ローカルAPI + peer同期) | 未着手 |
| 4 | MCP Server (stdio) | 未着手 |
| 5 | 2台で動作テスト | 未着手 |
| 6 | RelayTransport追加 | 未着手 |

## claude-peers-mcp との違い

| | claude-peers-mcp | claude-mesh |
|---|---|---|
| 通信範囲 | 同一マシン内 | リモートマシン間 |
| トポロジ | Star型（broker中心） | P2P（broker同士が対等接続） |
| Transport | HTTP (localhost) | WebSocket（差し替え可能） |
| peer発見 | ローカルbrokerのみ | リモートbrokerとpeer同期 |

## 技術スタック

- Python 3.13+
- websockets（broker間通信）
- SQLite（peer/message管理）
- MCP SDK（Claude Code連携）

## 動作環境

- Windows 10/11, macOS, Linux
- Tailscale推奨（NAT越え不要の場合はLAN直接も可）
