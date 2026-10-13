# 設計

## 1. 現状（2026-10-13 調査）

```
parkhomes-okinawa.com/QAparkhome/
  └ iframe → hideo-t.github.io/QAparkhome/（このリポジトリの index.html）
        ├ qa_data.json（3MB）をブラウザで全部読む
        ├ バイグラム＋キーワード一致で上位8件を選ぶ
        ├ system プロンプトをブラウザで組み立てる
        └ POST https://aisdr-proxy.hdxrope.workers.dev/  { model, system, messages }
              └ Anthropic Messages API（APIキーは Worker の Secret）
```

### 課題

| # | 課題 | 根拠 |
|---|---|---|
| A | 知識の中身が薄い | `qa_data.json` 8,100件のうち、違う回答は50件だけ。残りは「〜について教えて」「〜 知りたい」等の言い換えの水増し。「質問1」形式のダミー質問が150件ある |
| B | 検索が表面の文字一致 | 言い回しが違うと拾えない。水増し・ダミーが上位を占めうる |
| C | Worker の防御が弱い | 用途の固定・利用元の制限・回数制限がない。詳細は private の aisdr-proxy リポジトリに記録 |
| D | 回答の根拠が見えない | 出典表示はカテゴリ名のチップだけ |
| E | 品質を測る手段がない | 評価セットも運用ログもない |

## 2. 目標の構成

```
ブラウザ（index.html）
  └ POST https://aisdr-proxy.hdxrope.workers.dev/parkhomes/chat  { messages }
        Worker（専用ルート）
        ├ Origin 許可リスト（parkhomes-okinawa.com / hideo-t.github.io / localhost）
        ├ IP 単位のレート制限（Workers Rate Limiting）
        ├ 入力の上限（履歴10往復・1発言1000字）
        ├ system = 固定の指示 ＋ 知識ベース全量（cache_control でキャッシュ）
        ├ model・max_tokens はサーバー側で固定
        └ Anthropic Messages API
        → { answer, model, usage }
```

## 3. 設計判断

### 3.1 新しい Worker を立てず、共用 Worker に専用ルートを足す

- 共用の `aisdr-proxy` は「AIの町医者」も `/` `/openai-image` `/deepseek` を使っている。
  `/` 自体を締めると町医者が壊れるおそれがある（町医者の配信元を把握していない）。
- 別 Worker にすると APIキーの Secret を二重に登録・管理することになる。
- そこで `aisdr-proxy` に **Park Homes 専用ルート `/parkhomes/chat`** を足し、コードは
  `src/parkhomes.js` に分ける。既存ルートの挙動は変えない。
- 段階5で D1・Vectorize などを足して共用 Worker が重くなったら、別 Worker へ切り出す。

### 3.2 `/` の防御は段階的に

- QAparkhome を新ルートへ移した後、`/` の利用者は町医者だけになる。
- 町医者の配信元（Origin）が分かれば `/` にも許可リストをかける。分かるまでは触らない。
  → PLAN.md の 1c。

### 3.3 検索をやめて知識ベースを全部渡す（段階2のA案。段階1で先行導入）

- 元の50問は約4,300字（数千トークン）しかない。検索で8件に絞る理由がない。
- 全量を system に入れ、`cache_control` でキャッシュする。
  Claude Sonnet 5 のキャッシュ最小長は 1,024 トークンで、これを超える。
- 検索漏れがゼロになり、水増しデータの悪影響も消える。
- カタログやPDFを足して数十万トークン規模になったら、段階5でベクトル検索に切り替える。

### 3.4 モデル

- 段階1では今と同じ `claude-sonnet-5` をサーバー側で固定する（挙動を変えないため）。
- `claude-sonnet-5-5` や `claude-haiku-5-5` への切り替えは、段階4の評価セットで比べてから決める。
- `claude-sonnet-5` は応答の先頭に `thinking` ブロックを付けることがある。
  Worker 側で `type === "text"` のブロックだけを連結して `answer` として返す。

### 3.5 レート制限の値

- Workers Rate Limiting の binding を使う。窓は 10秒か60秒しか選べない。
- 1 IP あたり 60秒に10回。人が会話する速さでは当たらず、機械的な連打は止まる。
- この制限は Cloudflare の拠点ごとに数える近似値。厳密な上限ではない。
  料金の最後の歯止めは Anthropic コンソール側の月額上限で持つ。

### 3.6 Origin チェックの限界

- Origin はブラウザ以外からは偽装できる。Origin チェックは「他サイトに埋め込まれて使われる」ことを防ぐもので、
  直接叩く攻撃はレート制限と「system を受け付けない（用途を Park Homes の回答に固定）」で抑える。
