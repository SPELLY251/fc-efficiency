"""상품 기대 BP 계산.

각 보상의 기대값을 두 부분으로 나눠 들고 다닌다.
  bp     : BP 카드처럼 수수료 없이 받는 BP
  player : 선수를 팔 때의 낙찰가(수수료 전)
실수령 = bp + player × (1 − 0.4 × (1 − 할인율))
"""
import re

import datacenter

DISCOUNTS = {"none": 0.0, "top": 0.2, "pc": 0.3, "pc_top": 0.5}


def net(ev, discount):
    return ev["bp"] + ev["player"] * (1 - 0.4 * (1 - discount))


def parse_bp_amount(text):
    """'8000000', 'BP 카드 5억', '500만', '1.5억' 등을 BP 숫자로."""
    t = text.replace(",", "").replace(" ", "")
    if re.fullmatch(r"\d+", t):
        return int(t)
    total, found = 0.0, False
    for num, unit in re.findall(r"(\d+(?:\.\d+)?)(억|만)", t):
        total += float(num) * (100_000_000 if unit == "억" else 10_000)
        found = True
    return int(total) if found else None


PACK_RE = re.compile(r"Top Price\s*(\d+)\s*(?:선수팩)?\s*\(([^)]*)\)", re.I)


def parse_pack_name(name):
    """'SPT, 26FSL 포함 Top Price 630 (11강, 114+)' -> (630, [11], 114)."""
    m = PACK_RE.search(name)
    if not m:
        return None
    top_n = int(m.group(1))
    inside = m.group(2)
    s = re.search(r"(\d+)\s*(?:~\s*(\d+))?\s*강", inside)
    if not s:
        return None
    lo = int(s.group(1))
    hi = int(s.group(2) or lo)
    o = re.search(r"(\d+)\s*\+", inside)
    ovr = int(o.group(1)) if o else 0
    return top_n, list(range(lo, hi + 1)), ovr


class Calculator:
    def __init__(self, prob_items, seasons, log=print):
        self.items = prob_items           # 이름 -> 확률표
        self.seasons = seasons            # 클래스 약칭 -> 시즌 번호
        self.log = log
        self.cache = {}
        self.details = {}                 # 선수팩 이름 -> 계산 근거

    def ev(self, name):
        if name in self.cache:
            return self.cache[name]
        table = self.items.get(name)
        if table and table.get("alias"):
            base = self.ev(table["alias"]["of"])
            f = table["alias"]["factor"]
            r = {"bp": base["bp"] * f, "player": base["player"] * f}
        elif table and table.get("topPrefix"):
            r = self._player_pack(name, table)
        elif table and table["groups"] and table["groups"][0]["grade"] == "BP":
            r = self._bp_table(table)
        elif table:
            r = self._box(table)
        else:
            amt = parse_bp_amount(name) if "BP" in name.upper() else None
            if amt is None:
                raise KeyError(f"확률표가 없는 보상: {name}")
            r = {"bp": amt, "player": 0.0}
        self.cache[name] = r
        return r

    def _bp_table(self, table):
        bp = 0.0
        for g in table["groups"]:
            for row in g["rows"]:
                label, amount, pct = row
                bp += float(pct) / 100 * amount * parse_bp_amount(label)
        return {"bp": bp, "player": 0.0}

    def _box(self, table):
        out = {"bp": 0.0, "player": 0.0, "parts": []}
        for g in table["groups"]:
            for label, amount, pct in g["rows"]:
                p = float(pct) / 100
                child = self.ev(label)
                out["bp"] += p * amount * child["bp"]
                out["player"] += p * amount * child["player"]
                out["parts"].append({"name": label, "prob": p, "amount": amount,
                                     "bp": child["bp"], "player": child["player"]})
        return out

    def _player_pack(self, name, table):
        parsed = parse_pack_name(name)
        if not parsed:
            raise ValueError(f"선수팩 이름을 해석할 수 없음: {name}")
        top_n, strongs, ovr = parsed
        classes = set()
        for g in table["groups"]:
            for c in g["grade"].split(","):
                if c.strip():
                    classes.add(datacenter.normalize_class(c))
        missing = [c for c in classes if c not in self.seasons]
        if missing:
            raise KeyError(f"{name}: 데이터센터에서 못 찾은 클래스 {missing}")
        season_nos = sorted(self.seasons[c] for c in classes)

        pool, reqs = [], 0
        for st in sorted(strongs, reverse=True):   # 높은 강화부터: 비싼 선수가 먼저 모인다
            pool.sort(key=lambda p: -p["price"])
            threshold = pool[top_n - 1]["price"] if len(pool) >= top_n else 0
            got, n = datacenter.top_players(season_nos, st, ovr, top_n, min_price=threshold)
            pool += [p for p in got if p["price"] >= threshold]
            reqs += n
        pool.sort(key=lambda p: -p["price"])

        ranks = []  # (순위, 확률)
        for g in table["groups"]:
            for a, b, amount, pct in g["rows"]:
                for k in range(a, b + 1):
                    ranks.append((k, float(pct) / 100 * amount))
        total_p = sum(p for _, p in ranks)
        gross = 0.0
        short = 0
        short_prob = 0.0
        # 같은 최저가 선수가 200명 넘게 몰리면 검색으로 다 볼 수 없다.
        # 그 순위는 확인된 가장 싼 가격(= 실제와 같거나 더 비쌀 수 없는 값)으로 채운다.
        floor_price = pool[-1]["price"] if pool else 0
        for k, p in ranks:
            if k <= len(pool):
                gross += p * pool[k - 1]["price"]
            else:
                gross += p * floor_price
                short += 1
                short_prob += p
        if total_p > 0:
            gross /= total_p   # 반올림 오차 보정: 확률 합을 1로 맞춤
        live = [k for k, p in ranks if p > 0]
        price_at = lambda k: pool[k - 1]["price"] if k <= len(pool) else floor_price
        max_price = price_at(min(live)) if live else 0
        min_price = price_at(max(live)) if live else 0
        self.details[name] = {
            "top_n": top_n, "strongs": strongs, "ovr_min": ovr,
            "classes": sorted(classes), "pool_size": len(pool),
            "missing_ranks": short, "missing_prob": short_prob, "floor_price": floor_price, "requests": reqs, "prob_sum": total_p,
            "expected_price": gross, "max_price": max_price, "min_price": min_price,
            "top3": [(p["name"], p["season"], p["strong"], p["price"]) for p in pool[:3]],
            "rank_n": (pool[top_n - 1]["price"] if len(pool) >= top_n else None),
        }
        self.log(f"  {name}: 후보 {len(pool)}명, 요청 {reqs}회, 기대 낙찰가 {gross/1e8:.2f}억")
        return {"bp": 0.0, "player": gross}
