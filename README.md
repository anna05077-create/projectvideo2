# 망원역 1번 출점 제안 — 상권 분석 조별 과제

PE 보유 커피·베이커리 전문점의 신규 출점 전략: **마포구 망원역 1번 상권에 "저녁에 붐비는 베이커리 라운지"**.

- **최종 페이지**: [`site/index.html`](site/index.html) (발표 영상 `site/motion.html` + `site/narration.m4a` 포함, 1분 24초)
- **문서**: `docs/` — 지표 설계(metrics), 근거 대장(evidence), 인사이트, 컨셉·인테리어·메뉴·손익, 영상 대본
- **분석 코드**: `analysis/` — `fetch_seoul.py`(데이터 수집) → `score.py`(점수·백테스트) → `validate_v2.py`(재설계 검증) → `pnl.py`(손익)
- **데이터**: 서울 열린데이터 광장, 서울시 상권분석서비스(2024 개편 상권 1,650개, 2021Q1~2026Q2). 원본 CSV는 용량 때문에 제외 — `.env`에 `SEOUL_API_KEY=...`를 넣고 `python analysis/fetch_seoul.py`, `python analysis/fetch_store_q.py`로 재수집
