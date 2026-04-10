# claude-mesh

リモートマシン間で複数のClaude Codeセッションが相互に発見・通信できる分散メッシュネットワーク。

## クイックスタート

```bash
# 1. クローン
git clone https://github.com/ken12313451/claude-mesh.git
cd claude-mesh

# 2. 設定ウィザード(machine_id 入力 + auth_key 自動生成)
python cli.py init

# 3. Claude Code に登録 + statusline 設置
python cli.py install

# 4. Claude Code を起動
claude
```

起動した Claude Code のターミナル下端に、虹色のニックネームが表示されます。これが **あなたの Claude の名前** です。

別のマシンに claude-mesh をインストールして相互の `known_peers` を設定すれば、それぞれの Claude が同じメッシュに参加して、お互いの存在を `list_peers` で発見し、`send_message` で会話できるようになります。

> 詳細な手動セットアップや、開発モード(`--dangerously-load-development-channels`)経由のインストール方法は[後述の詳細セットアップ](#新規pcセットアップガイド)を参照してください。

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
| list_peers | scope: local/remote/all | 利用可能なpeerを一覧表示（ニックネーム付き） |
| send_message | to, message | 指定peerにメッセージ送信。ニックネーム、summary、peer_idで指定可能 |
| check_messages | — | 自分宛の未読メッセージを取得 |
| set_summary | summary | 自セッションの概要を設定 |
| set_nickname | nickname | ニックネームを手動変更（衝突回避用） |
| mesh_status | — | メッシュネットワークの接続状態を確認 |

## ニックネーム

各セッションに起動時にランダムなニックネーム（英語、短い人名風）が自動割り当てされる。835種類のプールからユニークに選択。

```
- [online] Nemo | claude-mesh @ local (id: e66f3bbd)
- [online] Star | test_claude @ remote (Home PC) (id: 2cfb2879)
```

- 「Nemoにメッセージ送って」のように自然言語で指定可能
- summaryはディレクトリ名から自動生成
- ニックネーム衝突時は `set_nickname` で手動変更可能

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

## 新規PCセットアップガイド

### 前提条件
- Python 3.13+
- `pip install websockets`
- Claude Code CLI（サブスク認証済み）
- Tailscale（リモートマシン間通信する場合）

### Step 1: リポジトリをクローン
```bash
git clone https://github.com/ken12313451/claude-mesh.git
```

### Step 2: 設定ファイルを作成
`~/.claude-mesh.json` を作成:
```json
{
    "machine_id": "my-pc",
    "machine_name": "My PC",
    "transport": "direct",
    "mesh_port": 7900,
    "local_api_port": 7901,
    "known_peers": {"相手のmachine_id": "相手のTailscale_IP:7900"},
    "auth_key": "全マシン共通のキー"
}
```
**注意:**
- `machine_id` は全マシンでユニーク。辞書順で小さい方がclient役（outgoing接続）になる
- `known_peers` は `{"machine_id": "address"}` 形式。相手のmachine_idを記載
- `auth_key` は全マシンで同一にすること

### Step 3: MCP グローバル登録
```bash
claude mcp add --scope user claude-mesh -- python "/path/to/claude-mesh/mcp_server.py"
```
これで全プロジェクトからclaude-meshツールが使えるようになる。

### Step 4: Claude起動コマンドの設定

#### bash（Git Bash）の場合 — `~/.bashrc` に追加:
```bash
alias claude='claude --dangerously-load-development-channels server:claude-mesh --dangerously-skip-permissions'
```

#### PowerShellの場合 — `$PROFILE` に追加:
```powershell
function claude { & claude.exe --dangerously-load-development-channels server:claude-mesh --dangerously-skip-permissions @args }
```

#### SSH経由でリモートPCのClaudeを起動する場合:
リモートPC側に `~/claude-mesh.sh` を作成:
```bash
#!/bin/bash
exec claude.exe --dangerously-load-development-channels server:claude-mesh --dangerously-skip-permissions "$@"
```
```bash
chmod +x ~/claude-mesh.sh
```
ローカルPC側のPowerShell `$PROFILE` に追加:
```powershell
function claude-remote { ssh -t remote-pc ~/claude-mesh.sh }
```

### Step 5: SSH設定（リモートPCへの接続用）
`~/.ssh/config` に追加:
```
Host remote-pc
    HostName <TailscaleのIP>
    User <ユーザー名>
    ServerAliveInterval 15
    ServerAliveCountMax 3
```

### Step 6: statusline設定（context: X% 表示）
`~/.claude/statusline.js` を作成:
```javascript
#!/usr/bin/env node
let input = '';
process.stdin.on('data', chunk => input += chunk);
process.stdin.on('end', () => {
    const data = JSON.parse(input);
    const pct = Math.floor(data.context_window?.used_percentage || 0);
    console.log(`context: ${pct}%`);
});
```
Claude Codeのsettings.jsonに追加:
```json
"statusLine": {
    "type": "command",
    "command": "node C:/Users/<ユーザー名>/.claude/statusline.js"
}
```

### Step 7: 動作確認
```bash
claude
```
起動時に以下が表示されればOK:
- `Listening for channel messages from: server:claude-mesh` — channels有効
- `bypass permissions on` — パーミッションスキップ有効
- `context: 0%` — statusline有効

`list_peers` で他のマシンのpeerが見えれば完了。

## 設定ファイル詳細

`~/.claude-mesh.json`:
```json
{
    "machine_id": "my-pc",
    "machine_name": "My PC",
    "transport": "direct",
    "mesh_port": 7900,
    "local_api_port": 7901,
    "known_peers": {"other-pc": "100.x.x.x:7900"},
    "auth_key": "shared-secret-key"
}
```

| フィールド | 説明 |
|-----------|------|
| machine_id | マシンの一意識別子。辞書順で小さい方がclient役 |
| machine_name | 表示名 |
| transport | "direct"（現在はこれのみ） |
| mesh_port | broker間通信ポート（デフォルト7900） |
| local_api_port | MCP→broker通信ポート（デフォルト7901） |
| known_peers | {machine_id: address} 形式の接続先 |
| auth_key | 認証キー（全マシン共通） |

## 実装ステップ

| Step | 内容 | 状態 |
|------|------|------|
| 1 | Transport抽象 + DirectTransport | ✅ 完了 |
| 2 | PeerRegistry (SQLite) | ✅ 完了 |
| 3 | Mesh Broker (ローカルAPI + peer同期) | ✅ 完了 |
| 4 | MCP Server (stdio) | ✅ 完了 |
| 5 | 2台で動作テスト | ✅ 完了 (2026-04-02) |
| 6 | broker自動起動 + heartbeat + stale cleanup | ✅ 完了 |
| 7 | channels リアルタイム通知 | ✅ 完了 |
| 8 | 日本語対応（UTF-8強制） | ✅ 完了 |
| 9 | ブロードキャスト（全peer一斉送信） | 未着手 |
| 10 | RelayTransport追加 | 未着手 |

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
