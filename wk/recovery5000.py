# recover_data.py
import json
import glob
from datetime import datetime

def recover_all_data():
    all_intents = []
    
    # 全てのJSONファイルをスキャン
    json_files = glob.glob("*.json")
    
    for file in json_files:
        if file == "base_qa_50.json":
            continue
            
        try:
            with open(file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            # 様々な形式に対応
            if isinstance(data, dict):
                if 'intents' in data:
                    all_intents.extend(data['intents'])
                    print(f"📄 {file}: {len(data['intents'])} インテント")
                elif 'questions' in data:
                    all_intents.extend(data['questions'])
                    print(f"📄 {file}: {len(data['questions'])} 質問")
            elif isinstance(data, list):
                all_intents.extend(data)
                print(f"📄 {file}: {len(data)} アイテム")
                
        except Exception as e:
            print(f"❌ {file}: 読み込みエラー - {e}")
    
    # 重複除去
    unique_intents = []
    seen = set()
    
    for intent in all_intents:
        # 簡易的な重複チェック
        intent_str = str(intent.get('patterns', [''])[0] if isinstance(intent, dict) else intent)
        if intent_str not in seen:
            seen.add(intent_str)
            unique_intents.append(intent)
    
    # リカバリーデータを保存
    recovered_data = {
        "metadata": {
            "version": "2.0",
            "generated_date": datetime.now().isoformat(),
            "total_questions": len(unique_intents),
            "language": "ja",
            "source": "recovered_from_interrupted_run"
        },
        "intents": unique_intents
    }
    
    with open('trailer_house_faq_recovered.json', 'w', encoding='utf-8') as f:
        json.dump(recovered_data, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ リカバリー完了: {len(unique_intents)} 件のデータを保存しました")
    return recovered_data

if __name__ == "__main__":
    data = recover_all_data()