"""브라우저에서 나눠 받은 확률표 조각(JSON 텍스트)을 이어 붙여 data/probability.json 에 합친다.

사용법: python merge_probability.py 조각1.txt 조각2.txt ...
"""
import json
import os
import sys
from datetime import date

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, "data", "probability.json")

text = "".join(open(p, encoding="utf-8").read() for p in sys.argv[1:])
new_items = json.loads(text)
with open(PATH, encoding="utf-8") as f:
    data = json.load(f)
added = [k for k in new_items if k not in data["items"]]
data["items"].update(new_items)
data["_fetched"] = date.today().isoformat()
with open(PATH, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=1)
print(f"새 확률표 {len(added)}개 추가, 전체 {len(data['items'])}개")
