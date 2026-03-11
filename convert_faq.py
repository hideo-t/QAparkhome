"""
trailer_house_faq_2000.json → qa_data.json 変換スクリプト
========================================================
使い方：
  python convert_faq.py

入力: trailer_house_faq_2000.json
出力: qa_data.json（chatbot用）
"""

import json

INPUT  = "trailer_house_faq_2000.json"
OUTPUT = "qa_data.json"

def convert():
    with open(INPUT, encoding='utf-8') as f:
        data = json.load(f)

    intents = data.get("intents", [])
    result = []

    for item in intents:
        category = item.get("category", "")
        patterns  = item.get("patterns", [])
        responses = item.get("responses", [])
        tag       = item.get("tag", "")

        if not patterns or not responses:
            continue

        # ① メインQ&A（patterns[0] × responses[0]）
        result.append({
            "id":       tag,
            "category": category,
            "question": patterns[0],
            "answer":   responses[0],
        })

        # ② 追加パターンも全部Q&Aとして展開（検索ヒット率UP）
        for i, pattern in enumerate(patterns[1:], 1):
            result.append({
                "id":       f"{tag}_p{i}",
                "category": category,
                "question": pattern,
                "answer":   responses[0],  # 回答は同じ
            })

    with open(OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    # 集計
    cats = {}
    for item in result:
        c = item["category"]
        cats[c] = cats.get(c, 0) + 1

    print(f"✅ 変換完了: {len(result)}問 → {OUTPUT}")
    print(f"\n【カテゴリ別】")
    for c, n in sorted(cats.items(), key=lambda x: -x[1]):
        print(f"  {c:<18} {n:>5}問")

if __name__ == "__main__":
    convert()
