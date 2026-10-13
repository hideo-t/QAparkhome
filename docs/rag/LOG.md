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
