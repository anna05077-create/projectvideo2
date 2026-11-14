"""손익 시뮬레이션 (P5). 모든 입력은 docs/concept.md '공통 가정' 표에서 인용.
실행: python analysis/pnl.py  (단위: 만 원)"""
import sys; sys.stdout.reconfigure(encoding="utf-8")
CUST = 8900          # 월 객수 [concept.md 공통 가정]
AOV = 1.5            # 객단가 15,000원 = 1.5만 원
COGS, UTIL, CARD, MKT = 0.32, 0.04, 0.03, 0.02
LABOR, RENT = 3300, 1100
CAPEX = 45000        # 초기 투자 4.5억 원
DEP = CAPEX / 60
E14_Q = 46000        # 상권 커피·제과 분기 매출 4.6억 원 [E14]

def pnl(cust=CUST, aov=AOV, rent=RENT):
    s = cust * aov
    c = {"원가": s*COGS, "인건비": LABOR, "임대료": rent, "관리비·공과금": s*UTIL,
         "카드·배달·기타": s*CARD, "마케팅": s*MKT}
    ebitda = s - sum(c.values())
    op = ebitda - DEP
    return dict(매출=s, **c, EBITDA=ebitda, 감가상각=DEP, 영업이익=op, 이익률=op/s*100)

sc = {"보수(-20%)": pnl(CUST*0.8), "기본": pnl(), "낙관(+15%)": pnl(CUST*1.15)}
keys = ["매출","원가","인건비","임대료","관리비·공과금","카드·배달·기타","마케팅","EBITDA","감가상각","영업이익"]
print("항목 | " + " | ".join(sc))
for k in keys:
    print(f"{k} | " + " | ".join(f"{v[k]:,.0f}" for v in sc.values()))
print("영업이익률(%) | " + " | ".join(f"{v['이익률']:.1f}" for v in sc.values()))
for n in ["보수(-20%)", "기본", "낙관(+15%)"]:
    print(f"투자회수 {n}: {CAPEX/sc[n]['EBITDA']:.1f}개월")
ramp = pnl(CUST*0.8)  # 초기 6개월 = 기본의 80%
cum = ramp["EBITDA"]*6
m = 6
while cum < CAPEX:
    m += 1; cum += sc["기본"]["EBITDA"]
print(f"램프업(6개월 80%) 월 EBITDA {ramp['EBITDA']:,.0f}, 영업이익 {ramp['영업이익']:,.0f}; 회수 {m}개월")
var = 1 - COGS - UTIL - CARD - MKT
be = (LABOR + RENT + DEP) / var
print(f"공헌이익률 {var*100:.0f}% / 손익분기 월매출 {be:,.0f} / 월객수 {be/AOV:,.0f} / 일객수 {be/AOV/30:,.0f}")
print("민감도(영업이익):")
for lab, kw in [("객단가 -10%", dict(aov=AOV*0.9)), ("객단가 +10%", dict(aov=AOV*1.1)),
                ("임대료 -20%", dict(rent=RENT*0.8)), ("임대료 +20%", dict(rent=RENT*1.2))]:
    r = pnl(**kw); print(f"  {lab}: {r['영업이익']:,.0f} ({r['이익률']:.1f}%)")
q = sc["기본"]["매출"]*3
print(f"기본 분기매출 {q:,.0f} / 상권 분기 {E14_Q:,} = {q/E14_Q*100:.0f}%")
