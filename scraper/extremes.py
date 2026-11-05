"""상품 1개를 깠을 때 나올 수 있는 최고/최저 실수령 BP.

- 선수팩: 최고 = 확률이 있는 가장 높은 순위의 선수 가격, 최저 = 확률이 있는 가장 낮은 순위의 선수 가격
- 상자: 그 안의 보상 중 (개수 × 최고/최저)가 가장 큰/작은 것 하나
- 상품: 구성품마다 최고(최저)를 개수만큼 더한 값
- 박씨처럼 모아서 교환하는 재료는 결과가 아니라 '모으는 중'인 아이템이므로 기대값으로 계산한다
"""
import re

from calc import DISCOUNTS, parse_bp_amount

FEE_KEEP = lambda d: 1 - 0.4 * (1 - d)


class Extremes:
    def __init__(self, prob_items, pack_details, ev_lookup):
        self.items = prob_items
        self.packs = pack_details      # Calculator.details (선수팩 이름 -> 근거)
        self.ev = ev_lookup            # 이름 -> {"bp","player"} 기대값
        self.cache = {}

    def value(self, name, d, hi):
        key = (name, d, hi)
        if key in self.cache:
            return self.cache[key]
        t = self.items.get(name)
        if t and t.get("alias"):
            e = self.ev(name)
            v = e["bp"] + e["player"] * FEE_KEEP(d)
        elif t and t.get("topPrefix"):
            info = self.packs[name]
            v = (info["max_price"] if hi else info["min_price"]) * FEE_KEEP(d)
        elif t and t["groups"] and t["groups"][0]["grade"] == "BP":
            vals = [amount * parse_bp_amount(label)
                    for g in t["groups"] for label, amount, pct in g["rows"] if float(pct) > 0]
            v = max(vals) if hi else min(vals)
        elif t:
            vals = [amount * self.value(label, d, hi)
                    for g in t["groups"] for label, amount, pct in g["rows"] if float(pct) > 0]
            v = max(vals) if hi else min(vals)
        else:
            v = parse_bp_amount(name) or 0
        self.cache[key] = v
        return v

    def product(self, components):
        out = {}
        for k, d in DISCOUNTS.items():
            lo = sum(c["count"] * self.value(c["name"], d, False) for c in components)
            hi = sum(c["count"] * self.value(c["name"], d, True) for c in components)
            out[k] = [lo, hi]
        return out
