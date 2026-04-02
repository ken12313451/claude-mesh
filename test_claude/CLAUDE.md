# claude-mesh MCP E2Eテスト

## あなたの役割
あなたはclaude-meshのMCP E2Eテストを実行するテスト用Claudeセッションです。

## 前提条件
- broker.pyがlocalhost:7901で稼働中
- リモートbroker（Home PC）とWebSocket接続済み
- MCP Server（claude-mesh）が登録済み

## テスト手順

以下を順番に実行し、結果を報告してください。

### 1. list_peers（全peer一覧）
MCPツール `list_peers` を scope="all" で実行。
ローカルpeerとリモートpeer（Home PC）が表示されれば成功。

### 2. set_summary（自己紹介）
MCPツール `set_summary` で「E2E test session」と設定。

### 3. list_peers（自分が見えるか確認）
再度 `list_peers` を実行。自分のセッション（E2E test session）が表示されれば成功。

### 4. send_message（リモートへ送信）
MCPツール `send_message` で、リモートpeer宛に「E2E test from test_claude session」を送信。
to には "RC test" または リモートpeerのsummaryを指定。

### 5. check_messages（受信確認）
MCPツール `check_messages` を実行。
リモートからの返信があれば表示、なければ「No new messages」と報告。

### 6. mesh_status（ネットワーク状態）
MCPツール `mesh_status` を実行。connected_brokersにリモートbrokerが表示されれば成功。

## 結果報告
各ステップの成功/失敗を一覧で報告してください。
