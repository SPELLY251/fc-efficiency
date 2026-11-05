"""확률표가 없는 새 상품이 있으면 GitHub 이슈를 연다 → 저장소 주인에게 이메일 알림이 간다.
같은 내용의 열린 이슈가 이미 있으면 새로 만들지 않는다."""
import json
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TITLE = "새 상품 확률표 필요"


def gh(*args):
    return subprocess.run(["gh", *args], capture_output=True, text=True, encoding="utf-8")


def main():
    path = os.path.join(ROOT, "output", "missing.json")
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        missing = json.load(f)
    if not missing:
        print("확률표가 필요한 새 상품 없음")
        return
    names = sorted(m["name"] for m in missing)
    body = ("웹 상점에 확률표가 없는 상품이 있어요. Claude에게 **\"확률표 갱신해줘\"**라고 말해 주세요.\n\n"
            + "\n".join(f"- {m['name']} ({m['price_fc']:,} FC)" for m in missing))
    existing = gh("issue", "list", "--state", "open", "--search", f"{TITLE} in:title", "--json", "number,body")
    if existing.returncode == 0:
        for issue in json.loads(existing.stdout or "[]"):
            if all(n in issue.get("body", "") for n in names):
                print(f"이미 열린 알림 #{issue['number']} 이 있어 새로 만들지 않음")
                return
    r = gh("issue", "create", "--title", f"{TITLE}: {len(missing)}개", "--body", body)
    print(r.stdout or r.stderr)


if __name__ == "__main__":
    main()
