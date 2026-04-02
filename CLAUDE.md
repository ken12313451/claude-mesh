# claude-mesh

## プロジェクト概要

リモートマシン間で複数のClaude Codeセッションが相互に発見・通信できる分散メッシュネットワーク。claude-peers-mcp（同一マシン内限定）をリモートマシン間に拡張するプロジェクト。

## 前身プロジェクト

- **claude-peers-mcp** — 同一マシン内のClaude Code間通信（MCP + ローカルbroker）
- **claude-pty-bridge** — PTY常駐 + WebSocket + ファイルベースリレーによるリモート1対1通信

## 設計原則

1. **Peer-to-Peer**: 中央サーバーなし。各マシンのbrokerが対等に接続
2. **Transport抽象化**: Tailscale直接 / クラウドリレー / ngrok等を差し替え可能
3. **MCP準拠**: Claude Codeの標準MCP機構で統合
4. **最小依存**: Python標準ライブラリ + websockets + SQLite

## コンポーネント

| ファイル | 役割 |
|---------|------|
| `broker.py` | Mesh Broker — 各マシンで1つ常駐。peer管理 + リモート同期 + メッセージルーティング |
| `transport/base.py` | Transport抽象インターフェース |
| `transport/direct.py` | Tailscale/LAN直接WebSocket接続 |
| `transport/relay.py` | クラウドリレー経由接続 |
| `mcp_server.py` | MCP Server — Claude Codeセッションごとに起動 |
| `registry.py` | Peer Registry — SQLiteでpeer/message管理 |
| `config.py` | 設定管理 |
| `mesh.json` | マシン固有の設定ファイル |

## 通信フロー

```
Claude → MCP Server → HTTP(localhost:7901) → Mesh Broker → Transport → Remote Broker → Registry → Remote Claude
```

## ポート使用

- 7900: Mesh Broker間通信（Transport層、リモート接続用）
- 7901: Mesh BrokerローカルAPI（MCP Server → Broker通信用）

## 関連リソース

- [claude-peers-mcp](https://github.com/louislva/claude-peers-mcp)
- [claude-pty-bridge](https://github.com/ken12313451/claude-pty-bridge)
- [Zenn記事: Claude Code同士が会話できるようになったらしいので試してみた](https://zenn.dev/acntechjp/articles/7bb9f418be6e68)

## 開発フェーズ

- Step 1: Transport抽象 + DirectTransport
- Step 2: PeerRegistry (SQLite)
- Step 3: Mesh Broker (ローカルAPI + peer同期)
- Step 4: MCP Server (stdio)
- Step 5: 2台で動作テスト
- Step 6: RelayTransport追加
