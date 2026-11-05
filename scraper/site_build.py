"""세 탭(웹 상점 / 붕어빵 속 SSS / 26UP 프리미엄 열쇠 상점)의 결과를 모아 site/index.html 에 넣는다.

입력: output/results.json, output/fishbread.json, output/keyshop.json
(시세를 새로 모으지 않음 — 각 계산 프로그램을 먼저 실행해 둘 것)
"""
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

import run_all

from datetime import date, datetime, timedelta, timezone

FISH_PERIOD = "2026.11.05(목) ~ 12.03(목) 점검 전"
KEY_PERIOD = "2026.10.29(목) ~ 11.26(목) 점검 전"
# 이 날짜(점검일)부터는 이벤트가 끝난 것으로 본다
FISH_END = date(2026, 12, 3)
KEY_END = date(2026, 11, 26)
KST = timezone(timedelta(hours=9))
GRADE_CELLS = {"special": {"SSS": 1, "SS": 2, "S": 6, "A": 10, "B": 30}, "normal": {"SSS": 9, "A": 40}}


def load(name):
    p = os.path.join(ROOT, "output", name)
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def fishbread_tab(fb):
    if not fb:
        return None
    cards = []
    for board, label in (("special", "스페셜 게임"), ("normal", "일반 게임")):
        first = fb["discounts"]["none"]["boards"][board]
        for i, t in enumerate(first["tickets"]):
            per = {}
            for dk, res in fb["discounts"].items():
                b = res["boards"][board]
                tk = b["tickets"][i]
                per[dk] = {
                    "ev": b["per_ticket_optimal"] * tk["count"],
                    "per_fc": tk["per_fc_optimal"],
                    "per_fc_alt": tk["per_fc_full_board"],
                    "per_ticket": b["per_ticket_optimal"],
                    "per_ticket_alt": b["per_ticket_full_board"],
                    "lucky7": b["lucky7_per_ticket"],
                    "draws_per_board": b["draws_per_board_optimal"],
                    "grades": [{"grade": g, "cells": GRADE_CELLS[board][g], "value": v["value"],
                                "choice": v["choice"]} for g, v in b["grades"].items()],
                    "coin_value": res["coin_value"],
                }
            cards.append({"name": t["name"], "group": label, "price_fc": t["price_fc"], "count": t["count"],
                          "period": FISH_PERIOD, "per": per})
    return {"cards": cards, "bonus_coins": fb.get("bonus_coins", {})}


def keyshop_tab(ks):
    if not ks:
        return None
    cards = []
    plans0 = ks["discounts"]["none"]["plans"]
    for i, p in enumerate(plans0):
        per = {}
        for dk, res in ks["discounts"].items():
            q = res["plans"][i]
            per[dk] = {"ev": q["bp"], "per_fc": q["per_fc"], "key_value": res["key_value"],
                       "uses": sorted(({"name": n, "keys": u["keys"], "per_key": u["per_key"],
                                        "on_c": u.get("on_c")} for n, u in res["uses"].items()),
                                      key=lambda x: -x["per_key"])}
        cards.append({"name": p["name"], "boxes": p["boxes"], "price_fc": p["price_fc"], "period": KEY_PERIOD,
                      "avg_keys": p["avg_keys"], "p_reach_120": p["p_reach_120"],
                      "p_reach_800": p["p_reach_800"], "per": per})
    return {"cards": cards, "keys_per_box": ks["keys_per_box"], "keys_per_box_base": ks["keys_per_box_base"],
            "copier_gain": ks["copier_gain"]}


PAGES = ["index.html", "guide.html", "about.html", "privacy.html"]


def apply_config():
    """site_config.json 값으로 검색 노출·통계·광고 코드와 robots/sitemap/ads.txt 를 만든다."""
    import re
    with open(os.path.join(ROOT, "site_config.json"), encoding="utf-8") as f:
        cfg = json.load(f)
    url = cfg.get("site_url", "").rstrip("/")
    site = os.path.join(ROOT, "site")
    for page in PAGES:
        path = os.path.join(site, page)
        with open(path, encoding="utf-8") as f:
            text = f.read()
        head = []
        if url:
            canon = url + "/" + ("" if page == "index.html" else page)
            head.append(f'<link rel="canonical" href="{canon}">')
            head.append(f'<meta property="og:url" content="{canon}">')
            head.append(f'<meta property="og:image" content="{url}/og.png">')
        if page == "index.html":
            if cfg.get("google_site_verification"):
                head.append(f'<meta name="google-site-verification" content="{cfg["google_site_verification"]}">')
            if cfg.get("naver_site_verification"):
                head.append(f'<meta name="naver-site-verification" content="{cfg["naver_site_verification"]}">')
        if cfg.get("ga_measurement_id"):
            gid = cfg["ga_measurement_id"]
            head.append(f'<script async src="https://www.googletagmanager.com/gtag/js?id={gid}"></script>'
                        f"<script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments);}}"
                        f"gtag('js',new Date());gtag('config','{gid}');</script>")
        if cfg.get("adsense_client"):
            head.append(f'<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client={cfg["adsense_client"]}" crossorigin="anonymous"></script>')
        block = "\n".join(head)
        text = re.sub(r"<!--SITE-START-->[\s\S]*?<!--SITE-END-->",
                      lambda m: "<!--SITE-START-->" + ("\n" + block + "\n" if block else "") + "<!--SITE-END-->", text)
        contact = cfg.get("contact_url") or "#"
        text = re.sub(r'id="contact" href="[^"]*"', f'id="contact" href="{contact}"', text)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)

    robots = "User-agent: *\nAllow: /\n" + (f"Sitemap: {url}/sitemap.xml\n" if url else "")
    with open(os.path.join(site, "robots.txt"), "w", encoding="utf-8") as f:
        f.write(robots)
    if url:
        today = datetime.now(KST).date().isoformat()
        locs = "".join(f"<url><loc>{url}/{'' if p == 'index.html' else p}</loc><lastmod>{today}</lastmod></url>" for p in PAGES)
        with open(os.path.join(site, "sitemap.xml"), "w", encoding="utf-8") as f:
            f.write(f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{locs}</urlset>\n')
    if cfg.get("adsense_client"):
        pub = cfg["adsense_client"].replace("ca-", "")
        with open(os.path.join(site, "ads.txt"), "w", encoding="utf-8") as f:
            f.write(f"google.com, {pub}, DIRECT, f08c47fec0942fa0\n")


def build():
    with open(os.path.join(ROOT, "data", "probability.json"), encoding="utf-8") as f:
        prob_file = json.load(f)
    web = load("results.json")
    for d in web["packs"].values():   # 예전 결과 호환
        d.setdefault("max_price", d["top3"][0][3] if d["top3"] else 0)
        d.setdefault("min_price", d["rank_n"] if d.get("rank_n") else d.get("floor_price", 0))
    data = run_all.site_data(web, prob_file["items"])
    today = datetime.now(KST).date()
    fish = fishbread_tab(load("fishbread.json"))
    key = keyshop_tab(load("keyshop.json"))
    if fish:
        fish["ended"] = today >= FISH_END
    if key:
        key["ended"] = today >= KEY_END
    data["tabs"] = {"fishbread": fish, "keyshop": key}

    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    path = os.path.join(ROOT, "site", "index.html")
    with open(path, encoding="utf-8") as f:
        page = f.read()
    start, end = "/*DATA-START*/", "/*DATA-END*/"
    i, k = page.index(start) + len(start), page.index(end)
    page = page[:i] + "window.FC_DATA = " + payload + ";" + page[k:]
    with open(path, "w", encoding="utf-8") as f:
        f.write(page)
    apply_config()
    print(f"사이트 데이터 갱신: 웹 상점 {len(data['products'])}개, "
          f"붕어빵 {len(data['tabs']['fishbread']['cards']) if data['tabs']['fishbread'] else 0}개, "
          f"열쇠 상점 {len(data['tabs']['keyshop']['cards']) if data['tabs']['keyshop'] else 0}개")


if __name__ == "__main__":
    build()
