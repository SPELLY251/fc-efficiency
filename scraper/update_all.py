"""전체 갱신: 붕어빵 → 열쇠 상점 → 웹 상점(마지막에 사이트까지 갱신).

- 같은 선수 시세는 3시간 동안 다시 받지 않으므로 겹치는 요청이 줄어든다.
- 끝난 이벤트는 계산을 건너뛰고, 사이트에 '종료'로 표시된다(site_build.py).
- 하나가 실패해도 나머지는 계속 진행한다.
"""
import sys
import traceback
from datetime import datetime, timedelta, timezone

import site_build

KST = timezone(timedelta(hours=9))


def main():
    today = datetime.now(KST).date()
    ok = True
    steps = []
    if today < site_build.FISH_END:
        import fishbread_run
        steps.append(("붕어빵 속 SSS", fishbread_run.main))
    if today < site_build.KEY_END:
        import keyshop_run
        steps.append(("26UP 프리미엄 열쇠 상점", keyshop_run.main))
    import run_all
    steps.append(("웹 상점", run_all.main))   # 마지막에 사이트까지 갱신

    for name, fn in steps:
        print(f"\n######## {name} ########", flush=True)
        try:
            fn()
        except Exception:
            ok = False
            traceback.print_exc()
            print(f"!! {name} 계산 실패 — 이전 결과를 그대로 둡니다", flush=True)
    if not ok:
        site_build.build()   # 실패한 탭은 이전 결과로라도 사이트를 만든다
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
