"""26UP 프리미엄 열쇠 상점 계산 → output/keyshop.json

규칙 (이벤트 페이지 말풍선 + FAQ + 사용자 캡처):
- 열쇠 상자 1개 = 확률표의 열쇠 (1/3/20/800개)
- 스페셜 부스트: 게이지 11칸, 11번째 상자에 ×2,×3,×2,×3,×2,×3,×2,×5 순서로 배율.
  부스트 때 노멀(1·3개) → 다음 게이지 4칸 찬 상태, 레어(20·800개) → 1칸 찬 상태로 시작.
- 열쇠 사용처
  · 1개: 선수팩 or BP 상자
  · 120/800개 더블 드로우: 보상 4종 중 2번 뽑아(중복 가능) 더 좋은 쪽 선택.
    선택 전 열쇠 복사기: 30/200개를 넣으면 그 × 배율(1.1~4.0)로 돌려받음(손해 없음).
  · 20/60/360개 세컨드 찬스: A·B는 즉시 지급, C면 C / 치얼업(2회 한정) / 열쇠 5·15·90개로 B 업그레이드 중 선택.
- 열쇠 1개의 가치 = 위 사용처 중 '열쇠 1개당 BP'가 가장 높은 것 (열쇠 가치가 다시 들어가므로 반복 계산).
- 치얼업은 2회 한정이라 장기 평균에서는 제외하고 따로 표시.
"""
import json
import os
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

import datacenter
from calc import Calculator, DISCOUNTS, net, parse_bp_amount

BOX_TABLE = "26UP 프리미엄 열쇠 상자"
COPIER_TABLE = "열쇠복사기 (열쇠 상점)"
BOOST_SEQ = [2, 3, 2, 3, 2, 3, 2, 5]
GAUGE = 11
RARE_KEYS = {20, 800}

DOUBLE = [  # (상자 이름, 열쇠, 복사기에 넣는 열쇠)
    ("[열쇠 800개] 프리미엄 더블드로우 상자", 800, 200),
    ("[열쇠 120개] 더블드로우 상자", 120, 30),
]
SECOND = [  # (상자 이름, 열쇠, 업그레이드 열쇠, 치얼업 보상)
    ("[열쇠 360개][선수팩 70%] 프리미엄 세컨드 찬스 드로우 상자", 360, 90, "BP 카드 75억"),
    ("[열쇠 60개][선수팩 70%] 세컨드 찬스 드로우 상자", 60, 15, "BP 카드 12억"),
    ("[열쇠 20개][선수팩 70%] 베이직 세컨드 찬스 드로우 상자", 20, 5, "BP 카드 3억"),
]
SINGLE = ("[열쇠 1개] 선수팩 or BP 상자", 1)
PRODUCTS = [  # (상품 이름, 상자 수, FC)
    ("[특별할인] 26UP 프리미엄 열쇠 상자 (계정 2회)", 1, 1590),
    ("26UP 프리미엄 열쇠 상자", 1, 1750),
    ("26UP 프리미엄 열쇠 상자 X 4", 4, 7000),
    ("[상시할인] 26UP 프리미엄 열쇠 상자 X 9", 9, 14900),
]


# 구매 방법별 카드: (이름, 상자 수, FC). 특별할인은 계정 2회.
PLANS = [
    ("[특별할인] 열쇠 상자 1개", 1, 1590),
    ("[특별할인] 열쇠 상자 2개 (계정 한도)", 2, 3180),
    ("열쇠 상자 1개", 1, 1750),
    ("열쇠 상자 X 4", 4, 7000),
    ("[상시할인] 열쇠 상자 X 9", 9, 14900),
    ("X 9 묶음 2번 (18개)", 18, 29800),
    ("X 9 묶음 4번 (36개)", 36, 59600),
    ("X 9 묶음 8번 (72개)", 72, 119200),
    ("X 9 묶음 16번 (144개)", 144, 238400),
    ("X 9 묶음 32번 (288개)", 288, 476800),
]
TRIALS = 20000


def simulate_keys(prob, n_boxes, trials, seed=7):
    """상자 n개를 처음부터 열 때 모이는 열쇠 수 (부스트 포함) — 표본 목록."""
    import random
    rnd = random.Random(seed + n_boxes)
    dist = [(amount, float(p) / 100) for _, amount, p in rows(prob, BOX_TABLE)]
    amounts = [a for a, _ in dist]
    cum, s = [], 0.0
    for _, p in dist:
        s += p
        cum.append(s)
    out = []
    for _ in range(trials):
        gauge, idx, total = 0, 0, 0
        for _ in range(n_boxes):
            r = rnd.random() * s
            x = next(a for a, c in zip(amounts, cum) if r <= c)
            gauge += 1
            if gauge == GAUGE:
                total += x * BOOST_SEQ[idx % len(BOOST_SEQ)]
                idx += 1
                gauge = 1 if x in RARE_KEYS else 4
            else:
                total += x
        out.append(total)
    return out


def best_spend_table(options, max_keys):
    """f[k] = 열쇠 k개로 얻을 수 있는 최대 기대 BP (사용처를 여러 번 조합).
    options: (필요 보유 열쇠, 실제로 줄어드는 열쇠, 기대 BP)"""
    f = [0.0] * (max_keys + 1)
    for k in range(1, max_keys + 1):
        best = f[k - 1]
        for need, spend, bp in options:
            if k >= need:
                cand = bp + f[k - spend]
                if cand > best:
                    best = cand
        f[k] = best
    return f


def rows(prob, name):
    return [r for g in prob[name]["groups"] for r in g["rows"]]


def keys_per_box(prob):
    """부스트까지 포함한 상자 1개당 평균 열쇠 (장기 평균)."""
    dist = [(amount, float(p) / 100) for _, amount, p in rows(prob, BOX_TABLE)]
    ex = sum(a * p for a, p in dist)
    p_rare = sum(p for a, p in dist if a in RARE_KEYS)
    # 부스트 상자 이후 다음 부스트까지 상자 수: 노멀 → 7개(4칸 찬 상태), 레어 → 10개(1칸 찬 상태)
    cycle = (GAUGE - 4) * (1 - p_rare) + (GAUGE - 1) * p_rare
    m_avg = sum(BOOST_SEQ) / len(BOOST_SEQ)
    per_box = ex * (cycle - 1 + m_avg) / cycle
    return ex, per_box, cycle, m_avg


def main():
    t0 = time.time()
    with open(os.path.join(ROOT, "data", "probability.json"), encoding="utf-8") as f:
        prob = json.load(f)["items"]
    calc = Calculator(prob, datacenter.season_ids())

    base_keys, keys_box, cycle, m_avg = keys_per_box(prob)
    copier_gain = sum(float(p) / 100 * float(lbl.split()[0]) for lbl, _, p in rows(prob, COPIER_TABLE)) - 1
    print(f"상자 1개당 열쇠: 기본 {base_keys:.3f}개, 부스트 포함 {keys_box:.3f}개 (부스트 주기 {cycle:.2f}상자, 평균 배율 {m_avg})")
    print(f"열쇠 복사기 평균 이득: 넣은 열쇠의 +{copier_gain*100:.1f}%")

    # 필요한 모든 보상의 기대값
    ev = {}
    def E(name):
        if name not in ev:
            ev[name] = calc.ev(name) if name in prob else {"bp": parse_bp_amount(name) or 0, "player": 0.0}
        return ev[name]
    for name, *_ in DOUBLE + SECOND:
        for lbl, _, _ in rows(prob, name):
            E(lbl)
    for _, _, _, cheer in SECOND:
        E(cheer)
    E(SINGLE[0])

    print("상자 여는 과정 모의 실험 중...")
    key_samples = {n: simulate_keys(prob, n, TRIALS) for n in sorted({n for _, n, _ in PLANS})}

    out = {"keys_per_box_base": base_keys, "keys_per_box": keys_box, "copier_gain": copier_gain,
           "discounts": {}, "packs": calc.details,
           "items": {k: v for k, v in ev.items()}}
    for key, d in DISCOUNTS.items():
        val = lambda n: net(E(n), d)
        v = 0.0
        for _ in range(100):   # 열쇠 가치 반복 계산
            uses = {}
            uses[SINGLE[0]] = {"keys": 1, "bp": val(SINGLE[0])}
            for name, cost, copy_in in DOUBLE:
                items = [(val(lbl), float(p) / 100, lbl) for lbl, _, p in rows(prob, name)]
                ps = sum(p for _, p, _ in items)
                items = [(x, p / ps, l) for x, p, l in items]
                emax = sum(p1 * p2 * max(x1, x2) for x1, p1, _ in items for x2, p2, _ in items)
                bonus = copy_in * copier_gain * v
                uses[name] = {"keys": cost, "bp": emax + bonus, "best_of_two": emax, "copier_bonus_bp": bonus}
            for name, cost, up, cheer in SECOND:
                (a_l, _, pa), (b_l, _, pb), (c_l, _, pc) = rows(prob, name)
                pa, pb, pc = float(pa) / 100, float(pb) / 100, float(pc) / 100
                on_c = max(val(c_l), val(b_l) - up * v)
                bp = pa * val(a_l) + pb * val(b_l) + pc * on_c
                with_cheer = pa * val(a_l) + pb * val(b_l) + pc * max(on_c, val(cheer))
                uses[name] = {"keys": cost, "bp": bp, "on_c": "업그레이드" if val(b_l) - up * v > val(c_l) else "C 그대로",
                              "bp_with_cheerup": with_cheer}
            for u in uses.values():
                u["per_key"] = u["bp"] / u["keys"]
            best = max(uses, key=lambda n: uses[n]["per_key"])
            new_v = uses[best]["per_key"]
            if abs(new_v - v) < 1:
                v = new_v
                break
            v = new_v
        # ---- 구매량별: 실제로 모은 열쇠로 가장 이득인 조합 ----
        options = [(1, 1, val(SINGLE[0]))]
        for name, cost, copy_in in DOUBLE:
            emax = uses[name]["best_of_two"]
            options.append((cost, cost, emax))                                    # 복사기 없이
            options.append((cost + copy_in, cost - round(copy_in * copier_gain), emax))  # 복사기 사용
        for name, cost, up, cheer in SECOND:
            (a_l, _, pa), (b_l, _, pb), (c_l, _, pc) = rows(prob, name)
            pa, pb, pc = float(pa) / 100, float(pb) / 100, float(pc) / 100
            options.append((cost, cost, pa * val(a_l) + pb * val(b_l) + pc * val(c_l)))           # C 그대로
            options.append((cost + up, cost + round(pc * up), pa * val(a_l) + (pb + pc) * val(b_l)))  # C면 업그레이드
        plans = []
        for pname, n, fc in PLANS:
            samples = key_samples[n]
            f = best_spend_table(options, max(samples))
            bp = sum(f[k] for k in samples) / len(samples)
            avg_keys = sum(samples) / len(samples)
            plans.append({"name": pname, "boxes": n, "price_fc": fc, "avg_keys": avg_keys,
                          "bp": bp, "per_fc": bp / fc,
                          "p_reach_800": sum(1 for k in samples if k >= 800) / len(samples),
                          "p_reach_120": sum(1 for k in samples if k >= 120) / len(samples)})
        res = {"key_value": v, "best_use": best, "uses": uses, "products": [], "plans": plans}
        for pname, n, fc in PRODUCTS:
            bp = n * keys_box * v
            res["products"].append({"name": pname, "boxes": n, "price_fc": fc, "bp": bp, "per_fc": bp / fc})
        out["discounts"][key] = res

    with open(os.path.join(ROOT, "output", "keyshop.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

    for key in ("none", "pc_top"):
        r = out["discounts"][key]
        print(f"\n=== 할인 {key} | 열쇠 1개 가치 {r['key_value']/1e4:,.0f}만 BP (가장 이득: {r['best_use']}) ===")
        for n, u in sorted(r["uses"].items(), key=lambda x: -x[1]["per_key"]):
            extra = f" | C 나오면 {u['on_c']}, 치얼업 포함 시 {u['bp_with_cheerup']/u['keys']/1e4:,.0f}만" if "on_c" in u else ""
            print(f"  {n}: 열쇠 1개당 {u['per_key']/1e4:,.0f}만 BP{extra}")
        for p in r["products"]:
            print(f"  [800개 기준] {p['name']}: 1 FC당 {p['per_fc']:,.0f}")
        for p in r["plans"]:
            print(f"  [구매량별] {p['name']}: 평균 열쇠 {p['avg_keys']:.0f}개, 기대 {p['bp']/1e8:.2f}억, 1 FC당 {p['per_fc']:,.0f}"
                  f" (120개 도달 {p['p_reach_120']*100:.0f}%, 800개 도달 {p['p_reach_800']*100:.0f}%)")
    print(f"\n완료 {time.time()-t0:.0f}초")


if __name__ == "__main__":
    main()
