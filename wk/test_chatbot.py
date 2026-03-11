"""
チャットbot 自動テストスクリプト
================================
KBからテスト問題を自動生成 → Claude APIに投げる → 正答率を評価

使い方：
  python test_chatbot.py

必要ファイル：
  - qa_data.json（KBデータ）

出力：
  - test_report.txt（詳細レポート）
  - コンソールに正答率サマリー
"""

import anthropic
import json
import random
import time
import os
from datetime import datetime

# ============================================================
# 設定
# ============================================================
API_KEY   = os.environ.get("ANTHROPIC_API_KEY", "ここにAPIキーを入れる")
MODEL     = "claude-haiku-4-5-20251001"  # 評価はHaikuで節約
KB_FILE   = "qa_data.json"
REPORT    = "test_report.txt"
TEST_COUNT = 30   # テスト問題数（多いほど精度UP・コストUP）
TOP_K      = 8    # RAGで渡す件数

SYSTEM_PROMPT = """あなたはPark Homes Okinawa（トレーラーハウスメーカー）の専門AIアシスタントです。
沖縄でのトレーラーハウスの購入・設置・活用に関するあらゆる質問に、わかりやすく親切に回答してください。"""

# ============================================================
# RAG検索（index.htmlと同じロジック）
# ============================================================
def tokenize(text):
    import re
    text = re.sub(r'[？！。、「」・…『』【】\(\)（）]', ' ', text or '')
    return [t for t in text.split() if len(t) >= 2]

def bigrams(text):
    clean = ''.join((text or '').split())
    return [clean[i:i+2] for i in range(len(clean)-1)]

def search_kb(kb, query, top_k=8):
    qt  = tokenize(query)
    qbg = bigrams(query)
    scored = []
    for item in kb:
        q_tokens = tokenize(item['question'])
        a_tokens = tokenize(item.get('answer', ''))
        ibg = bigrams(item['question'])
        score = 0
        if item['question'] == query: score += 20
        for bg in qbg:
            if bg in ibg: score += 3
        for q in qt:
            for t in q_tokens: score += 4 if t==q else (2 if q in t or t in q else 0)
            for t in a_tokens: score += 2 if t==q else (1 if q in t or t in q else 0)
        cat = item.get('category', '')
        if any(k in query for k in ['税','費用','価格']) and '税' in cat: score += 2
        if any(k in query for k in ['法','許可','申請']) and '法' in cat: score += 2
        if any(k in query for k in ['台風','沖縄','離島']) and '沖縄' in cat: score += 3
        if score > 0:
            scored.append({**item, 'score': score})
    scored.sort(key=lambda x: -x['score'])
    seen, result = set(), []
    for item in scored:
        key = (item.get('answer',''))[:40]
        if key not in seen:
            seen.add(key)
            result.append(item)
        if len(result) >= top_k: break
    return result

# ============================================================
# 評価ロジック（Claude Haikuが正誤を判定）
# ============================================================
JUDGE_PROMPT = """以下のQ&Aペアについて、「回答」が「正解」の内容を含んでいるか評価してください。

質問：{question}
正解：{expected}
回答：{actual}

評価基準：
- 正解の主要なポイントが含まれていれば「OK」
- 全く違う内容・明らかに誤りなら「NG」
- 部分的に合っていれば「PARTIAL」

必ず以下のJSON形式のみで出力（説明不要）：
{{"result": "OK" または "PARTIAL" または "NG", "reason": "一言で理由"}}"""

def judge(client, question, expected, actual):
    try:
        msg = client.messages.create(
            model=MODEL,
            max_tokens=200,
            messages=[{"role": "user", "content": JUDGE_PROMPT.format(
                question=question, expected=expected, actual=actual
            )}]
        )
        raw = msg.content[0].text.strip()
        raw = raw.replace('```json','').replace('```','').strip()
        return json.loads(raw)
    except:
        return {"result": "ERROR", "reason": "判定失敗"}

# ============================================================
# メイン
# ============================================================
def main():
    print("=" * 55)
    print("  Park Homes チャットbot 自動テスト")
    print(f"  開始: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 55)

    if API_KEY == "ここにAPIキーを入れる":
        print("❌ APIキーが設定されていません")
        return

    # KBロード
    with open(KB_FILE, encoding='utf-8') as f:
        kb = json.load(f)
    print(f"✅ KB読み込み: {len(kb)}問")

    # テスト問題をランダムサンプリング（カテゴリ均等）
    cats = {}
    for item in kb:
        c = item.get('category','不明')
        cats.setdefault(c, []).append(item)

    test_items = []
    per_cat = max(1, TEST_COUNT // len(cats))
    for c, items in cats.items():
        sampled = random.sample(items, min(per_cat, len(items)))
        test_items.extend(sampled)
    test_items = test_items[:TEST_COUNT]
    random.shuffle(test_items)
    print(f"✅ テスト問題: {len(test_items)}問\n")

    client = anthropic.Anthropic(api_key=API_KEY)
    results = []

    for i, item in enumerate(test_items, 1):
        q        = item['question']
        expected = item['answer']
        cat      = item.get('category','')

        print(f"[{i:02d}/{len(test_items)}] {q[:40]}...")

        # RAG検索
        hits = search_kb(kb, q, TOP_K)
        ctx  = '\n\n【関連専門知識】\n' + '\n\n'.join(
            f"[{j+1}][{h['category']}] Q:{h['question']}\n    A:{h['answer']}"
            for j, h in enumerate(hits)
        ) if hits else ''

        # Claude API呼び出し
        try:
            msg = client.messages.create(
                model=MODEL,
                max_tokens=512,
                system=SYSTEM_PROMPT + ctx,
                messages=[{"role": "user", "content": q}]
            )
            actual = msg.content[0].text.strip()
        except Exception as e:
            actual = f"ERROR: {e}"

        # 正誤判定
        verdict = judge(client, q, expected, actual)
        result  = verdict.get('result', 'ERROR')
        reason  = verdict.get('reason', '')

        mark = '✅' if result=='OK' else ('⚠️' if result=='PARTIAL' else '❌')
        print(f"      {mark} {result} - {reason}")

        results.append({
            "no": i, "category": cat, "question": q,
            "expected": expected, "actual": actual,
            "result": result, "reason": reason
        })
        time.sleep(0.5)

    # ============================================================
    # 集計
    # ============================================================
    ok      = sum(1 for r in results if r['result']=='OK')
    partial = sum(1 for r in results if r['result']=='PARTIAL')
    ng      = sum(1 for r in results if r['result']=='NG')
    total   = len(results)
    score   = (ok + partial*0.5) / total * 100

    print(f"\n{'='*55}")
    print(f"  【テスト結果】")
    print(f"  正解(OK)    : {ok}問 ({ok/total:.0%})")
    print(f"  部分正解    : {partial}問 ({partial/total:.0%})")
    print(f"  不正解(NG)  : {ng}問 ({ng/total:.0%})")
    print(f"  総合スコア  : {score:.1f}点 / 100点")
    print(f"{'='*55}")

    # カテゴリ別集計
    cat_stats = {}
    for r in results:
        c = r['category']
        cat_stats.setdefault(c, {'OK':0,'PARTIAL':0,'NG':0,'total':0})
        cat_stats[c]['total'] += 1
        key = r['result'] if r['result'] in ['OK','PARTIAL','NG'] else 'NG'
        cat_stats[c][key] += 1

    print(f"\n【カテゴリ別スコア】")
    for c, s in sorted(cat_stats.items()):
        sc = (s['OK'] + s['PARTIAL']*0.5) / s['total'] * 100
        bar = '█' * int(sc//10) + '░' * (10-int(sc//10))
        print(f"  {c:<16} {bar} {sc:.0f}点 ({s['total']}問)")

    # レポート保存
    with open(REPORT, 'w', encoding='utf-8') as f:
        f.write(f"Park Homes チャットbot テストレポート\n")
        f.write(f"生成日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"総合スコア: {score:.1f}点\n\n")
        for r in results:
            mark = '✅' if r['result']=='OK' else ('⚠️' if r['result']=='PARTIAL' else '❌')
            f.write(f"{'─'*50}\n")
            f.write(f"[{r['no']:02d}] {mark} {r['result']} | {r['category']}\n")
            f.write(f"Q: {r['question']}\n")
            f.write(f"正解: {r['expected'][:100]}\n")
            f.write(f"回答: {r['actual'][:200]}\n")
            f.write(f"判定理由: {r['reason']}\n\n")

    print(f"\n📄 詳細レポート → {REPORT}")
    print(f"  終了: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()
