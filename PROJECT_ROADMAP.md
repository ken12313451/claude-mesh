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

**現実的な工数:** 4〜6 日(集中作業時)

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

| 項目 | 工数感 |
|---|---|
| ユニットテスト(`registry.py` の基本操作、`config.py` の I/O) | 1日 |
| ユニットテスト(`broker.py` の HTTP API、モック transport) | 1日 |
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
