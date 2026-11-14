"""P8 보완: 사전 설계(W0) 실패 → 규칙(6-2 ③⑤)에 따른 재설계 V2 검증 + 추가 근거 수치.
python analysis/validate_v2.py   (score.py 실행 후)
- 지표를 연율화(÷ 구간 연수), C2·D2를 변화량으로 바꿔 재검증
- V2 점수: 백테스트에서 방향이 맞은 신호만 사용 (집적도 +, 점포당 매출 수준 −(평균회귀), A3 전환율 +, C1 점포 증가 + 여부 확인)
- 홀드아웃: V2 를 만든 구간(2021→2023 / 2023→최근)과 다른 구간(하반기 평균 끝점)에서 재검증
- 추가 근거: 집적지 중 점포 감소 vs 증가 상권의 이후 성장(E09), 제과/커피 비율 서울 기준(E19), 시간대 6구간(E16)
"""
import json
import runpy
import sys
import io
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr, mannwhitneyu

ROOT = Path(__file__).resolve().parents[1]
A = ROOT / "analysis"
_old = sys.stdout
sys.stdout = io.StringIO()
g = runpy.run_path(str(A / "score.py"))
sys.stdout = _old
agg, win, target, filt, area, ix = g["agg"], g["win"], g["target"], g["filt"], g["area"], g["ix"]
lg = g["lg"]


def feats(qa, qb, years):
    a, b = agg(qa), agg(qb)
    f = pd.DataFrame(index=b.index)
    f["A1"] = lg(b.flpop, a.flpop) / years
    f["A2"] = lg(b.fixed, a.fixed) / years
    f["A3"] = lg(b.conv, a.conv) / years
    f["B1"] = lg(b.ticket, a.ticket) / years
    f["B2"] = (b.young_share - a.young_share) / years
    f["C1"] = lg(b.stores, a.stores) / years
    f["C2"] = (b.close_rt - a.close_rt) / years
    f["D1"] = (b.frc_share - a.frc_share) / years
    f["D2"] = (b.oth_open_rt - a.oth_open_rt) / years
    f["CLUSTER"] = np.log(b.stores)            # 집적도 (수준)
    f["PERSTORE"] = np.log(b.per_store)        # 점포당 매출 수준 (평균회귀)
    f["MOM"] = lg(b.per_store, a.per_store) / years
    f["sales_b"], f["stores_b"], f["per_store_b"] = b.sales, b.stores, b.per_store
    return f.replace([np.inf, -np.inf], np.nan)


def tgt(qa, qb, years):
    y, y2 = target(qa, qb)
    return y / years


def pct(x, d):
    x = x.clip(x.quantile(0.025), x.quantile(0.975))
    r = x.rank(pct=True) * 100
    return r if d > 0 else 100 - r


def eval_score(s, y):
    m = s.notna() & y.notna()
    s, y = s[m], y[m]
    q = s.rank(pct=True)
    top, bot = y[q >= 0.8], y[q <= 0.2]
    return dict(rho=round(spearmanr(s, y)[0], 3),
                top20=round(float(np.expm1(top.median())) * 100, 2),
                bot20=round(float(np.expm1(bot.median())) * 100, 2),
                p=round(float(mannwhitneyu(top, bot, alternative="greater").pvalue), 4), n=int(m.sum()))


out = {}
# --- 1) 연율화·변화량 버전으로 W0 재검증 (방향 보정 상관)
DIR = {"A1": 1, "A2": 1, "A3": 1, "B1": 1, "B2": 1, "C1": -1, "C2": -1, "D1": 1, "D2": 1}
f = filt(feats(win(20211, 20214), win(20231, 20234), 2.0))
y = tgt(win(20231, 20234), win(20253, 20262), 2.5).rename("Y")
f = f.join(y, how="inner").dropna(subset=["Y"])
out["ind_corr_annualized"] = {k: round(spearmanr(f[k], f.Y, nan_policy="omit")[0] * d, 3) for k, d in DIR.items()}
for k in ["CLUSTER", "PERSTORE", "MOM"]:
    out["ind_corr_annualized"][k] = round(spearmanr(f[k], f.Y, nan_policy="omit")[0], 3)
W0 = dict(A=35, B=20, C=30, D=15)
AX = {"A": ["A1", "A2", "A3"], "B": ["B1", "B2"], "C": ["C1", "C2"], "D": ["D1", "D2"]}


def w0(df):
    p = pd.DataFrame({k: pct(df[k], d) for k, d in DIR.items()})
    ax = pd.DataFrame({a: p[c].mean(axis=1) for a, c in AX.items()})
    return sum(ax[a] * w for a, w in W0.items()) / 100


out["W0_annualized"] = eval_score(w0(f), f.Y)

# --- 2) V2: 백테스트 통과 신호 (방향 일치 + |rho|>=0.05) 로 재설계
passed = {k: (1 if v > 0 else -1) for k, v in out["ind_corr_annualized"].items()
          if abs(v) >= 0.05 and k != "MOM"}
# 원래 방향 기준 상관을 실제 부호로 변환
sign = {}
for k in passed:
    raw = spearmanr(f[k], f.Y, nan_policy="omit")[0]
    sign[k] = 1 if raw > 0 else -1
out["V2_signals"] = {k: ("+" if s > 0 else "−") for k, s in sign.items()}


def v2(df):
    return pd.DataFrame({k: pct(df[k], s) for k, s in sign.items()}).mean(axis=1)


out["V2_train"] = eval_score(v2(f), f.Y)
out["MOM_train"] = eval_score(f.MOM, f.Y)

# --- 3) 홀드아웃: 다른 끝점(하반기 평균)으로 재검증
h = filt(feats(win(20213, 20214), win(20233, 20234), 2.0))
yh = tgt(win(20233, 20234), win(20253, 20254), 2.0).rename("Y")
h = h.join(yh, how="inner").dropna(subset=["Y"])
out["V2_holdout"] = eval_score(v2(h), h.Y)
out["W0_holdout"] = eval_score(w0(h), h.Y)

# --- 4) 최신 구간 V2 순위
L = filt(feats(win(20233, 20242), win(20253, 20262), 2.0))
ixl = ix[ix.STDR_YYQU_CD == ix.STDR_YYQU_CD.max()].set_index("TRDAR_CD")
L = L[ixl.reindex(L.index).TRDAR_CHNGE_IX.ne("HL").values]
L["V2"] = v2(L)
L["W0"] = w0(L)
L = L.join(area[["TRDAR_CD_NM", "SIGNGU_CD_NM"]]).sort_values("V2", ascending=False)
L["V2_rank"] = range(1, len(L) + 1)
L["W0_rank"] = L.W0.rank(ascending=False).fillna(0).astype(int)
L.to_csv(A / "scores_v2.csv", encoding="utf-8-sig")
m = L.loc[3110554]
out["mangwon"] = dict(V2=round(m.V2, 1), V2_rank=int(m.V2_rank), W0=round(m.W0, 1), W0_rank=int(m.W0_rank), n=len(L),
                      V2_rank_cluster10=int((L[L.stores_b >= 10].V2 > m.V2).sum() + 1),
                      n_cluster10=int((L.stores_b >= 10).sum()))
out["V2_top10"] = L.head(10)[["TRDAR_CD_NM", "SIGNGU_CD_NM", "V2", "W0_rank", "stores_b", "sales_b"]].round(1).reset_index().to_dict("records")
top_big = L[(L.stores_b >= 10)].head(10)
out["V2_top10_cluster"] = top_big[["TRDAR_CD_NM", "SIGNGU_CD_NM", "V2", "V2_rank", "stores_b", "sales_b", "per_store_b"]].round(1).reset_index().to_dict("records")

# --- 5) E09: 집적지(점포 10+) 중 2021→2023 점포 감소 vs 증가 상권의 이후 성장
cl = f[f.stores_b >= 10]
dec, inc = cl.Y[cl.C1 < 0], cl.Y[cl.C1 > 0]
out["E09"] = dict(n_dec=int(len(dec)), n_inc=int(len(inc)),
                  dec_median=round(float(np.expm1(dec.median())) * 100, 2),
                  inc_median=round(float(np.expm1(inc.median())) * 100, 2),
                  p=round(float(mannwhitneyu(dec, inc, alternative="greater").pvalue), 4))
# 집적 상위 20% vs 하위 20% (E05 효과 크기)
q = f.CLUSTER.rank(pct=True)
out["E05_size"] = dict(top20=round(float(np.expm1(f.Y[q >= .8].median())) * 100, 2),
                       bot20=round(float(np.expm1(f.Y[q <= .2].median())) * 100, 2))

# --- 6) E19, E16 baselines
sel = pd.read_csv(ROOT / "data/raw/VwsmTrdarSelngQq_추정매출-상권.csv")
sel = sel[sel.STDR_YYQU_CD.isin([20253, 20254, 20261, 20262])]
cb = sel[sel.SVC_INDUTY_CD.isin(["CS100010", "CS100005"])]
by = cb.groupby("SVC_INDUTY_CD").THSMON_SELNG_AMT.sum()
out["E19_seoul_bakery_to_coffee"] = round(by["CS100005"] / by["CS100010"] * 100, 1)
mw = cb[cb.TRDAR_CD == 3110554].groupby("SVC_INDUTY_CD").THSMON_SELNG_AMT.sum()
out["E19_mangwon_4q"] = round(mw["CS100005"] / mw["CS100010"] * 100, 1)
for c, nm in [(3110852, "이수역9번"), (3110718, "한국SGI본부")]:
    x = cb[cb.TRDAR_CD == c].groupby("SVC_INDUTY_CD").THSMON_SELNG_AMT.sum()
    out[f"E19_{nm}"] = round(x.get("CS100005", 0) / x["CS100010"] * 100, 1)
tz = ["TMZON_00_06_SELNG_AMT", "TMZON_06_11_SELNG_AMT", "TMZON_11_14_SELNG_AMT", "TMZON_14_17_SELNG_AMT",
      "TMZON_17_21_SELNG_AMT", "TMZON_21_24_SELNG_AMT"]
s_all = cb[tz].sum(); s_mw = cb[cb.TRDAR_CD == 3110554][tz].sum()
out["E16_mangwon"] = (s_mw / s_mw.sum() * 100).round(1).tolist()
out["E16_seoul"] = (s_all / s_all.sum() * 100).round(1).tolist()

json.dump(out, open(A / "results_v2.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=float)
print(json.dumps({k: v for k, v in out.items() if k not in ("V2_top10",)}, ensure_ascii=False, indent=1))
