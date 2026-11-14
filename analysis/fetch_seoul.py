"""서울 열린데이터 광장 OpenAPI로 서울시 상권분석서비스 데이터를 받아 data/raw/에 CSV로 저장한다.

사용: python analysis/fetch_seoul.py [서비스명 ...]
API 키는 프로젝트 루트 .env 의 SEOUL_API_KEY 에서 읽는다 (커밋 금지).
"""
import csv
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
BASE = "http://openapi.seoul.go.kr:8088/{key}/json/{svc}/{start}/{end}/"
PAGE = 1000

SERVICES = {
    "VwsmTrdarSelngQq": "추정매출-상권",
    "VwsmTrdarFlpopQq": "길단위인구-상권",
    "VwsmTrdarWrcPopltnQq": "직장인구-상권",
    "VwsmTrdarRepopQq": "상주인구-상권",
    "VwsmTrdarStorQq": "점포-상권",
    "VwsmTrdarIxQq": "상권변화지표-상권",
    "VwsmTrdarFcltyQq": "집객시설-상권",
    "TbgisTrdarRelm": "영역-상권",
    "trdarNcmCnsmp": "소비-상권",  # 구 '소득소비-상권'(VwsmTrdarNcmCnsmpQq)은 ERROR-500. OA-21278
}


def load_key():
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("SEOUL_API_KEY="):
            return line.split("=", 1)[1].strip()
    raise SystemExit(".env 에 SEOUL_API_KEY 가 없습니다")


def get_page(key, svc, start, end):
    url = BASE.format(key=key, svc=svc, start=start, end=end)
    for attempt in range(6):
        try:
            r = requests.get(url, timeout=60)
            data = r.json()
            if svc in data:
                return data[svc]
            code = data.get("RESULT", {}).get("CODE")
            if code == "INFO-200":
                return {"row": [], "list_total_count": 0}
            raise RuntimeError(data)
        except Exception as e:  # noqa: BLE001
            if attempt == 5:
                raise
            time.sleep(2 * (attempt + 1))


def fetch(key, svc):
    first = get_page(key, svc, 1, 1)
    total = int(first["list_total_count"])
    ranges = [(s, min(s + PAGE - 1, total)) for s in range(1, total + 1, PAGE)]
    print(f"[{svc}] {SERVICES[svc]}: {total:,} rows, {len(ranges)} pages", flush=True)
    rows = []
    done = 0
    with ThreadPoolExecutor(max_workers=6) as ex:
        for page in ex.map(lambda r: get_page(key, svc, *r)["row"], ranges):
            rows.extend(page)
            done += 1
            if done % 100 == 0:
                print(f"  [{svc}] {done}/{len(ranges)}", flush=True)
    if len(rows) != total:
        print(f"  !! [{svc}] expected {total}, got {len(rows)}", flush=True)
    out = RAW / f"{svc}_{SERVICES[svc]}.csv"
    cols = list(rows[0].keys())
    with out.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    print(f"  saved {out.name} ({len(rows):,} rows)", flush=True)


if __name__ == "__main__":
    key = load_key()
    targets = sys.argv[1:] or list(SERVICES)
    for svc in targets:
        fetch(key, svc)
    print("ALL DONE", flush=True)
