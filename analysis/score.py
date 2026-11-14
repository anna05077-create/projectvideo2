"""P3: 성장 점수 계산 + 백테스트 + 최종 상권 선정.  python analysis/score.py
출력: analysis/results.json, analysis/scores_latest.csv, analysis/backtest.csv
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr, mannwhitneyu

ROOT = Path(__file__).resolve().parents[1]
R = ROOT / "data" / "raw"
A = ROOT / "analysis"
CB = ["CS100010", "CS100005"]  # 커피-음료, 제과점

# ---------- load ----------
sel = pd.read_csv(R / "VwsmTrdarSelngQq_추정매출-상권.csv",
                  usecols=["STDR_YYQU_CD", "TRDAR_CD", "SVC_INDUTY_CD", "THSMON_SELNG_AMT", "THSMON_SELNG_CO",
                           "AGRDE_20_SELNG_AMT", "AGRDE_30_SELNG_AMT",
                           "TMZON_06_11_SELNG_AMT", "TMZON_11_14_SELNG_AMT", "TMZON_14_17_SELNG_AMT",
                           "TMZON_17_21_SELNG_AMT", "TMZON_21_24_SELNG_AMT", "MDWK_SELNG_AMT", "WKEND_SELNG_AMT",
                           "ML_SELNG_AMT", "FML_SELNG_AMT", "AGRDE_10_SELNG_AMT", "AGRDE_40_SELNG_AMT",
                           "AGRDE_50_SELNG_AMT", "AGRDE_60_ABOVE_SELNG_AMT"])
sel = sel[sel.SVC_INDUTY_CD.isin(CB)]
salesq = sel.drop(columns="SVC_INDUTY_CD").groupby(["TRDAR_CD", "STDR_YYQU_CD"]).sum()

stor = pd.read_csv(R / "VwsmTrdarStorQq_점포-상권.csv",
                   usecols=["STDR_YYQU_CD", "TRDAR_CD", "SVC_INDUTY_CD", "SIMILR_INDUTY_STOR_CO", "FRC_STOR_CO",
                            "OPBIZ_STOR_CO", "CLSBIZ_STOR_CO"])
cbst = stor[stor.SVC_INDUTY_CD.isin(CB)].groupby(["TRDAR_CD", "STDR_YYQU_CD"])[
    ["SIMILR_INDUTY_STOR_CO", "FRC_STOR_CO", "CLSBIZ_STOR_CO", "OPBIZ_STOR_CO"]].sum()
oth = stor[~stor.SVC_INDUTY_CD.isin(CB)].groupby(["TRDAR_CD", "STDR_YYQU_CD"])[
    ["SIMILR_INDUTY_STOR_CO", "OPBIZ_STOR_CO"]].sum()

fl = pd.read_csv(R / "VwsmTrdarFlpopQq_길단위인구-상권.csv").set_index(["TRDAR_CD", "STDR_YYQU_CD"])["TOT_FLPOP_CO"]
wr = pd.read_csv(R / "VwsmTrdarWrcPopltnQq_직장인구-상권.csv").set_index(["TRDAR_CD", "STDR_YYQU_CD"])["TOT_WRC_POPLTN_CO"]
rp = pd.read_csv(R / "VwsmTrdarRepopQq_상주인구-상권.csv").set_index(["TRDAR_CD", "STDR_YYQU_CD"])["TOT_REPOP_CO"]
ix = pd.read_csv(R / "VwsmTrdarIxQq_상권변화지표-상권.csv")
area = pd.read_csv(R / "TbgisTrdarRelm_영역-상권.csv").set_index("TRDAR_CD")

panel = salesq.join(cbst, how="outer").join(oth, rsuffix="_OTH").join(fl).join(wr).join(rp)
panel = panel.reset_index()


def win(q0, q1):
    """quarters q0..q1 inclusive (as int yyyyq)"""
    qs = []
    y, q = divmod(q0, 10)
    while y * 10 + q <= q1:
        qs.append(y * 10 + q)
        q += 1
        if q == 5:
            y, q = y + 1, 1
    return qs


def agg(qs):
    p = panel[panel.STDR_YYQU_CD.isin(qs)].groupby("TRDAR_CD")
    m = p.mean(numeric_only=True)
    s = p.sum(numeric_only=True)
    out = pd.DataFrame(index=m.index)
    out["sales"] = m.THSMON_SELNG_AMT
    out["cnt"] = m.THSMON_SELNG_CO
    out["stores"] = m.SIMILR_INDUTY_STOR_CO
    out["frc_share"] = s.FRC_STOR_CO / s.SIMILR_INDUTY_STOR_CO
    out["close_rt"] = s.CLSBIZ_STOR_CO / s.SIMILR_INDUTY_STOR_CO
    out["oth_open_rt"] = s.OPBIZ_STOR_CO_OTH / s.SIMILR_INDUTY_STOR_CO_OTH
    out["flpop"] = m.TOT_FLPOP_CO
    out["fixed"] = m.TOT_WRC_POPLTN_CO + m.TOT_REPOP_CO
    out["ticket"] = s.THSMON_SELNG_AMT / s.THSMON_SELNG_CO
    out["young_share"] = (s.AGRDE_20_SELNG_AMT + s.AGRDE_30_SELNG_AMT) / s.THSMON_SELNG_AMT
    out["conv"] = m.THSMON_SELNG_CO / m.TOT_FLPOP_CO
    out["per_store"] = m.THSMON_SELNG_AMT / m.SIMILR_INDUTY_STOR_CO
    return out


def lg(b, a):
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.log(b / a)


def features(qa, qb):
    a, b = agg(qa), agg(qb)
    f = pd.DataFrame(index=b.index)
    f["A1"] = lg(b.flpop, a.flpop)
    f["A2"] = lg(b.fixed, a.fixed)
    f["A3"] = lg(b.conv, a.conv)
    f["B1"] = lg(b.ticket, a.ticket)
    f["B2"] = b.young_share - a.young_share
    f["C1"] = lg(b.stores, a.stores)
    f["C2"] = b.close_rt
    f["D1"] = b.frc_share - a.frc_share
    f["D2"] = b.oth_open_rt
    f["MOM"] = lg(b.per_store, a.per_store)  # 통제 변수: 과거 점포당 매출 성장
    f["sales_b"] = b.sales
    f["stores_b"] = b.stores
    f["per_store_b"] = b.per_store
    return f.replace([np.inf, -np.inf], np.nan)


DIR = {"A1": 1, "A2": 1, "A3": 1, "B1": 1, "B2": 1, "C1": -1, "C2": -1, "D1": 1, "D2": 1}
AXES = {"A": ["A1", "A2", "A3"], "B": ["B1", "B2"], "C": ["C1", "C2"], "D": ["D1", "D2"]}
WEIGHTS = {
    "W0 기본": dict(A=35, B=20, C=30, D=15),
    "W1 동일": dict(A=25, B=25, C=25, D=25),
    "W2 수요중심": dict(A=45, B=20, C=20, D=15),
    "W3 경쟁중심": dict(A=25, B=20, C=40, D=15),
    "W4 선행제외": dict(A=40, B=25, C=35, D=0),
}


def filt(f):
    ok = f.sales_b.notna() & f.stores_b.notna()
    thr = f.loc[ok, "sales_b"].quantile(0.30)
    ok &= f.sales_b >= thr
    ok &= f.stores_b >= 3
    ok &= area.reindex(f.index).TRDAR_SE_CD.ne("U").values
    return f[ok]


def score(f, w):
    pct = pd.DataFrame(index=f.index)
    for k, d in DIR.items():
        x = f[k].clip(f[k].quantile(0.025), f[k].quantile(0.975))
        r = x.rank(pct=True) * 100
        pct[k] = r if d > 0 else 100 - r
    ax = pd.DataFrame({a: pct[c].mean(axis=1) for a, c in AXES.items()})
    tot = sum(ax[a] * w[a] for a in w) / sum(w.values())
    return tot, ax, pct


def target(qa, qb):
    a, b = agg(qa), agg(qb)
    t = lg(b.per_store, a.per_store)
    seoul = np.log((b.sales.sum() / b.stores.sum()) / (a.sales.sum() / a.stores.sum()))
    return (t - seoul).replace([np.inf, -np.inf], np.nan), \
        (lg(b.sales, a.sales) - np.log(b.sales.sum() / a.sales.sum())).replace([np.inf, -np.inf], np.nan)


res = {}
# ---------- backtest ----------
BT = dict(feat=(win(20211, 20214), win(20231, 20234)), tgt=(win(20231, 20234), win(20253, 20262)))
fbt = filt(features(*BT["feat"]))
y, y2 = target(*BT["tgt"])
fbt = fbt.join(y.rename("Y"), how="inner").join(y2.rename("Y2")).dropna(subset=["Y"])
res["bt_n"] = int(len(fbt))
res["ind_corr"] = {k: round(spearmanr(fbt[k], fbt.Y, nan_policy="omit")[0] * DIR[k], 3) for k in DIR}
res["ind_corr"]["MOM(과거 점포당매출 성장)"] = round(spearmanr(fbt.MOM, fbt.Y, nan_policy="omit")[0], 3)
corrm = fbt[list(DIR)].corr(method="spearman").round(2)
res["corr_matrix"] = {"labels": list(DIR), "values": corrm.values.tolist()}
res["max_abs_corr"] = float(corrm.where(~np.eye(len(DIR), dtype=bool)).abs().max().max())
wres = {}
for name, w in WEIGHTS.items():
    s, _, _ = score(fbt, w)
    rho = spearmanr(s, fbt.Y, nan_policy="omit")[0]
    q = s.rank(pct=True)
    top, bot = fbt.Y[q >= 0.8], fbt.Y[q <= 0.2]
    wres[name] = dict(rho=round(rho, 3), top20=round(float(np.expm1(top.median())) * 100, 1),
                      bot20=round(float(np.expm1(bot.median())) * 100, 1),
                      p=float(mannwhitneyu(top.dropna(), bot.dropna(), alternative="greater").pvalue),
                      rho_market=round(spearmanr(s, fbt.Y2, nan_policy="omit")[0], 3))
mom_rho = spearmanr(fbt.MOM, fbt.Y, nan_policy="omit")[0]
res["weights_bt"] = wres
res["momentum_rho"] = round(mom_rho, 3)
best = max(wres, key=lambda k: wres[k]["rho"])
chosen = "W0 기본" if wres[best]["rho"] - wres["W0 기본"]["rho"] < 0.05 else best
res["best"], res["chosen"] = best, chosen
# stability: alt windows (H2 averages)
alt = filt(features(win(20213, 20214), win(20233, 20234)))
ya, _ = target(win(20233, 20234), win(20253, 20254))
alt = alt.join(ya.rename("Y"), how="inner").dropna(subset=["Y"])
sa, _, _ = score(alt, WEIGHTS[chosen])
res["alt_rho"] = round(spearmanr(sa, alt.Y, nan_policy="omit")[0], 3)

# ---------- latest scoring ----------
LAT = (win(20233, 20242), win(20253, 20262))
fl_ = filt(features(*LAT))
ixl = ix[ix.STDR_YYQU_CD == ix.STDR_YYQU_CD.max()].set_index("TRDAR_CD")
fl_ = fl_[ixl.reindex(fl_.index).TRDAR_CHNGE_IX.ne("HL").values]
s, ax, pct = score(fl_, WEIGHTS[chosen])
s_b, _, _ = score(fbt, WEIGHTS[chosen])
out = fl_.join(ax.add_prefix("ax_")).assign(score=s).join(pct.add_prefix("p_"))
out = out.join(area[["TRDAR_CD_NM", "TRDAR_SE_CD_NM", "SIGNGU_CD_NM", "ADSTRD_CD_NM", "XCNTS_VALUE", "YDNTS_VALUE"]])
out = out.join(ixl[["TRDAR_CHNGE_IX_NM"]])
out = out.sort_values("score", ascending=False)
out.to_csv(A / "scores_latest.csv", encoding="utf-8-sig")
fbt.assign(score=s_b).to_csv(A / "backtest.csv", encoding="utf-8-sig")
res["latest_n"] = int(len(out))
res["windows"] = {"backtest_feature": "2021Q1-Q4 평균 → 2023Q1-Q4 평균",
                  "backtest_target": "2023Q1-Q4 평균 → 2025Q3-2026Q2 평균 (점포당 매출, 서울 대비)",
                  "latest_feature": "2023Q3-2024Q2 평균 → 2025Q3-2026Q2 평균"}
cols = ["TRDAR_CD_NM", "TRDAR_SE_CD_NM", "SIGNGU_CD_NM", "ADSTRD_CD_NM", "score", "ax_A", "ax_B", "ax_C", "ax_D",
        "A1", "A2", "A3", "B1", "B2", "C1", "C2", "D1", "D2", "MOM", "sales_b", "stores_b", "per_store_b",
        "TRDAR_CHNGE_IX_NM", "XCNTS_VALUE", "YDNTS_VALUE"]
top = out.head(10)[cols].reset_index()
res["top10"] = json.loads(top.to_json(orient="records", force_ascii=False))
json.dump(res, open(A / "results.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=float)
print(json.dumps({k: v for k, v in res.items() if k not in ("top10", "corr_matrix")}, ensure_ascii=False, indent=1))
print(top[["TRDAR_CD", "TRDAR_CD_NM", "SIGNGU_CD_NM", "score", "ax_A", "ax_B", "ax_C", "ax_D", "per_store_b", "stores_b"]].round(1).to_string())
