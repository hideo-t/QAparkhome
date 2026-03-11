"""
トレーラーハウス Q&A 500問生成スクリプト（v2）
============================================
使い方：
  1. base_qa_50.json を同じフォルダに置く
  2. ANTHROPIC_API_KEY を設定
     Windows: set ANTHROPIC_API_KEY=sk-ant-xxxx
     Mac/Linux: export ANTHROPIC_API_KEY=sk-ant-xxxx
  3. python generate_qa_v2.py
  4. qa_data.json が生成される（500問以上）

必要なライブラリ：
  pip install anthropic
"""

import anthropic
import json
import time
import os
from datetime import datetime

# ============================================================
#  設定
# ============================================================
API_KEY    = os.environ.get("ANTHROPIC_API_KEY", "ここにAPIキーを入れる")
MODEL      = "claude-opus-4-5"
BASE_FILE  = "base_qa_50.json"   # 元データ
OUTPUT     = "qa_data.json"      # 出力先

# ============================================================
#  プロンプト定義（7カテゴリ × 約70問）
# ============================================================
PROMPTS = [
    {
        "id": "law",
        "category": "法令・手続き詳細",
        "prompt": """あなたはトレーラーハウスの法律専門家です。Q&Aを70問作成してください。

テーマ：法令・手続きの深掘り
トピック：
- 市街化調整区域・農地・河川敷・別荘地への設置
- 旅館業法・消防法の具体的な要件
- 特殊車両通行許可の詳細
- 用途地域ごとの制限
- 沖縄県固有の法令・条例・台風対策規制

必ずJSON配列のみ出力（前後の説明文は不要）：
[{"question":"質問","answer":"回答（200字以内）","category":"法令・手続き"},...]

質問は口語も含む（例：「農地に置ける？」「申請めんどくさい？」）"""
    },
    {
        "id": "tax",
        "category": "税金・費用詳細",
        "prompt": """あなたはトレーラーハウスの税務専門家です。Q&Aを70問作成してください。

テーマ：税金・費用・投資対効果
トピック：
- 固定資産税がかからない理由の詳細
- 減価償却4年の具体的な節税シミュレーション
- 法人購入の場合の経費処理
- 民泊・宿泊施設の収益計算（具体的な数字で）
- 融資・ローン・補助金・助成金
- 初期投資の回収期間の目安

必ずJSON配列のみ出力：
[{"question":"質問","answer":"回答（200字以内）","category":"税金・費用"},...]

「いくら儲かる？」「節税できる？」など口語的な質問も含める"""
    },
    {
        "id": "install",
        "category": "設置・工事・環境",
        "prompt": """あなたはトレーラーハウスの設置工事専門家です。Q&Aを70問作成してください。

テーマ：設置・工事・環境対応
トピック：
- 土地の条件（広さ・形状・地盤・傾斜地）
- 電気・水道・ガスの引き込み工事詳細
- 沖縄の台風対策・固定方法（風速数値を含む）
- 沖縄の塩害・湿気・シロアリ・サビ対策
- 離島（石垣・宮古・久米島）への輸送・設置
- 複数台設置・太陽光発電との組み合わせ

必ずJSON配列のみ出力：
[{"question":"質問","answer":"回答（200字以内）","category":"設置・工事"},...]

沖縄固有の環境（台風・塩害・亜熱帯）の質問を多く含める"""
    },
    {
        "id": "business",
        "category": "活用用途・ビジネスモデル",
        "prompt": """あなたはトレーラーハウス活用コンサルタントです。Q&Aを70問作成してください。

テーマ：活用用途とビジネスモデル
トピック：
- グランピング・アウトドア・リゾート施設
- 民泊・宿泊施設（Airbnb・旅館業登録）
- 飲食店・カフェ・サロン・美容室・店舗
- 農業（農家民宿・農作業小屋・体験農園）
- 週末別荘・セカンドハウス・沖縄移住
- 沖縄観光業との組み合わせ・グランピング

必ずJSON配列のみ出力：
[{"question":"質問","answer":"回答（200字以内）","category":"活用用途"},...]

「何に使えるの？」「どんなビジネスができる？」など初心者向け質問を多く含める"""
    },
    {
        "id": "compare",
        "category": "購入比較・検討",
        "prompt": """あなたはトレーラーハウス販売コンサルタントです。Q&Aを70問作成してください。

テーマ：購入検討・比較・メーカー選び
トピック：
- コンテナハウス・プレハブ・キャンピングカーとの違い
- 普通の家（建築物）との比較・メリットデメリット
- 新築vs中古の選び方・中古市場
- メーカー選びのポイント・確認すべきこと
- 購入から設置完了までの流れ・スケジュール
- アフターサービス・保証・トラブル対応

必ずJSON配列のみ出力：
[{"question":"質問","answer":"回答（200字以内）","category":"購入比較"},...]

「プレハブと何が違うの？」「失敗しない選び方は？」など素朴な疑問を多く含める"""
    },
    {
        "id": "colloquial",
        "category": "口語・あいまい質問",
        "prompt": """あなたはトレーラーハウスの専門家です。Q&Aを80問作成してください。

テーマ：実際のユーザーが打ち込む口語的・あいまいな質問
質問パターン：
- 超短い質問（「値段は？」「許可いる？」「移動できる？」「何年使える？」）
- 文脈が不完全（「海の近くに置きたい」「農家なんだけど」「庭に置きたい」）
- 感情が入った質問（「本当に固定資産税かからないの？」「台風で飛ばない？」）
- 比較質問（「マンション買うより得？」「キャンプ場みたいに使える？」）
- 沖縄移住者向け（「沖縄で暮らしたい」「海が見える場所に住みたい」）
- 不安な質問（「ローンは組める？」「隣近所に迷惑かけない？」）

必ずJSON配列のみ出力：
[{"question":"質問","answer":"回答（200字以内）","category":"口語質問"},...]

chatbotが実際に受ける質問に近い表現・省略・口語体で作成すること"""
    },
    {
        "id": "okinawa",
        "category": "沖縄特化",
        "prompt": """あなたは沖縄でトレーラーハウス事業を展開する専門家です。
沖縄固有の事情に特化したQ&Aを70問作成してください。

トピック：
- 台風対策（風速・固定方法・被害事例・保険）
- 塩害・湿気・シロアリ・サンゴ礁地盤
- 離島（石垣・宮古・西表・久米島・沖永良部）への輸送・費用
- 沖縄の観光業との連携（グランピング・民泊・リゾート）
- 沖縄移住希望者向けの活用（移住支援制度との組み合わせ）
- やんばる・美ら海・本部半島周辺の法規制
- 沖縄の補助金・支援制度・IT導入補助金
- リゾート開発・ホテル・グランピング施設としての活用
- 沖縄の気候に合った仕様（断熱・通風・UVカット）

必ずJSON配列のみ出力：
[{"question":"質問","answer":"回答（200字以内）","category":"沖縄特化"},...]

「沖縄に移住したい」「海の見える場所に置きたい」「台風が心配」など
沖縄ならではの動機・不安を持つ人向けの質問を多く含める"""
    },
]

# ============================================================
#  メイン処理
# ============================================================
def load_base_data():
    """base_qa_50.json を読み込む"""
    if not os.path.exists(BASE_FILE):
        print(f"⚠️  {BASE_FILE} が見つかりません。スクリプトと同じフォルダに置いてください。")
        return []
    with open(BASE_FILE, encoding='utf-8') as f:
        data = json.load(f)
    # id が無ければ付与
    for i, item in enumerate(data):
        if 'id' not in item:
            item['id'] = f"base_{i+1:03d}"
    print(f"✅ 元データ読み込み: {len(data)}問")
    return data


def generate_batch(client, prompt_config):
    """1カテゴリ分を生成"""
    print(f"\n{'─'*50}")
    print(f"▶ {prompt_config['category']}")
    print(f"{'─'*50}")

    try:
        msg = client.messages.create(
            model=MODEL,
            max_tokens=8000,
            messages=[{"role": "user", "content": prompt_config["prompt"]}]
        )
        raw = msg.content[0].text.strip()

        # ```json ... ``` ブロックを除去
        raw = raw.replace("```json", "").replace("```", "").strip()

        # JSON抽出
        start = raw.find("[")
        end   = raw.rfind("]") + 1
        if start == -1 or end == 0:
            print(f"  ⚠️  JSONが見つかりません")
            print(f"  先頭100文字: {raw[:100]}")
            return []

        items = json.loads(raw[start:end])

        # id・category を付与・補完
        for i, item in enumerate(items):
            item.setdefault('id',       f"{prompt_config['id']}_{i+1:03d}")
            item.setdefault('category', prompt_config['category'])

        print(f"  ✅ {len(items)}問 生成")
        return items

    except json.JSONDecodeError as e:
        print(f"  ❌ JSONパースエラー: {e}")
        return []
    except Exception as e:
        print(f"  ❌ APIエラー: {e}")
        return []


def save(data, path):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main():
    print("=" * 55)
    print("  トレーラーハウス Q&A 500問生成スクリプト v2")
    print(f"  開始: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 55)

    if API_KEY == "ここにAPIキーを入れる":
        print("❌ APIキーが設定されていません。")
        print("   環境変数 ANTHROPIC_API_KEY を設定してください。")
        return

    client = anthropic.Anthropic(api_key=API_KEY)

    # 元データ読み込み
    all_qa = load_base_data()
    if not all_qa:
        return

    # 7カテゴリを順番に生成
    for config in PROMPTS:
        batch = generate_batch(client, config)
        all_qa.extend(batch)

        # 途中保存（クラッシュ対策）
        save(all_qa, OUTPUT)
        print(f"  💾 中間保存 → 現在合計 {len(all_qa)}問")

        time.sleep(2)  # レート制限対策

    # 完了
    print("\n" + "=" * 55)
    print(f"  ✅ 完了！ 合計 {len(all_qa)}問")
    print(f"  📄 保存先: {OUTPUT}")
    print(f"  終了: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 55)

    # カテゴリ別集計
    print("\n【カテゴリ別】")
    cats = {}
    for item in all_qa:
        c = item.get('category', '不明')
        cats[c] = cats.get(c, 0) + 1
    for c, n in sorted(cats.items(), key=lambda x: -x[1]):
        bar = '█' * (n // 5)
        print(f"  {c:<16} {n:>4}問 {bar}")


if __name__ == "__main__":
    main()
