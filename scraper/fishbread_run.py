"""붕어빵 속 SSS 계산 실행 → output/fishbread.json"""
import json
import os
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

import datacenter
from calc import Calculator, DISCOUNTS, net
from fishbread import board_average, optimal_per_draw, describe_policy, simulate_draws_per_board

# ---- 이벤트 규칙 (사용자 확인 + 웹상점 '전체 보상 안내') ----
# '붕어빵 아저씨의 깜짝 제안! 코인 붕어빵 틀': 황금(160)·팥(45) 교환 때 1회,
# 코인을 넣으면 넣은 만큼 그대로 돌려받고 + 확률표의 보너스 코인을 더 받는다(손해 없음).
# → 그 교환의 실제 코인 비용 = 필요 코인 − 보너스 코인 기대값
COIN_BONUS = {
    "황금 붕어빵 상자": "붕어빵 아저씨의 깜짝 제안! (프리미엄 코인 160개)",
    "[선수팩 80%] 팥 붕어빵 상자": "붕어빵 아저씨의 깜짝 제안! (프리미엄 코인 45개)",
}
COIN_SHOP = [  # (아이템, 필요 코인, 교환 제한 없음?)
    ("황금 붕어빵 상자", 160, True),
    ("특제 붕어빵 상자", 75, True),
    ("[선수팩 80%] 팥 붕어빵 상자", 45, False),   # 3회 제한
    ("26UP 11강 확정 + BP", 20, False),            # 2회 제한
    ("[스페셜SSS] 행운의 BP 카드 (4.5억~11억)", 15, True),
    ("[스페셜SS] 행운의 BP 카드 (1.5억~3.5억)", 5, True),
    ("[스페셜B] 행운의 BP 카드 (3000만~7000만)", 1, True),
]
SPECIAL = {
    "grades": ["SSS", "SS", "S", "A", "B"],
    "counts": [1, 2, 6, 10, 30],
    "items": {
        "SSS": ["[스페셜SSS][26UP 11강 기회] 상자", "[스페셜SSS] 행운의 BP 카드 (4.5억~11억)"],
        "SS": ["[스페셜SS][26UP 10강 기회] 상자", "[스페셜SS] 행운의 BP 카드 (1.5억~3.5억)"],
        "S": ["[스페셜S][26UP 10강 기회] 상자", "[스페셜S] 행운의 BP 카드 (9000만~2.1억)"],
        "A": ["[스페셜A][26UP 9강 기회] 상자", "[스페셜A] 행운의 BP 카드 (6000만~1.4억)"],
        "B": ["[스페셜B] 행운의 BP 카드 (3000만~7000만)"],
    },
    "coins": {"SSS": 15, "SS": 5, "S": 3, "A": 2, "B": 1},
    "lucky7": True,
    "tickets": [  # (상품 이름, 장 수, FC)
        ("스페셜 게임 참여권 1개", 1, 2100),
        ("[특별할인] 스페셜 게임 참여권 1개 (10회 제한)", 1, 1900),
        ("스페셜 게임 참여권 4개 묶음", 4, 7500),
        ("스페셜 게임 참여권 8개 묶음", 8, 14900),
    ],
}
NORMAL = {
    "grades": ["SSS", "A"],
    "counts": [9, 40],
    "items": {
        "SSS": ["[일반SSS][26UP 11강 기회] 상자", "[일반SSS] 행운의 BP 카드 (1.4억~2.8억)"],
        "A": ["[일반A] 행운의 BP 카드 (1800만~3600만)"],
    },
    "coins": {},   # 일반 게임은 코인 시스템이 없음 (사용자 확인) → 아이템으로만 계산
    "lucky7": False,   # 럭키 7은 스페셜 게임만 해당 (사용자 확인)
    "tickets": [
        ("일반 게임 참여권 1개", 1, 990),
        ("일반 게임 참여권 5개 묶음", 5, 4950),
    ],
}
LUCKY7_GRADE = "S"   # 7번 참여마다 스페셜 S등급 보상 1개


def main():
    t0 = time.time()
    with open(os.path.join(ROOT, "data", "probability.json"), encoding="utf-8") as f:
        prob = json.load(f)["items"]
    calc = Calculator(prob, datacenter.season_ids())

    names = {n for b in (SPECIAL, NORMAL) for lst in b["items"].values() for n in lst}
    names |= {n for n, _, _ in COIN_SHOP}
    ev = {}
    for n in sorted(names):
        ev[n] = calc.ev(n)
        print(f"  {n}: BP {ev[n]['bp']/1e8:.2f}억 + 선수 {ev[n]['player']/1e8:.2f}억")

    # 코인 붕어빵 틀 보너스 코인 기대값 (예: 160개 교환 시 +10~80개)
    bonus_coins = {}
    for item, table_name in COIN_BONUS.items():
        rows = prob[table_name]["groups"][0]["rows"]
        bonus_coins[item] = sum(float(p) / 100 * int(label.replace("개", "")) for label, _, p in rows)
        print(f"  {item} 교환 시 보너스 코인 기대값 {bonus_coins[item]:.2f}개")

    out = {"discounts": {}, "items": {n: ev[n] for n in names}, "packs": calc.details,
           "bonus_coins": bonus_coins}
    for key, d in DISCOUNTS.items():
        val = {n: net(ev[n], d) for n in names}
        coin_rates = {n: val[n] / (c - bonus_coins.get(n, 0)) for n, c, _ in COIN_SHOP}
        coin_value = max(r for (n, c, unl), r in zip(COIN_SHOP, coin_rates.values()) if unl)
        res = {"coin_value": coin_value, "coin_rates": coin_rates, "boards": {}}
        for label, b in (("special", SPECIAL), ("normal", NORMAL)):
            grade_val, grade_pick = [], {}
            for g in b["grades"]:
                options = [(val[n], n) for n in b["items"][g]]
                if g in b["coins"]:
                    options.append((b["coins"][g] * coin_value, f"코인 {b['coins'][g]}개"))
                best = max(options)
                grade_val.append(best[0])
                grade_pick[g] = {"value": best[0], "choice": best[1],
                                 "options": [{"name": n, "value": v} for v, n in options]}
            avg = board_average(b["counts"], grade_val)
            g_opt, keep = optimal_per_draw(b["counts"], grade_val)
            lucky = max(val[n] for n in SPECIAL["items"][LUCKY7_GRADE]) / 7 if b["lucky7"] else 0.0
            res["boards"][label] = {
                "grades": grade_pick,
                "per_ticket_full_board": avg + lucky,
                "per_ticket_optimal": g_opt + lucky,
                "lucky7_per_ticket": lucky,
                "policy": describe_policy(b["counts"], b["grades"], keep),
                "draws_per_board_optimal": simulate_draws_per_board(b["counts"], keep, trials=5000),
                "tickets": [{"name": n, "count": c, "price_fc": fc,
                             "per_fc_optimal": (g_opt + lucky) * c / fc,
                             "per_fc_full_board": (avg + lucky) * c / fc} for n, c, fc in b["tickets"]],
            }
        out["discounts"][key] = res

    os.makedirs(os.path.join(ROOT, "output"), exist_ok=True)
    with open(os.path.join(ROOT, "output", "fishbread.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

    for key in ("none", "pc_top"):
        r = out["discounts"][key]
        print(f"\n=== 할인 {key} | 코인 1개 가치 {r['coin_value']/1e8:.3f}억 ===")
        for label, b in r["boards"].items():
            print(f" [{label}] 1장당: 끝까지 {b['per_ticket_full_board']/1e8:.3f}억 / 최적리셋 {b['per_ticket_optimal']/1e8:.3f}억 (판당 평균 {b['draws_per_board_optimal']:.1f}회 뽑고 리셋)")
            for g, p in b["grades"].items():
                print(f"    {g}: {p['value']/1e8:.3f}억 ← {p['choice']}")
            for t in b["tickets"]:
                print(f"    {t['name']}: 1 FC당 {t['per_fc_optimal']:,.0f} (끝까지 {t['per_fc_full_board']:,.0f})")
            for line in b["policy"]:
                print("    ", line)
    print(f"\n완료 {time.time()-t0:.0f}초")


if __name__ == "__main__":
    main()
