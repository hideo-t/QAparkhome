# 作業ログ

## 2026-10-13

### 調査
- `parkhomes-okinawa.com/QAparkhome/` は `hideo-t.github.io/QAparkhome/` を iframe で表示しているだけと確認。
- 本体 `index.html` の仕組みを確認（DESIGN.md §1）。
- `qa_data.json` を集計: 8,100件 / ユニーク回答50件 / ユニーク質問353件 / 「質問N」ダミー150件。
- `aisdr-proxy` のソースを確認。`/` は町医者と共用（防御の詳細は aisdr-proxy 側に記録）。
- Claude Sonnet 5 のキャッシュ最小長は 1,024 トークン。`base_qa_50.json` は約4,300字で、全量投入して問題ない。

### 設計・計画
- DESIGN.md、PLAN.md を作成。段階1から着手。

### 1a 実装（aisdr-proxy `420acfc`）
- `src/parkhomes/index.js` を追加。`/parkhomes/chat` を既存処理より前で分岐。既存ルートは無変更。
- `wrangler.toml` に Rate Limiting binding `PH_LIMITER`（60秒10回）を追加。
- 知識ベースは `base_qa_50.json` をそのまま `src/parkhomes/kb.json` として同梱（段階2で作り直す）。system は 5,618字。

ローカル確認（`wrangler dev`、APIキーはダミー）

| 確認 | 結果 |
|---|---|
| Origin なし / 他サイトの Origin | 403 |
| 許可 Origin の preflight | 204、`Access-Control-Allow-Origin` に同じ Origin |
| 壊れた JSON / 空の messages / 最後が assistant / 1001字 | 400 |
| GET | 405 |
| 正しいリクエスト | Anthropic まで届き、ダミーキーで 401 → 502 で返る |
| 連打 | 11回目以降 429 |
| 既存 `/` の preflight | 204、`*`（従来どおり） |
| 単体テスト | 送信本文は `model`/`max_tokens`/`system`/`messages` の4項目だけ。クライアントの `system`・`model` は捨てる。履歴は10件まで、先頭は user |

### 1b 実装（QAparkhome ブランチ `feat/parkhomes-chat` `451aa38`）
- `index.html` / `chatbot.html` から、ブラウザ側の知識ベース検索と system 組み立てを削除（約250行減）。
  3MB の `qa_data.json` を読まなくなる。
- 送信は `{ messages }` だけ、表示は `data.answer`。
- 失敗した質問は履歴から外す（次の送信で user が2つ続かないように）。
- Worker のデプロイと本番確認が済むまで main にはマージしない（GitHub Pages が即時反映されるため）。

### レビュー（別エージェント）と修正
- 重大・高の指摘なし。中・低の指摘を反映（aisdr-proxy の修正コミット、QAparkhome ブランチの修正コミット）。
  - 例外時もCORSヘッダー付きで 502 を返す
  - レート制限の binding が無い本番では 503（制限なしで公開しない。localhost だけ例外）
  - Anthropic のエラー詳細（キー・残高の状態）は画面に出さず、Worker のログにだけ残す
  - `Vary: Origin` を常に付ける。preflight を `Max-Age 86400` でキャッシュ
  - messages は50件まで
  - `max_tokens` を 2048 に（`claude-sonnet-5` の thinking もこの枠を使い、1024 だと回答が切れるおそれ）
  - 画面: クリア時に送信中の要求を止める、入力欄 `maxlength=1000`、空の `ANTHROPIC_API_KEY` 定数を削除
- 見送り: `hideo-t.github.io` は GitHub Pages 全体で1つの Origin なので、同じアカウントの他リポジトリのページからも呼べる。現状は許容。
- 修正後にローカル確認と単体テストを再実行し、すべて期待どおり。

### 次: デプロイ（Cloudflare へのログインが必要）
