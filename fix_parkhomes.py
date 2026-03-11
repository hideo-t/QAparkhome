"""
park_homes_top.html（またはindex.html）の情報を正式情報に更新するスクリプト
使い方：
  1. このファイルをindex.htmlと同じフォルダに置く
  2. python fix_parkhomes.py を実行
  3. 修正済みの index.html が上書き保存される
  4. GitHubにpush（またはアップロード）
"""

import re

# ===== 修正対象ファイル =====
TARGET = "index.html"

# ===== 正式情報 =====
CORRECT_TEL        = "098-856-6666"
CORRECT_TEL_LINK   = "0988566666"
CORRECT_ADDRESS    = "沖縄県豊見城市豊崎1-1223"
CORRECT_COMPANY    = "株式会社パークホームズ オキナワ"
CORRECT_HOURS      = "受付時間：9:00〜18:00（土日祝休）"

with open(TARGET, "r", encoding="utf-8") as f:
    html = f.read()

original = html

# 1. 電話番号ダミー → 正式番号
html = html.replace("098-000-0000", CORRECT_TEL)
html = html.replace("0980000000",   CORRECT_TEL_LINK)
html = html.replace("098-000-000",  CORRECT_TEL)   # 念のため

# 2. 住所ダミー → 正式住所
html = html.replace("沖縄県〇〇市〇〇町1-1-1", CORRECT_ADDRESS)
html = html.replace("沖縄県○○市○○町1-1-1",  CORRECT_ADDRESS)

# 3. tel:リンクも修正
html = re.sub(r'tel:09800+\d*', f'tel:{CORRECT_TEL_LINK}', html)

# 4. 受付時間（土日祝休が抜けている場合）
html = html.replace("受付時間 9:00〜18:00", "受付時間：9:00〜18:00（土日祝休）")
html = html.replace("受付時間：9:00〜18:00（土日祝休）（土日祝休）", "受付時間：9:00〜18:00（土日祝休）")  # 二重防止

# 5. 電話番号の文字ズレ修正（ナビ・ヘッダーのtel表示をflex整列に）
#    ナビ内の電話番号部分をインラインスタイルで確実に揃える
html = html.replace(
    f'📞 {CORRECT_TEL}',
    f'<span style="display:inline-flex;align-items:center;gap:4px;white-space:nowrap;">📞&nbsp;{CORRECT_TEL}</span>'
)
# 既に置換済みの二重適用防止
html = html.replace(
    f'<span style="display:inline-flex;align-items:center;gap:4px;white-space:nowrap;">📞&nbsp;{CORRECT_TEL}</span>' * 2,
    f'<span style="display:inline-flex;align-items:center;gap:4px;white-space:nowrap;">📞&nbsp;{CORRECT_TEL}</span>'
)

with open(TARGET, "w", encoding="utf-8") as f:
    f.write(html)

# 変更箇所のサマリー
changes = 0
for a, b in zip(original.splitlines(), html.splitlines()):
    if a != b:
        changes += 1

print(f"✅ 修正完了：{changes}行を更新しました → {TARGET}")
print(f"   電話番号  : {CORRECT_TEL}")
print(f"   住所      : {CORRECT_ADDRESS}")
print(f"   会社名    : {CORRECT_COMPANY}")
print()
print("次のステップ：")
print("  git add index.html")
print("  git commit -m 'fix: 正式情報・電話番号表示修正'")
print("  git push")
