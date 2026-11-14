"""점포-상권: 분석에 필요한 분기만 분기 파라미터로 병렬 수집 (전체 168만 행 대신)."""
import csv, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from fetch_seoul import load_key, get_page, RAW
import requests
key = load_key(); svc = "VwsmTrdarStorQq"
QS = [20211,20212,20213,20214,20231,20232,20233,20234,20241,20242,20253,20254,20261,20262]
def pg(q, s, e):
    url = f"http://openapi.seoul.go.kr:8088/{key}/json/{svc}/{s}/{e}/{q}"
    for i in range(6):
        try: return requests.get(url, timeout=60).json()[svc]["row"]
        except Exception:
            if i == 5: raise
jobs = []
for q in QS:
    tot = int(requests.get(f"http://openapi.seoul.go.kr:8088/{key}/json/{svc}/1/1/{q}", timeout=60).json()[svc]["list_total_count"])
    jobs += [(q, s, min(s+999, tot)) for s in range(1, tot+1, 1000)]
print(len(jobs), "pages", flush=True)
rows = []
with ThreadPoolExecutor(max_workers=24) as ex:
    for i, r in enumerate(ex.map(lambda j: pg(*j), jobs)):
        rows += r
        if i % 100 == 0: print(i, flush=True)
out = RAW / f"{svc}_점포-상권.csv"
with out.open("w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
print("saved", len(rows), flush=True)
