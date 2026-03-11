"""
トレーラーハウスFAQチャットボットデータ生成器（安定版）
2000件をターゲットに、チェックポイント保存機能付き
"""

import json
import time
import hashlib
from typing import List, Dict, Any
from datetime import datetime
from tqdm import tqdm
import openai
from concurrent.futures import ThreadPoolExecutor, as_completed
import os
import signal
import sys

class TrailerHouseFAQGenerator:
    def __init__(self, api_key: str, model: str = "deepseek-chat"):
        """
        初期化
        Args:
            api_key: DeepSeek API key
            model: 使用するモデル
        """
        self.client = openai.OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com",
            timeout=120.0,  # タイムアウト延長
            max_retries=5    # リトライ回数増加
        )
        self.model = model
        self.generated_data = {
            "metadata": {
                "version": "2.0",
                "generated_date": datetime.now().isoformat(),
                "total_questions": 0,
                "language": "ja",
                "source": "DeepSeek API"
            },
            "categories": [
                "法令・手続き",
                "税金・費用", 
                "設置・運用",
                "メンテナンス",
                "カスタマイズ",
                "購入・販売",
                "生活・快適性",
                "災害・安全"
            ],
            "intents": [],
            "contexts": {},
            "keywords_index": {}
        }
        
        # キャッシュ用
        self.cache = {}
        
        # 中断シグナルのハンドラ
        signal.signal(signal.SIGINT, self.signal_handler)
        
    def signal_handler(self, sig, frame):
        """Ctrl+Cで中断された時のハンドラ"""
        print("\n\n🚨 中断シグナルを受信しました。データを保存します...")
        self.save_to_file("trailer_house_faq_interrupted.json")
        print("💾 中断データを保存しました。")
        sys.exit(0)
    
    def load_base_qa(self, base_qa_file: str) -> List[Dict]:
        """
        ベースとなる50のQAを読み込み
        """
        with open(base_qa_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def generate_question_variations(self, base_question: str, answer: str, category: str, count: int = 8) -> List[str]:
        """
        1つの質問からバリエーションを生成（件数減らして安定化）
        """
        # キャッシュチェック
        cache_key = hashlib.md5(f"{base_question}_{count}".encode()).hexdigest()
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        prompt = f"""
あなたはトレーラーハウスの専門家です。以下のFAQの質問から、自然な言い換えを{count}個生成してください。

【元の質問】
{base_question}

【回答】
{answer}

【カテゴリ】
{category}

要件：
1. 自然な日本語で、実際のユーザーが使いそうな表現
2. 敬語・丁寧語・カジュアルなど、様々な文体を含める
3. 同義語や言い換え表現を活用
4. 質問の意図は維持したまま、異なる角度からの質問も含める
5. 1行に1つの質問を出力

出力形式：
質問1
質問2
質問3
...
"""
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "あなたはトレーラーハウスFAQの専門家です。的確な質問の言い換えを生成します。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.8,
                max_tokens=1500,
                timeout=60
            )
            
            variations = response.choices[0].message.content.strip().split('\n')
            variations = [v.strip() for v in variations if v.strip() and not v.startswith('```')]
            
            # キャッシュに保存
            self.cache[cache_key] = variations
            time.sleep(0.3)  # API制限対策（間隔短縮）
            
            return variations[:count]  # 指定数に制限
            
        except Exception as e:
            print(f"⚠️  Error generating variations: {e}")
            return [base_question]
    
    def generate_response_variations(self, base_answer: str) -> List[str]:
        """
        回答の文体バリエーションを生成（簡略化）
        """
        # APIコールを減らすため、簡易的なバリエーションを返す
        return [
            base_answer,  # 標準
            f"【回答】\n{base_answer}",  # 見出し付き
            f"結論：{base_answer[:50]}... 詳細は以下をご確認ください。\n\n{base_answer}"  # 要約付き
        ]
    
    def generate_situational_questions_batch(self, base_qa: List[Dict], situations: List[str], total_count: int = 600) -> List[Dict]:
        """
        シチュエーション別質問をバッチ処理で一括生成（効率化）
        """
        all_questions = []
        
        prompt = f"""
以下の{len(situations)}つの状況について、それぞれ{total_count//len(situations)}個程度のトレーラーハウスに関する質問を生成してください。

【状況】
{chr(10).join([f'{i+1}. {s}' for i, s in enumerate(situations)])}

【参考QA例】
{json.dumps(base_qa[:5], ensure_ascii=False, indent=2)}

要件：
1. 各状況に特化した実用的な質問
2. 日本語で自然な表現
3. 以下のJSON形式で出力

出力形式：
[
  {{
    "situation": "状況1",
    "questions": [
      {{"question": "質問文1", "category": "カテゴリ"}},
      ...
    ]
  }},
  ...
]
"""
        
        try:
            print("🔄 シチュエーション質問を一括生成中...（約2-3分かかります）")
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "あなたはトレーラーハウスの専門家です。状況に応じた質問をJSON形式で生成します。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.9,
                max_tokens=4000,
                timeout=300  # 5分タイムアウト
            )
            
            # JSON部分を抽出
            content = response.choices[0].message.content
            import re
            json_match = re.search(r'\[.*\]', content, re.DOTALL)
            if json_match:
                questions_data = json.loads(json_match.group())
                for item in questions_data:
                    for q in item['questions']:
                        all_questions.append({
                            "question": q['question'],
                            "category": q.get('category', '一般'),
                            "situation": item['situation']
                        })
            
            print(f"✅ {len(all_questions)}件のシチュエーション質問を生成")
            return all_questions[:total_count]
            
        except Exception as e:
            print(f"❌ シチュエーション生成エラー: {e}")
            return []
    
    def generate_all(self, base_qa_file: str, target_size: int = 2000) -> Dict:
        """
        メイン生成関数 - 2000件を目標に効率化
        """
        print(f"Loading base QA from {base_qa_file}...")
        base_qa = self.load_base_qa(base_qa_file)
        print(f"Loaded {len(base_qa)} base QA pairs")
        
        all_intents = []
        used_patterns = set()
        
        # チェックポイントから再開するか確認
        if os.path.exists('trailer_house_faq_checkpoint.json'):
            try:
                with open('trailer_house_faq_checkpoint.json', 'r', encoding='utf-8') as f:
                    checkpoint = json.load(f)
                    all_intents = checkpoint.get('intents', [])
                    print(f"🔄 チェックポイントから再開: {len(all_intents)}件既存")
            except:
                print("⚠️ チェックポイント読み込みエラー、新規生成開始")
        
        SAVE_INTERVAL = 50  # 50件ごとに保存
        
        # フェーズ1: 基本QAのバリエーション（最重要項目から）
        print("\n=== Phase 1: Generating variations from base QA ===")
        phase1_count = min(400, target_size // 3)
        
        # 重要度の高いQAから優先処理
        priority_categories = ["法令・手続き", "税金・費用", "設置・運用"]
        priority_qa = [qa for qa in base_qa if qa.get('category') in priority_categories]
        other_qa = [qa for qa in base_qa if qa not in priority_qa]
        
        for qa in tqdm(priority_qa + other_qa[:20], desc="Processing base QA"):
            if len(all_intents) >= phase1_count:
                break
                
            try:
                question_variations = self.generate_question_variations(
                    qa["question"], 
                    qa["answer"], 
                    qa.get("category", "一般"), 
                    count=6  # 6パターンに削減
                )
                
                intent = {
                    "tag": f"faq_{len(all_intents):05d}",
                    "category": qa.get("category", "一般"),
                    "patterns": question_variations,
                    "responses": [qa["answer"]],  # シンプルに
                    "context": {}
                }
                
                all_intents.append(intent)
                
                # チェックポイント保存
                if len(all_intents) % SAVE_INTERVAL == 0:
                    self.generated_data["intents"] = all_intents
                    self.save_to_file("trailer_house_faq_checkpoint.json")
                    print(f"💾 チェックポイント保存: {len(all_intents)}件")
                    
            except Exception as e:
                print(f"⚠️ エラー: {e}、スキップ")
                continue
        
        # フェーズ2: シチュエーション別質問（バッチ処理で効率化）
        print("\n=== Phase 2: Generating situational questions (batched) ===")
        phase2_count = min(600, target_size - len(all_intents))
        
        situations = [
            "初めてトレーラーハウスの購入を検討している",
            "事業用（宿泊施設・カフェなど）として利用したい",
            "既存の土地に設置したい",
            "中古トレーラーハウスを探している",
            "投資用物件として運用したい"
        ]
        
        situational_qas = self.generate_situational_questions_batch(
            base_qa, situations, phase2_count
        )
        
        for sqa in situational_qas[:phase2_count]:
            intent = {
                "tag": f"faq_sit_{len(all_intents):05d}",
                "category": sqa.get("category", "一般"),
                "patterns": [sqa["question"]],
                "responses": ["この質問については、具体的な状況により回答が異なります。詳細をお聞かせいただければ、より正確なアドバイスができます。"],
                "context": {"situation": sqa.get('situation', '')}
            }
            all_intents.append(intent)
            
            if len(all_intents) % SAVE_INTERVAL == 0:
                self.generated_data["intents"] = all_intents
                self.save_to_file("trailer_house_faq_checkpoint.json")
        
        # フェーズ3: 残りを基本QAの追加バリエーションで補充
        if len(all_intents) < target_size:
            print(f"\n=== Phase 3: Adding variations to reach {target_size} ===")
            remaining = target_size - len(all_intents)
            
            for i in tqdm(range(remaining), desc="Adding variations"):
                base_idx = i % len(base_qa)
                qa = base_qa[base_idx]
                
                try:
                    # 簡易バリエーション（APIコールなし）
                    variations = [
                        qa["question"],
                        f"{qa['question']}について教えて",
                        f"{qa['question']} 知りたい",
                        f"{qa['question']} 詳細"
                    ]
                    
                    intent = {
                        "tag": f"faq_extra_{len(all_intents):05d}",
                        "category": qa.get("category", "一般"),
                        "patterns": variations,
                        "responses": [qa["answer"]],
                        "context": {"generated": "simple"}
                    }
                    all_intents.append(intent)
                    
                    if len(all_intents) % SAVE_INTERVAL == 0:
                        self.generated_data["intents"] = all_intents
                        self.save_to_file("trailer_house_faq_checkpoint.json")
                        
                except Exception as e:
                    print(f"⚠️ エラー: {e}")
                    continue
        
        # 最終データの構築
        self.generated_data["metadata"]["total_questions"] = len(all_intents)
        self.generated_data["intents"] = all_intents[:target_size]
        
        return self.generated_data
    
    def save_to_file(self, filename: str = "trailer_house_faq_2000.json"):
        """
        生成したデータをJSONファイルに保存
        """
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.generated_data, f, ensure_ascii=False, indent=2)
        print(f"\n✅ Saved {len(self.generated_data['intents'])} intents to {filename}")
        
    def print_statistics(self):
        """
        生成されたデータの統計情報を表示
        """
        print("\n=== Generation Statistics ===")
        print(f"Total intents: {len(self.generated_data['intents'])}")
        
        # カテゴリ別集計
        category_count = {}
        for intent in self.generated_data['intents']:
            cat = intent.get('category', '未分類')
            category_count[cat] = category_count.get(cat, 0) + 1
        
        print("\nCategory breakdown:")
        for cat, count in sorted(category_count.items()):
            print(f"  {cat}: {count} intents")

# ベースQAファイルの作成
def create_base_qa_file():
    """
    50のベースQAを含むJSONファイルを作成
    """
    base_qa = [
        {
            "question": "トレーラーハウスは建築物ですか？車両ですか？",
            "answer": "特定の条件を満たせば「車両」、満たさなければ「建築物」として扱われます。車両扱いとなるためには、①公道を走行できる、②随時かつ任意に移動できる、③水道や電気などの配線・配管が工具を使わずに着脱できる、の3つの要件をすべて満たす必要があります。",
            "category": "法令・手続き"
        },
        {
            "question": "建築確認申請は必要ですか？",
            "answer": "車両扱いの場合は不要ですが、建築物扱いの場合は必要です。建築物として扱われる場合でも、都市計画区域内に設置する場合などは建築確認が必要になります。",
            "category": "法令・手続き"
        },
        {
            "question": "設置場所に制限はありますか？",
            "answer": "車両扱いの場合、原則として家を建てられない土地（例：市街化調整区域、原野、雑種地）にも設置できる可能性が広がります。ただし、農地に設置するには農地転用の手続きが必要です。",
            "category": "法令・手続き"
        },
        {
            "question": "固定資産税はかかりますか？",
            "answer": "車両扱いの場合はかかりません。トレーラーハウスは動産（車両）とみなされるため、固定資産税の課税対象外です。",
            "category": "税金・費用"
        },
        {
            "question": "本体価格の相場はいくらくらいですか？",
            "answer": "メーカーや仕様によりますが、本体価格の目安は400万円〜1,200万円程度です。簡易的なものであれば300万円台から、フルオーダーに近い高級仕様になると1,500万円以上になることもあります。",
            "category": "税金・費用"
        },
        {
            "question": "注文してから納品までどのくらいかかりますか？",
            "answer": "一般的に、契約から納品までは約2〜4ヶ月程度です。メーカーの生産状況や仕様の複雑さによって変動します。",
            "category": "設置・運用"
        },
        {
            "question": "断熱性や耐震性は大丈夫ですか？",
            "answer": "メーカーによって性能は異なります。最近では、北海道や沖縄などの過酷な環境にも対応できるよう、高い断熱性能や耐風圧性能を持った製品も増えています。メーカーに確認しましょう。",
            "category": "設置・運用"
        },
        {
            "question": "メンテナンスはどのくらい必要ですか？",
            "answer": "一般的な家屋と同様に、外壁の塗り替えやシーリング補修、屋根のメンテナンスが必要です。また、車両部分（シャーシ、タイヤ、ブレーキなど）の定期的な点検・整備も欠かせません。",
            "category": "メンテナンス"
        },
        {
            "question": "デザインは自由に選べますか？",
            "answer": "はい、多くのメーカーでカスタマイズが可能です。外観の色や素材、内装のレイアウトなどを選ぶことができます。",
            "category": "カスタマイズ"
        },
        {
            "question": "中古のトレーラーハウスを購入する場合の注意点は？",
            "answer": "車両としての状態（車検の有無、走行装置の状態）や、過去の改造歴、書類の有無などを専門業者にしっかりと確認してもらいましょう。",
            "category": "購入・販売"
        },
        {
            "question": "事業用（宿泊施設など）として使いたい場合、どんな許可が必要ですか？",
            "answer": "簡易宿所営業の許可（旅館業法）を保健所に申請する必要があります。また、消防法に基づく消火器の設置や避難経路の確保も義務付けられます。",
            "category": "法令・手続き"
        },
        {
            "question": "自治体ごとにルールは違いますか？",
            "answer": "はい。トレーラーハウスの扱いや設置に関する条例は自治体によって異なります。設置を検討する際は、必ず事前に該当する自治体の窓口で相談・確認することが重要です。",
            "category": "法令・手続き"
        },
        {
            "question": "一度設置したら、絶対に移動できないのですか？",
            "answer": "車両扱いであれば、移動は可能です。ただし、移動のたびに牽引車の手配や輸送経路の確認（特殊車両通行許可が必要な場合あり）が必要になります。",
            "category": "設置・運用"
        },
        {
            "question": "トレーラーハウスを店舗やオフィスにする場合、用途地域の制限は受けますか？",
            "answer": "車両扱いであれば、原則として受けません。しかし、建築物とみなされる設置方法（固定設置など）をとった場合は、その地域の用途制限に従う必要があります。",
            "category": "法令・手続き"
        },
        {
            "question": "トレーラーハウスを駐車場に置くことはできますか？",
            "answer": "駐車場の所有者の許可があれば可能ですが、用途地域によっては駐車場での宿泊が条例で禁止されている場合があるので注意が必要です。",
            "category": "設置・運用"
        },
        {
            "question": "土地を購入してトレーラーハウスを置く場合、土地の登記はどうなりますか？",
            "answer": "トレーラーハウス自体は動産（車両）のため、土地の登記には影響しません。建物の登記のように、トレーラーハウスを不動産として登記することはできません。",
            "category": "法令・手続き"
        },
        {
            "question": "災害時に仮設住宅として利用する場合の手続きは？",
            "answer": "災害救助法に基づき、自治体が主体となって設置するケースが一般的です。個人が所有するトレーラーハウスを被災地に提供する場合は、自治体の受け入れ態勢や支援制度を確認する必要があります。",
            "category": "災害・安全"
        },
        {
            "question": "自宅の庭にトレーラーハウスを置く場合、何か手続きは必要ですか？",
            "answer": "車両扱いの要件を満たしていれば、建築確認申請は不要です。ただし、固定資産税の対象となる「家屋」とみなされる設置方法（基礎で固定するなど）をとった場合は、市区町村への手続きが必要になる可能性があります。",
            "category": "法令・手続き"
        },
        {
            "question": "トレーラーハウスはリース契約できますか？",
            "answer": "はい、可能です。事業用などではリースを利用するケースもあります。",
            "category": "購入・販売"
        },
        {
            "question": "メーカー保証はありますか？",
            "answer": "あります。期間や内容はメーカーによって異なりますが、一般的に1年間の保証が付けられていることが多いです。",
            "category": "購入・販売"
        },
        {
            "question": "不動産取得税はかかりますか？",
            "answer": "車両扱いの場合はかかりません。",
            "category": "税金・費用"
        },
        {
            "question": "自動車税はかかりますか？",
            "answer": "ケースによります。車検付きで大型のトレーラーハウスの場合はかかるものもありますが、サイズによっては固定資産税も自動車税もかからない場合があります。詳細は専門家への相談をおすすめします。",
            "category": "税金・費用"
        },
        {
            "question": "減価償却は何年でできますか？",
            "answer": "法定耐用年数は4年です。トレーラーハウスは法律上「車両」に分類されるためです。",
            "category": "税金・費用"
        },
        {
            "question": "本体価格以外にかかる費用は？",
            "answer": "運送費（陸送費）、電気・ガス・上下水道の工事費用、各種申請にかかる費用（旅館業許可申請など）が別途必要です。",
            "category": "税金・費用"
        },
        {
            "question": "設置費用（工事費）の目安は？",
            "answer": "50万円〜150万円程度が目安です。電気や水道の引き込み工事、レベル調整などの基礎工事が含まれます。",
            "category": "税金・費用"
        },
        {
            "question": "支払い方法は？",
            "answer": "現金一括払いが基本ですが、メーカーによってはローンやリースでの契約も可能な場合があります。多くの場合、契約時に総額の30％、着工時に50％、納品時に残額という分割払いのスケジュールが一般的です。",
            "category": "購入・販売"
        },
        {
            "question": "中古市場はありますか？",
            "answer": "はい、あります。トレーラーハウスは移動が可能なため、中古車のように売買される市場が存在します。状態が良ければ、購入価格の半額以上で取引されることもあります。",
            "category": "購入・販売"
        },
        {
            "question": "保険には入れますか？",
            "answer": "入れます。一般住宅と同様に、火災保険や家財保険への加入が可能です。",
            "category": "税金・費用"
        },
        {
            "question": "ローンの金利はどのくらいですか？",
            "answer": "一般的な住宅ローンとは異なり、オートローンやプロパーローン（事業用）の適用となるため、金利は借入額や返済期間、信用情報によって異なります。",
            "category": "税金・費用"
        },
        {
            "question": "事業用として運用する場合の利回りは？",
            "answer": "立地や運営方法によりますが、目安として利回り10〜15％程度を見込めるケースもあります。",
            "category": "税金・費用"
        },
        {
            "question": "見積もりは無料ですか？",
            "answer": "多くのメーカーで、初回の相談や見積もりは無料です。",
            "category": "購入・販売"
        },
        {
            "question": "中古トレーラーハウスの耐用年数はどう計算しますか？",
            "answer": "中古自動車と同じ計算方法で求めます。法定耐用年数（4年）を経過しているかどうかで計算式が変わります。",
            "category": "税金・費用"
        },
        {
            "question": "自分で設置場所まで移動できますか？",
            "answer": "基本的には、専門業者による牽引車での陸送となります。事前に国土交通省への特殊車両通行許可申請が必要な場合もあります。",
            "category": "設置・運用"
        },
        {
            "question": "どんな土地でも設置できますか？",
            "answer": "設置には、牽引車が進入できる十分な幅の道路や、トレーラーハウスを据え付けるための平坦なスペースが必要です。事前の現地調査で輸送ルートの確認が行われます。",
            "category": "設置・運用"
        },
        {
            "question": "電気や水道はどうやって確保しますか？",
            "answer": "設置場所で、電力会社やガス会社、水道局と契約し、工事を行って配管・配線を接続します。",
            "category": "設置・運用"
        },
        {
            "question": "トレーラーハウスは何年くらい住めますか？",
            "answer": "適切なメンテナンスを行えば、20年以上使用することは可能です。",
            "category": "メンテナンス"
        },
        {
            "question": "インターネットは使えますか？",
            "answer": "設置場所で通信環境を整えれば使えます。最近のトレーラーハウスホテルなどでは、各部屋にWi-Fiを完備している例も多いです。",
            "category": "生活・快適性"
        },
        {
            "question": "トレーラーハウスホテルのチェックインやチェックアウトの方法は？",
            "answer": "施設によって異なりますが、無人フロントシステムやタブレット端末を導入している施設が増えています。",
            "category": "設置・運用"
        },
        {
            "question": "防音対策はされていますか？",
            "answer": "メーカーやグレードによります。宿泊施設などで使用する場合は、隣室や外部への音漏れに配慮した防音仕様を選ぶとよいでしょう。",
            "category": "生活・快適性"
        },
        {
            "question": "ペットと一緒に住めますか？",
            "answer": "可能です。ただし、賃貸物件に置く場合や、ホテルとして運用する場合は、それぞれのルールに従う必要があります。",
            "category": "生活・快適性"
        },
        {
            "question": "トレーラーハウスを置くために、土地の整地は必要ですか？",
            "answer": "必要です。トレーラーハウスを安定して設置するためには、ある程度平らな地面が必要です。必要に応じて、砕石を敷いたり、コンクリートブロックを設置するなどの整地工事が行われることがあります。",
            "category": "設置・運用"
        },
        {
            "question": "トレーラーハウス内で洗濯はできますか？",
            "answer": "多くのトレーラーハウスには、洗濯機を設置するスペースが確保されています。ホテルタイプでは、部屋に洗濯機が備え付けられていることもあります。",
            "category": "生活・快適性"
        },
        {
            "question": "駐車場は必要ですか？",
            "answer": "自家用車をお持ちの場合は、トレーラーハウスとは別に駐車スペースを確保する必要があります。ホテルの場合、1部屋につき1台分の駐車場を用意している施設が多いです。",
            "category": "設置・運用"
        },
        {
            "question": "トレーラーハウスをレンタルすることはできますか？",
            "answer": "はい、レンタル事業を行っている会社もあります。イベント出店や期間限定の店舗、別荘としての利用など、様々な用途でレンタルが可能です。",
            "category": "購入・販売"
        },
        {
            "question": "トレーラーハウスは環境に優しいのですか？",
            "answer": "基礎工事が少なく、撤去時にも廃材が少ないことから、環境負荷が低いとされています。また、太陽光発電などを組み合わせることで、よりエコロジーな運用も可能です。",
            "category": "設置・運用"
        },
        {
            "question": "トレーラーハウスを置く際、近隣への挨拶は必要ですか？",
            "answer": "一般的な家を建てる場合と同様に、近隣住民への挨拶や説明をしておくことで、後々のトラブルを防ぐことができます。",
            "category": "設置・運用"
        },
        {
            "question": "地震の時はどうすればいいですか？",
            "answer": "トレーラーハウスは車両であるため、揺れに対してある程度柔軟に追従します。しかし、転倒防止の措置（ジャッキの固定など）は日頃から確認しておきましょう。また、内部の家具の固定など、一般的な地震対策も必要です。",
            "category": "災害・安全"
        },
        {
            "question": "信頼できるメーカーや販売店の選び方は？",
            "answer": "以下のポイントを確認するとよいでしょう。①車両総重量や最大積載量を明確に説明しているか、②ブレーキなどの制動装置が信頼できるか、③保証内容やアフターフォローが充実しているか、④実際の施工事例や口コミが多いか、⑤疑問に対して曖昧な回答をせず、しっかり説明してくれるか",
            "category": "購入・販売"
        },
        {
            "question": "ナンバープレートと車検は必要ですか？",
            "answer": "車両として公道を走行するためには、ナンバープレートの取得と車検（重量によっては車検不要の場合も）への適合が必要です。車両総重量によって区分が分かれます。",
            "category": "法令・手続き"
        },
        {
            "question": "牽引するために必要な免許は？",
            "answer": "トレーラーハウスの車両総重量が750kgを超える場合は、牽引するための免許（例：牽引第二種免許など、総重量や牽引する車両によって必要な免許が異なります）が必要になる場合があります。詳しくは警察や運転免許センターでご確認ください。",
            "category": "法令・手続き"
        }
    ]
    
    with open('base_qa_50.json', 'w', encoding='utf-8') as f:
        json.dump(base_qa, f, ensure_ascii=False, indent=2)
    
    print(f"✅ Created base_qa_50.json with {len(base_qa)} questions")
    return 'base_qa_50.json'

# メイン実行
def main():
    """
    メイン実行関数
    """
    import os
    
    # APIキーの設定
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        api_key = input("🔑 DeepSeek APIキーを入力してください: ").strip()
    
    if not api_key:
        print("❌ APIキーが設定されていません")
        return
    
    # ベースQAファイルの作成
    base_qa_file = create_base_qa_file()
    
    # ジェネレーターの初期化
    generator = TrailerHouseFAQGenerator(api_key=api_key, model="deepseek-chat")
    
    # 2000件のデータ生成
    print("\n🚀 Starting generation of 2000 FAQ items...")
    print("💾 50件ごとに自動保存されます")
    print("🛑 Ctrl+Cで中断すると、その時点までのデータを保存します")
    print("-" * 50)
    
    start_time = time.time()
    
    try:
        data = generator.generate_all(base_qa_file, target_size=2000)
        
        # 最終保存
        generator.save_to_file("trailer_house_faq_2000.json")
        generator.print_statistics()
        
        elapsed_time = time.time() - start_time
        print(f"\n⏱️  Total generation time: {elapsed_time/60:.1f} minutes")
        
    except Exception as e:
        print(f"\n❌ エラーが発生しました: {e}")
        print("💾 途中までのデータを保存しています...")
        generator.save_to_file("trailer_house_faq_error_recovery.json")

if __name__ == "__main__":
    main()