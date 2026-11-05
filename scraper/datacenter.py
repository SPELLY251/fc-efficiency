"""FC온라인 데이터센터(fconline.nexon.com/datacenter) 선수 기준가 수집.

- 검색 1번에 최대 200명만 나오므로, 가격 높은 순으로 받은 뒤
  마지막 선수 가격을 상한으로 바꿔 다시 검색한다.
- 경계에서 겹치는 선수는 선수 고유번호(spid)로 제거한다.
- 가격 상한 값(n8PlayerGrade1Max)의 단위는 1,000 BP.
"""
import html as _html
import re
import time

import requests

URL = "https://fconline.nexon.com/datacenter/PlayerList"
DELAY = 3.0          # 요청 사이 대기(초) — 넥슨 서버 부담을 줄이기 위해 넉넉히
PAGE_LIMIT = 200
UA = "fc-efficiency (personal BP calculator; low-frequency)"

_session = requests.Session()
_session.headers["User-Agent"] = UA
_last_request = 0.0


# 같은 갱신 시간대(3시간 이내)에 같은 검색을 다시 하지 않도록 결과를 파일에 잠시 저장한다
import json as _json
import os as _os
_CACHE_PATH = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), "output", "dc_cache.json")
_CACHE_TTL = 3 * 3600
_cache = None


def _cache_load():
    global _cache
    if _cache is None:
        try:
            with open(_CACHE_PATH, encoding="utf-8") as f:
                raw = _json.load(f)
            now = time.time()
            _cache = {k: v for k, v in raw.items() if now - v["t"] < _CACHE_TTL}
        except (OSError, ValueError):
            _cache = {}
    return _cache


def _cache_save():
    _os.makedirs(_os.path.dirname(_CACHE_PATH), exist_ok=True)
    with open(_CACHE_PATH, "w", encoding="utf-8") as f:
        _json.dump(_cache, f, ensure_ascii=False)


def _post(data):
    global _last_request
    wait = DELAY - (time.time() - _last_request)
    if wait > 0:
        time.sleep(wait)
    for attempt in range(3):
        try:
            r = _session.post(URL, data=data, timeout=60)
            _last_request = time.time()
            r.raise_for_status()
            return r.text
        except requests.RequestException:
            _last_request = time.time()
            if attempt == 2:
                raise
            time.sleep(10 * (attempt + 1))


def season_ids():
    """클래스 약칭(예: SPT, 26FSL) -> 데이터센터 시즌 번호."""
    global _last_request
    r = _session.get("https://fconline.nexon.com/datacenter", timeout=60)
    _last_request = time.time()
    r.raise_for_status()
    out = {}
    for tag in re.finditer(r'<input[^>]*class="season_check[^"]*"[^>]*>', r.text):
        no = re.search(r'data-no="(\d+)"', tag.group(0))
        sid = re.search(r'id="season_([^"]+)"', tag.group(0))
        if no and sid:
            out.setdefault(sid.group(1).upper(), int(no.group(1)))
        # 이미지 파일 이름도 별칭으로 등록 (예: 26 LIVE -> live.png)
        label = r.text[tag.end(): r.text.find("</label>", tag.end())]
        img = re.search(r'/season/(?:filter/)?([^"/]+)\.png', label)
        if no and img:
            out.setdefault(img.group(1).upper(), int(no.group(1)))
    return out


def normalize_class(abbr):
    """확률표의 클래스 표기를 데이터센터 이미지 이름 규칙에 맞춘다."""
    a = abbr.strip().upper().replace(".", "").replace(" ", "")
    a = re.sub(r"^(\d\d)HEROES$", r"\1HR", a)
    a = re.sub(r"^(\d\d)PL$", r"\1PLA", a)
    return a


def _parse(text, strong):
    players = []
    for unit in text.split('<div id="area_playerunit_')[1:]:
        spid = int(unit[: unit.index('"')])
        name = re.search(r'<div class="name">([^<]*)</div>', unit)
        season = re.search(r"/season/([^.\"]+)\.png", unit)
        ovr = re.search(r'skillData_\d+">\s*(\d+)', unit)
        price = re.search(r'span_bp%d"[^>]*alt="([\d,]+)"' % strong, unit)
        if not price:
            continue
        players.append({
            "spid": spid,
            "name": _html.unescape(name.group(1)).strip() if name else "",
            "season": season.group(1) if season else "",
            "ovr": int(ovr.group(1)) if ovr else 0,
            "strong": strong,
            "price": int(price.group(1).replace(",", "")),
        })
    return players


def top_players(season_nos, strong, ovr_min, need, min_price=0):
    """조건에 맞는 선수를 가격 높은 순으로 최소 need명(가능하면) 모은다.

    min_price보다 싼 선수만 남으면 더 볼 필요가 없으므로 멈춘다
    (여러 강화 단계를 합쳐 순위를 매길 때 요청 수를 크게 줄여 준다).
    """
    seasons = "," + ",".join(str(s) for s in season_nos) + ","
    base = {
        "strSeason": seasons,
        "n1Strong": strong,
        "n4OvrMin": ovr_min,
        "n4OvrMax": 200,
        "n8PlayerGrade1Min": 0,
        "strOrderby": " n8playergrade1 desc",
        "n4SalaryMin": 4, "n4SalaryMax": 99,
        "n4PageNo": 1,
    }
    seen, result = set(), []
    cap = 999_900_000  # 1,000 BP 단위 → 9,999억
    requests_made = 0
    while True:
        cache = _cache_load()
        ckey = f"{seasons}|{strong}|{ovr_min}|{cap}"
        if ckey in cache:
            page = cache[ckey]["players"]
        else:
            page = _parse(_post({**base, "n8PlayerGrade1Max": cap}), strong)
            requests_made += 1
            cache[ckey] = {"t": time.time(), "players": page}
            _cache_save()
        new = [p for p in page if p["spid"] not in seen]
        for p in new:
            seen.add(p["spid"])
            result.append(p)
        if len(page) < PAGE_LIMIT or len(result) >= need:
            break
        last_price = page[-1]["price"]
        if last_price < min_price:
            break
        next_cap = last_price // 1000
        if not new:
            # 같은 가격 선수가 200명 넘게 몰린 경우: 한 단계 낮춰 진행
            next_cap = min(next_cap, cap) - 1
        cap = next_cap
        if cap <= 0:
            break
    result.sort(key=lambda p: -p["price"])
    return result, requests_made
