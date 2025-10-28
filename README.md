# 📚 옵셋 도서 제작 관리 (Streamlit)

도서 사양 관리 / 발주 입력 / 발주 조회(취소, 계산서 체크)까지 가능한 경량 웹앱입니다.  
- 프론트/백엔드: **Streamlit + SQLite(SQLAlchemy)**
- 주요 기능:
  - 📘 도서 사양 등록/수정/삭제 (내지 분할 문자열, 판형/표지/제본/후가공 등)
  - 📦 발주 입력 (발주일·제작처·항목별 단가/비용 → 공급가/VAT/총액 자동 계산)
  - 🔍 발주 조회 (도서/부수 검색, 상세 expander, ✖️ 취소, ✅ 계산서 발행 체크)

---

## 🚀 로컬 실행

```bash
# 1) 의존성 설치
pip install -r requirements.txt

# 2) 실행
streamlit run app.py
