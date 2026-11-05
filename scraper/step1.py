"""1단계: [10~11강 20%] 10~11강팩 or BP 패키지 하나만 계산해서 검증용 정답과 비교."""
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

import datacenter
import shop
from calc import Calculator, DISCOUNTS, net

TARGET = "[10~11강 20%] 10~11강팩 or BP 패키지"

REFERENCE = {
    "행운의 BP 카드 (400만~800만)": 4_810_000,
    "SPT, 26FSL 포함 Top Price 630 (11강, 114+)": 980_000_000,
    "26UP 포함 Top Price 270 (10강, 114+)": 855_000_000,
    "UC Top Price 60 (10강, 117+)": 709_000_000,
    "26UP Top Price 95 (11강, 114+)": 1_237_000_000,
    "UC Top Price 110 (11강, 117+)": 936_000_000,
}


def main():
    print("웹샵 상품 목록 읽는 중...")
    products = shop.fetch_all(max_pages=1)
    prod = next(p for p in products if p["name"] == TARGET)
    print(f"  {prod['name']} / {prod['price_fc']:,} FC / 구성품 {prod['components']}")

    with open(os.path.join(ROOT, "data", "probability.json"), encoding="utf-8") as f:
        prob = json.load(f)["items"]

    print("데이터센터 클래스 번호 읽는 중...")
    seasons = datacenter.season_ids()
    print(f"  클래스 {len(seasons)}개")

    calc = Calculator(prob, seasons)
    print("선수팩 시세 수집 중 (요청 간격 3초)...")

    box_name = prod["components"][0]["name"]
    box = calc.ev(box_name)

    print("\n=== 구성별 비교 (보상 1회 기준) ===")
    for part in box["parts"]:
        mine = part["bp"] + part["player"]
        ref = REFERENCE.get(part["name"])
        diff = f"{(mine / ref - 1) * 100:+.1f}%" if ref else ""
        print(f"  {part['prob']*100:8.4f}%  {part['name']:<45} 내 계산 {mine/1e8:7.3f}억  정답 {ref/1e8 if ref else 0:7.3f}억  {diff}")

    print("\n=== 1 FC당 BP ===")
    box_only = {k: net(box, d) / prod["price_fc"] for k, d in DISCOUNTS.items()}
    print("  [상자만, 정답과 같은 방식]  " + "  ".join(f"{k}: {v:,.0f}" for k, v in box_only.items()))
    print("  정답:                       none: 42,492  pc_top: 46,292")

    total = {"bp": 0.0, "player": 0.0}
    for c in prod["components"]:
        e = calc.ev(c["name"])
        total["bp"] += c["count"] * e["bp"]
        total["player"] += c["count"] * e["player"]
    full = {k: net(total, d) / prod["price_fc"] for k, d in DISCOUNTS.items()}
    print("  [보너스 팩 포함 전체 상품]  " + "  ".join(f"{k}: {v:,.0f}" for k, v in full.items()))

    out = {"product": prod, "box": box, "details": calc.details, "per_fc_box_only": box_only, "per_fc_full": full}
    os.makedirs(os.path.join(ROOT, "output"), exist_ok=True)
    with open(os.path.join(ROOT, "output", "step1_result.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

    print("\n=== 선수팩 상세 ===")
    for n, d in calc.details.items():
        print(f"  {n}: 후보 {d['pool_size']}명 (필요 {d['top_n']}), 빠진 순위 {d['missing_ranks']}, 확률합 {d['prob_sum']:.6f}, TOP1 {d['top3'][0] if d['top3'] else None}")


if __name__ == "__main__":
    main()
