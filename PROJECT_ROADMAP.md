# claude-mesh プロジェクトロードマップ

このドキュメントは claude-mesh を「個人で便利に使えるツール」から「他人にも触ってもらえる
OSS」に育てる過程を3つのフェーズに分けて記述する。技術仕様(プロジェクトが何であるか)
は [README.md](./README.md) を、開発時のアシスタント向けの指示は
[CLAUDE.md](./CLAUDE.md) を参照すること。

---

## ミッション

**「Claude に名前が付く」** — claude-mesh の最大の差別化要素はここにある。LangGraph や
CrewAI、Claude Code subagent といった既存の multi-agent アプローチはどれも「役割」や
「インスタンス」を扱うが、**人格を持った固有名詞** として Claude を扱うのは claude-mesh
だけ。リモートマシンをまたいで対称な会話ができることと相まって、技術的な目新しさだけ
ではなく感情的な吸引力を持つ。ロードマップ全体はこの軸で評価する。

---

## 非機能要件: ホット更新性

**原則: claude-mesh 自身のアップデートによって、既に走っている Claude Code セッション
が再起動を強いられないこと。**

claude-mesh の構造上の弱点は、現状ではバグ修正や機能追加を反映するために全ての
Claude Code を手動で再起動する必要があるところにある。ロジックの大部分が
`mcp_server.py`(stdio 経由で Claude Code の子プロセスとして動く)に同居しているため、
コードを編集してもメモリ内ロード済みの既存プロセスには届かない。

OSS として配布する時、「`pip install --upgrade` したけど既存セッションを全部再起動
してください」と言わなければならない体験は致命的に悪い。アップデートが痛みなしに
届く構造は機能ではなく **基盤要件** として扱う。

**解決アプローチ(B.0 で実装):**

- `mcp_server.py` を「stdio と broker HTTP を橋渡しするだけ」の薄いシム(約150行)に
  まで削ぎ落とす
- ロジック(nickname 管理、tool handler 実装、heartbeat、メッセージルーティング)は
  broker 側に移動
- broker は既に独立プロセスなので、broker だけを再起動すれば大半の更新が反映される
- シムは broker への接続が一瞬切れることに耐えるよう、自動再接続を持つ
- シム自体を変更した場合だけ Claude Code の再起動が必要だが、シムは薄いので頻繁には
  変わらない想定

詳細は下記の **Phase B.0** を参照。

## 競合

claude-mesh の最大のライバルは別の OSS ではなく **Anthropic 公式の Claude Code subagent
機能**。多くの人は「複数 Claude を協調させたい」と聞くと反射的に「subagent でいいので
は?」と考えるため、ピッチの最初の1〜2文で違いを打ち出す必要がある:

- **多マシンにまたがる**(subagent は1マシン内)
- **永続的な peer ID と人格**(subagent は使い捨て)
- **異なるプロジェクトにいる Claude 同士**(subagent は同一プロジェクト内)
- **対称的な P2P 通信**(subagent は親子関係)

---

## 現在地

セッション 2026-04-10 〜 2026-04-11 の作業で、フェーズ A は実質完了。
フェーズ B/C はこれから。

最新の主要マイルストーン:

- 2026-04-10: ステータスラインのニックネーム取り違えバグ修正(`_guess_session_id`
  のクロスプロジェクト走査と heartbeat の nickname 再同期欠落)
- 2026-04-10: `cli.py`(対話セットアップ CLI、`init` / `install` / `status`)追加
- 2026-04-11: リポジトリ整理(Python コードを `src/` に集約)、`test_claude/` を
  個人情報含むため履歴ごと削除(filter-repo + force push)、本ロードマップ作成

---

## Phase A: 「クローンしたら 5 分で動く」最低ライン ✅

**目的:** git clone してきた人が、設定ファイルを手で書かず、MCP も手で登録せず、
statusline も手で配置せず、5 分以内に動かせる状態にする。

| 項目 | 状態 |
|---|---|
| `cli.py init` 対話ウィザード(machine_id / port / auth_key 自動生成) | ✅ |
| `cli.py install` MCP 登録 + statusline 自動配置 + 二重登録防止 | ✅ |
| `cli.py status` 診断コマンド | ✅ |
| README にクイックスタート章 | ✅ |
| 既存環境(ken1i のメインマシン)での `status` 動作確認 | ✅ |
| **別マシン or クリーン環境での `init` / `install` 実機検証** | ⏳ 未実施 |

**A の完全完了の条件:** 別マシン(Home PC など)で `git pull` → `python cli.py init` →
`python cli.py install` → `claude` 起動 → ステータスラインに虹色のニックネーム表示、
までを実際に踏んで成功させる。

---

## Phase B: 「pipx install で済む」OSS 標準

**目的:** クローンせずにワンライナーでインストールでき、複数人の開発が回せる体裁を
整える。OSS としての最低限の作法を満たす。

**現実的な工数:** 6〜9 日(集中作業時、B.0 込み)

### B.0 thin shim refactor(ホット更新性の基盤)★最優先

**目的:** `mcp_server.py` を薄いシムに削ぎ落とし、ロジックを broker 側に寄せる。
これにより broker の再起動だけで大半のアップデートが反映されるようにする。
**B.1 のパッケージ化より前に実施する** — 太い shim をそのままパッケージ化してから
リファクタするのは二度手間になるため。

| 項目 | 工数感 |
|---|---|
| broker 側に nickname pool + nickname 発行ロジックを移動 | 半日 |
| broker 側に tool handler 実装(list_peers / send_message / check_messages / set_summary / set_nickname / mesh_status)を移動。シムは HTTP proxy として薄い関数を持つだけにする | 1日 |
| broker に event stream エンドポイント新設(`GET /events?peer_id=...`、SSE または long-poll)。メッセージ受信を poll ではなく push で受け取る | 半日 |
| シム側に event stream 受信ループを実装、自動再接続と event ID ベースの重複検知を持たせる | 半日 |
| シム側を `_guess_session_id` / `_save_nickname` / `_remove_nickname` / stdio I/O / event stream 購読、の最小機能に絞る(現 660 行 → 約 150 行の目標) | 半日 |
| broker 側に heartbeat nickname 同期ロジックを移動(現在シム側にあるもの) | 数時間 |
| broker 再起動時にシム側が graceful に再接続することを動作確認(手動 `kill` + broker 再起動) | 数時間 |
| リファクタ後の回帰テスト(既存動作が全部動くこと)| 半日 |

**完了判定:**
- `kill <broker_pid>` してから broker.py を直接手で再起動しても、Claude Code 側は
  何事もなかったかのように動き続ける
- broker.py にバグ修正を入れて上記の再起動だけで反映される
- mcp_server.py(シム)は意図的に薄く、変更頻度が極めて低いファイルになっている

**後方互換性:** このリファクタは **1度きりの Claude Code 再起動を強いる**(シムの
構造が変わるため)。それ以降は broker の更新では再起動不要になる。Zenn 記事の
ストーリーとしては「この1回の再起動が最後の再起動です」という形で打ち出せる。

### B.1 構造とパッケージング

| 項目 | 工数感 |
|---|---|
| `src/` 構造 → `src/claude_mesh/` パッケージ化(`__init__.py`、相対インポート整備) | 半日 |
| `pyproject.toml` 整備、エントリポイント `claude-mesh` を `[project.scripts]` で公開 | 数時間 |
| `python cli.py init` → `claude-mesh init` で動くようにする | 数時間 |
| `LICENSE` ファイルの追加(MIT を想定。要確認) | 5分 |
| `CHANGELOG.md` の追加と運用ルール記載(Keep a Changelog 形式) | 数時間 |

### B.2 機能拡充

| 項目 | 工数感 |
|---|---|
| `claude-mesh peer add <id>=<host:port>` サブコマンド | 数時間 |
| `claude-mesh peer list` / `peer remove <id>` | 数時間 |
| `claude-mesh uninstall`(install を逆回しできる) | 数時間 |
| 既存ピアへのハンドシェイク確認(`peer add` 時に自動接続テスト) | 半日 |

### B.3 品質保証

B.0 の thin shim refactor により broker 側ロジックが pure function に近い形で
整理されているはずなので、テストを書きやすい前提で設計する。shim 側は stdio I/O
と HTTP proxy のみなので、ユニットテストより統合テスト(mcp_server.py を実プロセス
として起動 → broker と会話させる)の方が適切。

| 項目 | 工数感 |
|---|---|
| ユニットテスト(`registry.py` の基本操作、`config.py` の I/O) | 1日 |
| ユニットテスト(`broker.py` の HTTP API、tool handler、nickname 発行、モック transport) | 1日 |
| 統合テスト(subprocess で shim 起動 → broker と会話 → 期待レスポンスが返る) | 半日 |
| GitHub Actions(lint + test を push / PR で自動実行) | 数時間 |
| pre-commit hook(black / ruff など最低限) | 数時間 |

### B 完了の判定基準

- `pipx install git+https://github.com/ken12313451/claude-mesh.git` で動く
- `claude-mesh init && claude-mesh install` で 5 分以内に動作環境ができる
- CI が GitHub 上で緑色になる
- LICENSE と CHANGELOG が存在する

---

## Phase C: 「公開してウケを狙う」プロダクト品質

**目的:** PyPI に publish し、Zenn / HN / X 等で発射して、外部のユーザーに触って
もらう状態に持っていく。

**現実的な工数:** 1〜2 週間(B 完了後)

### C.1 検証と移植性

| 項目 | 工数感 |
|---|---|
| Linux 実機検証(Ubuntu か Debian) | 半日 |
| macOS 実機検証(可能なら) | 半日 |
| クリーンインストール再現テスト(VM か Docker、最低 2 OS) | 半日 |
| Windows / Linux / macOS の差異(改行コード、ロックファイル、パス区切り)を埋める | 1日 |

### C.2 ドキュメント

| 項目 | 工数感 |
|---|---|
| セキュリティモデルの明文化(`auth_key` の役割、Tailscale 前提、listen バインド範囲、`--dangerously-skip-permissions` を強制する設計の正当化) | 半日 |
| 図解の整備(architecture, message flow, sequence diagram) | 半日 |
| ドキュメントサイト(mkdocs + GitHub Pages)構築 | 1日 |
| 英語版 README(日本語版から要約) | 半日 |

### C.3 マーケティング素材 ★★★

| 項目 | 工数感 | 重要度 |
|---|---|---|
| **デモ動画(30 秒〜1 分)** — 「A14 のターミナルで Claude に頼んだら自宅 PC の Claude が応答してファイルを書く」みたいな絵的に強いシナリオ | 半日〜1日 | ★★★ |
| Zenn 記事(日本語、Zenn 元記事の続編としてリンクを貼る) | 半日〜1日 | ★★ |
| GIF / スクリーンショット(README 最上部に貼る用) | 数時間 | ★★ |

### C.4 公開

| 項目 | 工数感 |
|---|---|
| PyPI アカウント作成、test.pypi で予行演習 | 半日 |
| 本番 PyPI publish | 数時間 |
| HN(Show HN)投稿、X 告知、Zenn 公開 | 数時間 |
| 公開後のフィードバック対応(issue 返信、バグ修正、PR レビュー) | 継続 |

### C 完了の判定基準

- `pip install claude-mesh`(または `pipx install claude-mesh`)で誰でも入る
- README 最上部にデモ GIF と「クローン → 5 分で動く」のクイックスタートがある
- Zenn 記事が公開されている
- HN 等で1度は発射した
- 外部 issue / PR に最低 1 回は反応した

---

## 戦略メモ

### デモ動画は最優先タスク

C.3 のデモ動画は工数比でリターンが異常に高い。理由:

1. デモを作る過程で「インストールが分かりにくい」「設定が手間」が必ず見つかり、
   B/C の他項目の優先度を勝手に決めてくれる
2. デモ動画があるだけで Zenn 記事は書ける(C.2/C.3 の他項目を後回しにできる)
3. 技術記事の冒頭に動画があると拡散率が桁違い

そのため B が完全に終わる前にデモ撮影を試みる価値がある。具体的には B.1(パッケージ化)が
終わったタイミングでスライドインさせる:

```
A 完了
 ↓
B.1(パッケージ化)
 ↓
B.2(機能拡充の最低限: peer add だけ)
 ↓
★ ここでデモ撮影 + Zenn 記事下書き
 ↓
反応を見て B.3(テスト/CI)/ C(残り)の優先度を再評価
```

### README と Phase 表記の統合は保留

README には現在「実装ステップ」テーブル(Step 1〜10)があり、これは技術的な実装
マイルストーンを追跡している。本ロードマップの A/B/C とは粒度も意図も違うため、
今すぐ統合しない。将来的には:

- README は「claude-mesh とは何か」「どう使うか」のみに専念
- 過去の実装ステップは PROJECT_ROADMAP.md か CHANGELOG.md に移管
- 進行中のフェーズだけを README から PROJECT_ROADMAP.md にリンクで参照

という形に整理する想定。タイミングは B のパッケージ化前後が良い(その時 README
をいずれにせよ書き直すため)。

### 拡散させたい目線での優先順位

ken1i 自身が「便利に使う」だけで止めるなら A だけで十分。「知り合いに勧める」レベル
なら A + README 強化。「不特定多数に届ける」なら B〜C 全体。本ロードマップは最後の
シナリオを想定しているが、各フェーズの途中で止めることもできる。

---

## 将来の検討事項(優先度低・アイデア保管庫)

フェーズ A/B/C に入れるほどの緊急性はないが、忘れたくないアイデアを置く場所。
ここに書かれているからといって実装するとは限らない。

### 多言語ニックネームプール

現在のニックネームプール(`src/nicknames.py`)は 835 種類の英語名(Basil、Nemo、
Pixel 等)のみ。これを **多言語対応** して、ユーザーが好みの言語を選べるようにする。

**スコープ:**

- 日本語プール: romaji 表記の短い日本名(TARO、HANA、KENJI 等)を 800 個
  - ひらがな・漢字・カタカナは扱わない(ASCII 範囲に留める)
  - ステータスラインの虹色レンダリングとの相性、文字幅の一貫性のため
- ドイツ語プール: 普通のドイツ人名(Klaus、Erika、Felix 等)を 800 個
- config キー `nickname_languages`(list 型、例: `["english", "japanese"]`)で
  複数選択可能にする
- デフォルトは `["english"]`(後方互換)
- init ウィザードで選択 UI を提供

**現状のコードへの影響:**
構造変更は不要。`NICKNAMES` はフラット文字列リストなので、後から
`NICKNAMES = NICKNAMES_EN + NICKNAMES_JA` のように合成するだけで済む。今の段階で
事前準備は何もしなくてよい。

**位置づけ:**
機能というよりマーケティング素材。日本語プールは Zenn 記事のスクリーンショットや
デモ動画で「自分の Claude が TARO になる」という体験を作るための材料。
理想的な実装タイミングは C(公開直前)。B.0 の thin shim refactor が完了していれば、
broker だけを更新すれば既存ユーザーにも反映される(ホット更新性の恩恵)。

### その他

ここに書く価値が出てきたアイデアは随時追加する。

---
