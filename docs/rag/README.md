# AIアシスタント高度化（RAG化）記録

`parkhomes-okinawa.com/QAparkhome/` のトレーラーハウスAIアシスタントを高度化する作業の記録。
設計・計画・実装ログをここに残す。作業のたびに更新する。

| ファイル | 中身 |
|---|---|
| [DESIGN.md](DESIGN.md) | 現状の構成、課題、目標の構成、設計判断とその理由 |
| [PLAN.md](PLAN.md) | 段階ごとの作業と完了条件、進捗 |
| [LOG.md](LOG.md) | 作業ログ（日付順。何をして、何を確かめたか） |

## 関係するリポジトリ

| リポジトリ | 役割 |
|---|---|
| [hideo-t/QAparkhome](https://github.com/hideo-t/QAparkhome) | チャット画面（GitHub Pages）。この記録もここ |
| hideo-t/aisdr-proxy（private） | Cloudflare Worker。Claude API を中継する。他案件と共用 |
| [hideo-t/phoka2](https://github.com/hideo-t/phoka2) | 公式サイトのステージング。知識ベースの材料（`data/site_data.json` など） |

## 進捗

| 段階 | 内容 | 状態 |
|---|---|---|
| 1 | Worker の防御と、モデル・プロンプトのサーバー側移設 | 作業中 |
| 2 | 知識ベース作り直し＋全量投入（プロンプトキャッシュ） | 未着手 |
| 3 | 出典リンク表示、根拠なし時の問い合わせ誘導 | 未着手 |
| 4 | 評価セットと質問ログ | 未着手 |
| 5 | ベクトル検索・見積連携・問い合わせ受付 | 必要になってから |
