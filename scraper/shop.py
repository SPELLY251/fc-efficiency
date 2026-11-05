"""넥슨 FC온라인 웹샵 상품 목록 수집 (서버가 HTML로 바로 주므로 일반 요청으로 충분)."""
import html as _html
import re
import time

import requests

LIST_URL = "https://shop.fconline.nexon.com/Shop/List"
DELAY = 3.0
UA = "fc-efficiency (personal BP calculator; low-frequency)"


def _clean(s):
    return re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", "", s))).strip()


def parse_list(text):
    products = []
    for li in re.split(r'<li class="hidden[^"]*" data-order=', text)[1:]:
        pid = re.search(r"/Shop/View\?strPid=(\d+)", li)
        name = re.search(r'<p class="text">(.*?)</p>', li, re.S)
        price = re.search(r'<p class="price fc[^"]*">(.*?)</p>', li, re.S)
        if not (pid and name and price):
            continue
        nums = re.findall(r"[\d,]+(?=\s*(?:FC|</strong>|<))", price.group(1))
        nums = [int(n.replace(",", "")) for n in nums if n.replace(",", "")]
        comp_block = re.search(r'<div class="tit">구성품</div>.*?<div class="system">(.*?)</div>', li, re.S)
        components = []
        if comp_block:
            for line in re.split(r"<br\s*/?>", comp_block.group(1)):
                line = _clean(line)
                m = re.match(r"(.+?)\s+(\d+)개$", line)
                if m:
                    components.append({"name": m.group(1).strip(), "count": int(m.group(2))})
        # 구매 제한 예: "구매제한 계정 3회", "구매제한 월50회"
        limit_m = re.search(r"<p class='state limit'>(.*?)</p>", li, re.S)
        limit_text = _clean(limit_m.group(1)) if limit_m else ""
        limit_n = re.search(r"(\d+)\s*회", limit_text)
        period = re.search(r'<div class="date[^"]*">\s*(?:<!--.*?-->)?\s*<p>(.*?)</p>', li, re.S)
        products.append({
            "pid": int(pid.group(1)),
            "name": _clean(name.group(1)),
            "price_fc": nums[-1] if nums else None,   # 할인 중이면 마지막 숫자가 실제 가격
            "components": components,
            "period": _clean(period.group(1)) if period else "",
            "limit_text": limit_text,
            "limit": int(limit_n.group(1)) if limit_n else None,
        })
    return products


def fetch_all(max_pages=10):
    s = requests.Session()
    s.headers["User-Agent"] = UA
    seen, out = set(), []
    for page in range(1, max_pages + 1):
        r = s.get(LIST_URL, params={"n1TabType": 1, "n1OrderType": 1, "n1PageNo": page, "strSType": "[]"}, timeout=60)
        r.raise_for_status()
        items = [p for p in parse_list(r.text) if p["pid"] not in seen]
        if not items:
            break
        for p in items:
            seen.add(p["pid"])
            out.append(p)
        time.sleep(DELAY)
    return out
