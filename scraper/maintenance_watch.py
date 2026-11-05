"""목요일 정기점검이 끝날 때까지 기다렸다가, 끝나면 '갱신해도 된다'고 알려 준다.

동작
1. FC온라인 공지 목록에서 오늘 날짜(예: 11/12(목))의 '점검' 공지 제목을 찾는다.
   제목 예: "(조기 오픈) 10/22(목) 정기점검 (오전 6시 30분 ~ 오전 10시 40분)"
2. 종료 예정 시각 5분 전까지 기다렸다가 공지를 다시 읽는다 (연장되면 제목의 시각이 바뀜).
3. 연장됐으면 새 시각으로 다시 기다리고, 아니면 종료 시각까지 기다린 뒤 한 번 더 확인한다.
4. 점검이 끝났으면 GITHUB_OUTPUT 에 run=true 를 남긴다 → 갱신 작업이 이어서 실행된다.

GitHub 작업 하나는 최대 6시간이라, 5시간 40분이 지나도 안 끝나면 다음 예약 실행에 넘긴다.
"""
import html
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone

import requests

sys.stdout.reconfigure(encoding="utf-8")
KST = timezone(timedelta(hours=9))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIST_URL = "https://fconline.nexon.com/news/notice/list"
UA = "fc-efficiency (personal BP calculator; low-frequency)"
MAX_RUNTIME = 5 * 3600 + 40 * 60
CHECK_BEFORE = timedelta(minutes=5)
AFTER_END = timedelta(minutes=2)

TIME_RE = re.compile(r"(오전|오후|낮|밤|새벽)?\s*(\d{1,2})\s*시(?:\s*(\d{1,2})\s*분)?")


def now():
    return datetime.now(KST)


def to_time(day, m):
    ampm, h, mi = m.group(1), int(m.group(2)), int(m.group(3) or 0)
    if ampm in ("오후", "밤") and h < 12:
        h += 12
    if ampm in ("오전", "새벽") and h == 12:
        h = 0
    return datetime(day.year, day.month, day.day, h % 24, mi, tzinfo=KST)


def find_notice(day):
    """오늘 날짜의 점검 공지 제목 → (제목, 종료 시각) 또는 None"""
    r = requests.get(LIST_URL, headers={"User-Agent": UA}, timeout=60)
    r.raise_for_status()
    text = re.sub(r"<script[\s\S]*?</script>", "", r.text)
    tag = f"{day.month}/{day.day}("
    best = None
    for sn, block in re.findall(r"n4ArticleSN=(\d+)[^>]*>([\s\S]{0,600}?)</a>", text):
        title = html.unescape(re.sub(r"<[^>]+>|\s+", " ", block)).strip()
        if "점검" not in title or tag not in title:
            continue
        rng = re.search(r"\(([^()]*~[^()]*)\)\s*$", title) or re.search(r"\(([^()]*~[^()]*)\)", title)
        if not rng:
            continue
        times = list(TIME_RE.finditer(rng.group(1).split("~")[-1]))
        if not times:
            continue
        end = to_time(day, times[-1])
        if best is None or int(sn) > best[0]:
            best = (int(sn), title, end)
    return (best[1], best[2]) if best else None


def already_updated_after(end):
    try:
        with open(os.path.join(ROOT, "output", "results.json"), encoding="utf-8") as f:
            ts = datetime.fromisoformat(json.load(f)["updated_at"])
        return ts >= end
    except (OSError, KeyError, ValueError):
        return False


def sleep_until(t, started):
    while now() < t:
        if time.time() - started > MAX_RUNTIME:
            return False
        time.sleep(min(300, max(1, (t - now()).total_seconds())))
    return True


def output(run, reason):
    print(f"결과: {'갱신 실행' if run else '갱신 안 함'} — {reason}", flush=True)
    gh_out = os.environ.get("GITHUB_OUTPUT")
    if gh_out:
        with open(gh_out, "a", encoding="utf-8") as f:
            f.write(f"run={'true' if run else 'false'}\n")


def main():
    started = time.time()
    day = now().date()
    found = find_notice(day)
    if not found:
        return output(False, f"오늘({day}) 점검 공지가 없어요")
    title, end = found
    print(f"점검 공지: {title}\n종료 예정: {end:%H:%M}", flush=True)
    if already_updated_after(end):
        return output(False, "이미 점검 후 갱신을 마쳤어요")

    while True:
        done_flag = "완료" in title or "조기 오픈" in title
        if done_flag and now() < end:
            end = now()    # 조기 종료
        if now() >= end:
            # 종료 시각이 지났으면 잠시 뒤 한 번 더 확인해서 막판 연장을 잡는다
            if not sleep_until(end + AFTER_END, started):
                return output(False, "시간 초과 — 다음 예약 실행에 넘겨요")
            again = find_notice(day)
            if again and again[1] > end and not ("완료" in again[0] or "조기 오픈" in again[0]):
                title, end = again
                print(f"연장 확인: {title} → {end:%H:%M}", flush=True)
                continue
            return output(True, f"점검 종료({end:%H:%M}) 확인")
        target = end - CHECK_BEFORE if now() < end - CHECK_BEFORE else end
        print(f"{target:%H:%M} 까지 기다린 뒤 다시 확인해요", flush=True)
        if not sleep_until(target, started):
            return output(False, "시간 초과 — 다음 예약 실행에 넘겨요")
        again = find_notice(day)
        if again:
            if again[1] != end:
                print(f"시각 변경: {again[0]} → {again[1]:%H:%M}", flush=True)
            title, end = again


if __name__ == "__main__":
    main()
