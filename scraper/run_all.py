"""2단계: 웹샵의 모든 확률형 상품을 계산해 output/results.json 으로 저장."""
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

import datacenter
import shop
from calc import Calculator, DISCOUNTS, net
from extremes import Extremes

KST = timezone(timedelta(hours=9))
# BP로 환산할 수 없는 상품 (계산에서 제외)
NON_BP_KEYWORDS = ["시뮬레이션권"]


def write_site(out, prob_items):
    """site/index.html 안의 DATA-START~DATA-END 자리에 데이터를 직접 넣는다.
    (별도 파일을 불러오지 않으므로 index.html 하나만 열어도 상품이 보인다)"""
    data = site_data(out, prob_items)
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    path = os.path.join(ROOT, "site", "index.html")
    with open(path, encoding="utf-8") as f:
        page = f.read()
    start, end = "/*DATA-START*/", "/*DATA-END*/"
    i, k = page.index(start) + len(start), page.index(end)
    page = page[:i] + "window.FC_DATA = " + payload + ";" + page[k:]
    with open(path, "w", encoding="utf-8") as f:
        f.write(page)
    for old in ("data.json", "data.js"):
        p = os.path.join(ROOT, "site", old)
        if os.path.exists(p):
            os.remove(p)


def site_data(out, prob_items):
    """사이트용 요약. 각 보상 줄(row)은 w(기대 개수)·bp·player 를 가진다.
    실수령 = w × (bp + player × (1 − 0.4 × (1 − 할인율)))"""
    # 최고/최저 계산용: 이름 -> 기대값
    ev_map = {}
    for p in out["products"]:
        for c in p["parts"]:
            ev_map[c["name"]] = {"bp": c["bp"], "player": c["player"]}
            for b in c.get("breakdown") or []:
                ev_map[b["name"]] = {"bp": b["bp"], "player": b["player"]}
    ext = Extremes(prob_items, out["packs"], lambda n: ev_map[n])

    products = []
    for p in out["products"]:
        rows = []
        for c in p["parts"]:
            if c.get("breakdown"):
                for b in c["breakdown"]:
                    rows.append({"name": b["name"], "from": c["name"], "prob": b["prob"],
                                 "amount": b["amount"] * c["count"],
                                 "w": b["prob"] * b["amount"] * c["count"],
                                 "bp": b["bp"], "player": b["player"]})
            else:
                rows.append({"name": c["name"], "from": None, "prob": 1.0, "amount": c["count"],
                             "w": c["count"], "bp": c["bp"], "player": c["player"]})
        products.append({
            "pid": p["pid"], "name": p["name"], "price_fc": p["price_fc"], "period": p["period"],
            "limit": p.get("limit"), "limit_text": p.get("limit_text", ""),
            "status": p.get("status", "ok"), "reason": p.get("reason"),
            "components": p["components"], "rows": rows,
            # 할인 종류별 [최저, 최고] 실수령 BP
            "range": ext.product(p["components"]) if p.get("status", "ok") == "ok" else None,
        })
    return {"updated_at": out["updated_at"], "probability_fetched": out["probability_fetched"],
            "products": products, "skipped": out["skipped"]}


def main():
    started = time.time()
    print("웹샵 상품 목록 읽는 중...")
    products = shop.fetch_all()
    print(f"  상품 {len(products)}개")

    with open(os.path.join(ROOT, "data", "probability.json"), encoding="utf-8") as f:
        prob_file = json.load(f)
    prob = prob_file["items"]

    seasons = datacenter.season_ids()
    calc = Calculator(prob, seasons)

    results, skipped = [], []
    for p in products:
        if any(k in p["name"] for k in NON_BP_KEYWORDS):
            skipped.append({"name": p["name"], "reason": "BP로 환산할 수 없는 상품"})
            continue
        print(f"\n[{p['name']}] {p['price_fc']:,} FC")
        parts, total, problem = [], {"bp": 0.0, "player": 0.0}, None
        for c in p["components"]:
            try:
                e = calc.ev(c["name"])
            except (KeyError, ValueError) as err:
                problem = str(err)
                break
            total["bp"] += c["count"] * e["bp"]
            total["player"] += c["count"] * e["player"]
            parts.append({"name": c["name"], "count": c["count"], "bp": e["bp"], "player": e["player"],
                          "breakdown": e.get("parts")})
        if problem:
            # 새 상품이라 확률표가 아직 없으면 '확률표 대기 중'으로 남긴다
            print(f"  확률표 대기 중: {problem}")
            results.append({**p, "status": "waiting", "reason": problem, "per_fc": None, "parts": []})
            continue
        per_fc = {k: net(total, d) / p["price_fc"] for k, d in DISCOUNTS.items()}
        print("  1 FC당 BP: " + "  ".join(f"{k} {v:,.0f}" for k, v in per_fc.items()))
        results.append({**p, "status": "ok", "ev": total, "per_fc": per_fc, "parts": parts})

    results.sort(key=lambda r: -(r["per_fc"]["none"] if r["per_fc"] else -1))
    out = {
        "updated_at": datetime.now(KST).isoformat(timespec="minutes"),
        "probability_fetched": prob_file.get("_fetched"),
        "discounts": DISCOUNTS,
        "products": results,
        "skipped": skipped,
        "packs": calc.details,
    }
    os.makedirs(os.path.join(ROOT, "output"), exist_ok=True)
    with open(os.path.join(ROOT, "output", "results.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    # 확률표가 없는 새 상품 목록 → 자동 갱신이 알림(GitHub 이슈 = 이메일)을 보낼 때 쓴다
    waiting = [{"name": p["name"], "price_fc": p["price_fc"], "reason": p.get("reason")}
               for p in results if p.get("status") == "waiting"]
    with open(os.path.join(ROOT, "output", "missing.json"), "w", encoding="utf-8") as f:
        json.dump(waiting, f, ensure_ascii=False, indent=1)

    import site_build      # 붕어빵·열쇠 상점 결과와 함께 사이트에 넣는다
    site_build.build()
    print(f"\n완료: {len(results)}개 계산, {len(skipped)}개 제외, {time.time() - started:.0f}초")


if __name__ == "__main__":
    main()
