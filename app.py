# -*- coding: utf-8 -*-
import os
from datetime import date

import streamlit as st
import pandas as pd

from sqlalchemy import (
    create_engine, Column, Integer, String, Text, text
)
from sqlalchemy.orm import declarative_base, sessionmaker
from urllib.parse import quote_plus

# =========================================================
# 페이지 설정
# =========================================================
st.set_page_config(
    page_title="📚 옵셋 도서 제작 관리",
    layout="wide",
    initial_sidebar_state="expanded",
)
# --- 항상 보이는 디버그 (로그인보다 위) ---
st.caption("🔧 app booted")
keys = list(st.secrets.keys())
st.caption("🔑 secrets keys = " + str(keys))
st.caption("🔒 has DB_HOST? " + str("DB_HOST" in st.secrets))


# =========================================================
# 🔐 접근 제한 (비밀번호 게이트)
#   - Secrets(APP_PASSWORD)가 있으면 사용, 없으면 기본값 사용
# =========================================================
APP_PASSWORD = st.secrets.get("APP_PASSWORD", "bookk2025")

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

def _login_form():
    st.title("🔒 접근 제한")
    pw = st.text_input("비밀번호를 입력하세요", type="password", key="pw_input")
    if st.button("접속", key="login_btn"):
        if (pw or "").strip() == str(APP_PASSWORD).strip():
            st.session_state.authenticated = True
            st.success("✅ 인증되었습니다.")
            st.rerun()
        else:
            st.error("❌ 비밀번호가 올바르지 않습니다.")

if not st.session_state.authenticated:
    _login_form()
    st.stop()

# ==========================
# DB 연결
#  - Supabase(Session pooler 6543) 권장
#  - Secrets에 값이 없으면 SQLite로 로컬 폴백
# ==========================
from urllib.parse import quote_plus  # ← 꼭 추가

def build_engine_from_secrets_or_sqlite():
    """Supabase 연결(정상), 실패/미설정 시 SQLite로 폴백."""
    try:
        st.write("🔧 build_engine_from_secrets_or_sqlite() 시작됨")
        st.write("DEBUG/keys:", list(st.secrets.keys()))

        host = st.secrets["DB_HOST"].strip()
        port = st.secrets.get("DB_PORT", "6543").strip()
        user = st.secrets.get("DB_USER", "postgres").strip()
        pwd = quote_plus(st.secrets["DB_PASS"])  # ← 여기 인코딩 필수
        name = st.secrets.get("DB_NAME", "postgres").strip()

        url = (
            f"postgresql+psycopg2://{user}:{pwd}@"
            f"{host}:{port}/{name}?sslmode=require"
        )
        st.write("DEBUG/url:", url)  # 👈 여기에 한 줄 추가!

        eng = create_engine(url, echo=False, pool_pre_ping=True)

        # 연결 테스트
        with eng.connect() as conn:
            conn.execute(text("select 1"))
            st.caption("🟢 DB 연결: Supabase(Session pooler)")
        return eng

    except Exception as e:
        st.error(f"DB 연결 실패: {e}")

        # 폴백: SQLite 로컬 파일
        os.makedirs("data", exist_ok=True)
        eng = create_engine("sqlite:///data/app.db", echo=False)
        st.warning("🟡 DB 연결 실패: 로컬 SQLite로 대체합니다.")
        return eng


engine = build_engine_from_secrets_or_sqlite()

Base = declarative_base()
SessionLocal = sessionmaker(bind=engine)
st.caption(f"🔎 engine.url = {engine.url}")
st.caption(f"🔎 dialect = {engine.dialect.name}")   # postgresql 이면 OK, sqlite면 폴백
# =========================================================
# 모델
# =========================================================
class Book(Base):
    __tablename__ = "books"
    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String, nullable=False)    # 도서명
    format = Column(String)                   # 판형
    cover_paper = Column(String)              # 표지 용지
    cover_color = Column(String)              # 표지 도수/양단면
    inner_spec = Column(Text)                 # 내지 사양(문자열)
    total_pages = Column(Integer)             # 총 페이지
    endpaper = Column(String)                 # 면지 여부
    wing = Column(String)                     # 날개 여부
    binding = Column(String)                  # 제본 방식
    postprocess = Column(String)              # 후가공

class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    book_id = Column(Integer, nullable=False)
    qty = Column(Integer, nullable=False)
    date = Column(String, nullable=False)  # YYYY-MM-DD
    vendor = Column(String)                # 제작처

    # 합계
    supply_price = Column(Integer)  # VAT 제외
    vat_price = Column(Integer)     # 10%
    total_price = Column(Integer)   # VAT 포함

    # 권당 가격(선택) - 단순 계산용
    unit_price = Column(Integer)

    # 표지
    cover_ctp_unit = Column(Integer); cover_ctp_cost = Column(Integer)
    cover_print_unit = Column(Integer); cover_print_cost = Column(Integer)
    cover_paper_unit = Column(Integer); cover_paper_cost = Column(Integer)

    # 본문1
    inner1_ctp_unit = Column(Integer); inner1_ctp_cost = Column(Integer)
    inner1_print_unit = Column(Integer); inner1_print_cost = Column(Integer)
    inner1_paper_unit = Column(Integer); inner1_paper_cost = Column(Integer)

    # 본문2(옵션)
    inner2_ctp_unit = Column(Integer); inner2_ctp_cost = Column(Integer)
    inner2_print_unit = Column(Integer); inner2_print_cost = Column(Integer)
    inner2_paper_unit = Column(Integer); inner2_paper_cost = Column(Integer)

    # 면지
    endpaper_unit = Column(Integer); endpaper_cost = Column(Integer)

    # 제본
    binding_unit = Column(Integer); binding_cost = Column(Integer)

    # 후가공
    laminating_unit = Column(Integer); laminating_cost = Column(Integer)
    epoxy_unit = Column(Integer); epoxy_cost = Column(Integer)
    plate_unit = Column(Integer); plate_cost = Column(Integer)
    film_unit = Column(Integer); film_cost = Column(Integer)

    # 기타
    misc_unit = Column(Integer); misc_cost = Column(Integer)
    delivery_unit = Column(Integer); delivery_cost = Column(Integer)

    # 편의 필드
    invoice_issued = Column(Integer, default=0)  # 0/1
    total_override = Column(Integer)             # 총액 수동입력(우선표시)
    memo = Column(Text)                          # 메모

Base.metadata.create_all(bind=engine)

# =========================================================
# Postgres/SQLite 겸용 컬럼 보장(마이그레이션)
#   - Postgres는 information_schema, SQLite는 PRAGMA 사용
# =========================================================
def _table_columns_pg(table_name: str) -> set[str]:
    q = text("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = :t
    """)
    with engine.connect() as conn:
        rows = conn.execute(q, {"t": table_name}).fetchall()
        return {r[0] for r in rows}

def _table_columns_sqlite(table_name: str) -> set[str]:
    with engine.connect() as conn:
        rows = conn.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
        # row: (cid, name, type, notnull, dflt_value, pk)
        return {r[1] for r in rows}

def ensure_orders_columns():
    # 엔진 종류 판별
    dialect = engine.dialect.name.lower()
    if dialect == "postgresql":
        cols = _table_columns_pg("orders")
    else:
        cols = _table_columns_sqlite("orders")

    stmts = []
    def add(stmt: str):
        stmts.append(stmt)

    # 누락 시 추가
    if "vendor" not in cols:
        add("ALTER TABLE orders ADD COLUMN vendor TEXT")
    if "unit_price" not in cols:
        add("ALTER TABLE orders ADD COLUMN unit_price INTEGER")
    if "invoice_issued" not in cols:
        add("ALTER TABLE orders ADD COLUMN invoice_issued INTEGER DEFAULT 0")
    if "total_override" not in cols:
        add("ALTER TABLE orders ADD COLUMN total_override INTEGER")
    if "memo" not in cols:
        add("ALTER TABLE orders ADD COLUMN memo TEXT")

    if not stmts:
        return

    with engine.begin() as conn:
        for s in stmts:
            try:
                conn.execute(text(s))
            except Exception:
                # 이미 있는 경우 등 에러 무시(엔진별 차이)
                pass

ensure_orders_columns()

# =========================================================
# 공용 함수
# =========================================================
def get_session():
    return SessionLocal()

def _to_int(x):
    try:
        return int(x)
    except:
        return 0

def calc_supply_and_vat(data_dict: dict):
    """*_cost 항목들을 합쳐 공급가/부가세/총액 계산"""
    keys_to_sum = [
        "cover_ctp_cost","cover_print_cost","cover_paper_cost",
        "inner1_ctp_cost","inner1_print_cost","inner1_paper_cost",
        "inner2_ctp_cost","inner2_print_cost","inner2_paper_cost",
        "endpaper_cost","binding_cost",
        "laminating_cost","epoxy_cost","plate_cost","film_cost",
        "misc_cost","delivery_cost"
    ]
    supply = sum(_to_int(data_dict.get(k, 0)) for k in keys_to_sum)
    vat = int(round(supply * 0.10))
    total = supply + vat
    return supply, vat, total

# =========================================================
# Book CRUD
# =========================================================
def add_book(book: dict):
    s = get_session()
    try:
        s.add(Book(**book))
        s.commit()
    finally:
        s.close()

def get_books():
    s = get_session()
    try:
        return s.query(Book).order_by(Book.id.desc()).all()
    finally:
        s.close()

def update_book(book_id: int, fields: dict):
    s = get_session()
    try:
        b = s.query(Book).filter(Book.id == book_id).first()
        if b:
            for k, v in fields.items():
                setattr(b, k, v)
            s.commit()
    finally:
        s.close()

def delete_book(book_id: int):
    s = get_session()
    try:
        b = s.query(Book).filter(Book.id == book_id).first()
        if b:
            s.delete(b)
            s.commit()
    finally:
        s.close()

# =========================================================
# Order CRUD
# =========================================================
def add_order(order_data: dict):
    s = get_session()
    try:
        # 비용 합계 기반 계산
        supply, vat, total = calc_supply_and_vat(order_data)

        # 권당 가격이 있으면 qty*unit_price를 공급가로 사용(단순)
        qty = _to_int(order_data.get("qty", 0))
        unit_price = _to_int(order_data.get("unit_price", 0))
        if unit_price and qty:
            supply = qty * unit_price
            vat = int(round(supply * 0.10))
            total = supply + vat

        o = Order(
            book_id=order_data["book_id"],
            qty=qty,
            date=order_data["date"],
            vendor=order_data.get("vendor", ""),
            supply_price=supply, vat_price=vat, total_price=total,
            unit_price=unit_price,

            cover_ctp_unit=_to_int(order_data.get("cover_ctp_unit", 0)),
            cover_ctp_cost=_to_int(order_data.get("cover_ctp_cost", 0)),
            cover_print_unit=_to_int(order_data.get("cover_print_unit", 0)),
            cover_print_cost=_to_int(order_data.get("cover_print_cost", 0)),
            cover_paper_unit=_to_int(order_data.get("cover_paper_unit", 0)),
            cover_paper_cost=_to_int(order_data.get("cover_paper_cost", 0)),

            inner1_ctp_unit=_to_int(order_data.get("inner1_ctp_unit", 0)),
            inner1_ctp_cost=_to_int(order_data.get("inner1_ctp_cost", 0)),
            inner1_print_unit=_to_int(order_data.get("inner1_print_unit", 0)),
            inner1_print_cost=_to_int(order_data.get("inner1_print_cost", 0)),
            inner1_paper_unit=_to_int(order_data.get("inner1_paper_unit", 0)),
            inner1_paper_cost=_to_int(order_data.get("inner1_paper_cost", 0)),

            inner2_ctp_unit=_to_int(order_data.get("inner2_ctp_unit", 0)),
            inner2_ctp_cost=_to_int(order_data.get("inner2_ctp_cost", 0)),
            inner2_print_unit=_to_int(order_data.get("inner2_print_unit", 0)),
            inner2_print_cost=_to_int(order_data.get("inner2_print_cost", 0)),
            inner2_paper_unit=_to_int(order_data.get("inner2_paper_unit", 0)),
            inner2_paper_cost=_to_int(order_data.get("inner2_paper_cost", 0)),

            endpaper_unit=_to_int(order_data.get("endpaper_unit", 0)),
            endpaper_cost=_to_int(order_data.get("endpaper_cost", 0)),
            binding_unit=_to_int(order_data.get("binding_unit", 0)),
            binding_cost=_to_int(order_data.get("binding_cost", 0)),

            laminating_unit=_to_int(order_data.get("laminating_unit", 0)),
            laminating_cost=_to_int(order_data.get("laminating_cost", 0)),
            epoxy_unit=_to_int(order_data.get("epoxy_unit", 0)),
            epoxy_cost=_to_int(order_data.get("epoxy_cost", 0)),
            plate_unit=_to_int(order_data.get("plate_unit", 0)),
            plate_cost=_to_int(order_data.get("plate_cost", 0)),
            film_unit=_to_int(order_data.get("film_unit", 0)),
            film_cost=_to_int(order_data.get("film_cost", 0)),
            misc_unit=_to_int(order_data.get("misc_unit", 0)),
            misc_cost=_to_int(order_data.get("misc_cost", 0)),
            delivery_unit=_to_int(order_data.get("delivery_unit", 0)),
            delivery_cost=_to_int(order_data.get("delivery_cost", 0)),
        )
        s.add(o)
        s.commit()
    finally:
        s.close()

def get_orders(book_id: int, qty_filter: int | None = None):
    s = get_session()
    try:
        q = s.query(Order).filter(Order.book_id == book_id)
        if qty_filter:
            q = q.filter(Order.qty == qty_filter)
        return q.order_by(Order.id.desc()).all()
    finally:
        s.close()

def delete_order(order_id: int):
    s = get_session()
    try:
        o = s.query(Order).filter(Order.id == order_id).first()
        if o:
            s.delete(o)
            s.commit()
    finally:
        s.close()

def set_invoice_status(order_id: int, is_issued: bool):
    s = get_session()
    try:
        o = s.query(Order).filter(Order.id == order_id).first()
        if o:
            o.invoice_issued = 1 if is_issued else 0
            s.commit()
    finally:
        s.close()

def set_order_override_and_memo(order_id: int, total_override: int, memo: str):
    s = get_session()
    try:
        o = s.query(Order).filter(Order.id == order_id).first()
        if o:
            o.total_override = _to_int(total_override)
            o.memo = (memo or "").strip()
            s.commit()
    finally:
        s.close()

# =========================================================
# 페이지 1) 🔍 발주 조회
#   - 총액 수동입력, 메모 열 편집 + 저장
# =========================================================
def render_order_query_page():
    st.header("🔍 발주 조회")

    # 상태 초기화
    if "confirm_delete_order" not in st.session_state:
        st.session_state["confirm_delete_order"] = None

    # 도서 검색/선택
    search_title = st.text_input("도서명 검색", key="query_search_title")
    books = get_books()
    filtered_books = [b for b in books if (search_title or "").strip() in (b.title or "")]
    if not search_title:
        filtered_books = books

    if not filtered_books:
        st.info("검색된 도서가 없습니다.")
        return

    selected_book = st.selectbox(
        "도서 선택",
        options=filtered_books,
        format_func=lambda x: f"{x.title} ({x.format})",
        key="query_book_select"
    )
    if not selected_book:
        return

    # 부수 필터
    qty_filter_text = st.text_input("부수 검색 (숫자만 입력)", key="query_qty_filter")
    orders = get_orders(
        selected_book.id,
        int(qty_filter_text) if qty_filter_text.isdigit() else None
    )

    if not orders:
        st.info("발주 내역이 없습니다.")
        return

    # 요약 표 (편집 가능)
    df_orig = pd.DataFrame([{
        "id": o.id,
        "발주일": o.date,
        "제작처": o.vendor or "",
        "부수": o.qty,
        "권당 가격": o.unit_price or 0,
        "공급가(VAT 제외)": o.supply_price or 0,
        "부가세": o.vat_price or 0,
        "총액(VAT 포함)": (o.total_override if (o.total_override not in (None, 0)) else (o.total_price or 0)),
        "총액 수동입력": o.total_override or 0,
        "메모": o.memo or "",
        "계산서 발행": bool(getattr(o, "invoice_issued", 0)),
    } for o in orders])

    edited = st.data_editor(
        df_orig,
        use_container_width=True,
        hide_index=True,
        column_order=[
            "발주일", "제작처", "부수", "권당 가격",
            "공급가(VAT 제외)", "부가세", "총액(VAT 포함)",
            "총액 수동입력", "메모", "계산서 발행", "id"
        ],
        column_config={
            "계산서 발행": st.column_config.CheckboxColumn("계산서 발행", help="발행 시 체크"),
            "총액 수동입력": st.column_config.NumberColumn("총액 수동입력(직접 입력 시 표시 우선)"),
            "메모": st.column_config.TextColumn("메모", help="자유 메모"),
            "id": st.column_config.Column("id", help="내부키", disabled=True),
        },
        key="order_invoice_editor"
    )

    # 변경 저장 (체크박스/수동총액/메모)
    if st.button("변경 저장", key="order_invoice_save"):
        orig = df_orig.set_index("id")
        new = edited.set_index("id")

        changed_count = 0

        # 계산서 발행 변경
        if "계산서 발행" in new.columns and "계산서 발행" in orig.columns:
            for oid in new.index:
                old_val = bool(orig.at[oid, "계산서 발행"])
                new_val = bool(new.at[oid, "계산서 발행"])
                if old_val != new_val:
                    set_invoice_status(int(oid), new_val)
                    changed_count += 1

        # 총액 수동입력/메모 변경
        def _safe_int(v):
            try: return int(v)
            except: return 0

        for oid in new.index:
            old_override = _safe_int(orig.at[oid, "총액 수동입력"]) if "총액 수동입력" in orig.columns else 0
            new_override = _safe_int(new.at[oid, "총액 수동입력"]) if "총액 수동입력" in new.columns else 0

            old_memo = str(orig.at[oid, "메모"]) if "메모" in orig.columns else ""
            new_memo = str(new.at[oid, "메모"]) if "메모" in new.columns else ""

            if (new_override != old_override) or (new_memo != old_memo):
                set_order_override_and_memo(int(oid), new_override, new_memo)
                changed_count += 1

        if changed_count == 0:
            st.info("변경된 항목이 없습니다.")
        else:
            st.success(f"{changed_count}건이 저장되었습니다.")
            st.rerun()

    st.markdown("### 세부 항목")

    for o in orders:
        # 표기용 총액: 수동입력이 있으면 우선
        shown_total = o.total_override if (o.total_override not in (None, 0)) else (o.total_price or 0)
        header = f"📄 {o.date} · {o.qty}부 · 총액 {shown_total:,}원"
        with st.expander(header, expanded=False):
            st.markdown(
                f"**공급가:** {(o.supply_price or 0):,}원 · "
                f"**부가세:** {(o.vat_price or 0):,}원 · "
                f"**총액(표시):** {shown_total:,}원"
            )
            st.write(f"• 제작처: {o.vendor or '—'}")
            st.write(f"• 권당 가격: {(o.unit_price or 0):,}원")
            st.write(f"• 계산서 발행: {'✅ 발행됨' if getattr(o, 'invoice_issued', 0) else '❌ 미발행'}")
            if o.memo:
                st.write(f"• 메모: {o.memo}")

            # 보조 출력 함수
            def show_line(label, unit, cost):
                u = unit or 0
                c = cost or 0
                if u or c:
                    st.write(f"- {label} 단가: {u:,} | 비용: {c:,}원")

            st.subheader("표지")
            show_line("CTP", o.cover_ctp_unit, o.cover_ctp_cost)
            show_line("인쇄", o.cover_print_unit, o.cover_print_cost)
            show_line("종이", o.cover_paper_unit, o.cover_paper_cost)

            st.subheader("본문1")
            show_line("CTP", o.inner1_ctp_unit, o.inner1_ctp_cost)
            show_line("인쇄", o.inner1_print_unit, o.inner1_print_cost)
            show_line("종이", o.inner1_paper_unit, o.inner1_paper_cost)

            if (o.inner2_ctp_cost or 0) or (o.inner2_print_cost or 0) or (o.inner2_paper_cost or 0):
                st.subheader("본문2")
                show_line("CTP", o.inner2_ctp_unit, o.inner2_ctp_cost)
                show_line("인쇄", o.inner2_print_unit, o.inner2_print_cost)
                show_line("종이", o.inner2_paper_unit, o.inner2_paper_cost)

            st.subheader("면지 / 제본")
            show_line("면지", o.endpaper_unit, o.endpaper_cost)
            show_line("제본", o.binding_unit, o.binding_cost)

            st.subheader("후가공")
            show_line("라미네이팅", o.laminating_unit, o.laminating_cost)
            show_line("에폭시", o.epoxy_unit, o.epoxy_cost)
            show_line("제판대", o.plate_unit, o.plate_cost)
            show_line("필름", o.film_unit, o.film_cost)

            # 발주 취소
            cols = st.columns(2)
            with cols[0]:
                if st.button("✖️ 발주 취소", key=f"cancel_order_btn_{o.id}"):
                    st.session_state["confirm_delete_order"] = o.id
                    st.rerun()

            if st.session_state.get("confirm_delete_order") == o.id:
                st.warning("정말 이 발주를 취소(삭제)하시겠습니까? 이 작업은 되돌릴 수 없습니다.")
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("✅ 예, 삭제합니다", key=f"confirm_delete_yes_{o.id}"):
                        delete_order(o.id)
                        st.success("발주가 취소되었습니다.")
                        st.session_state["confirm_delete_order"] = None
                        st.rerun()
                with c2:
                    if st.button("취소", key=f"confirm_delete_no_{o.id}"):
                        st.session_state["confirm_delete_order"] = None
                        st.rerun()

# =========================================================
# 페이지 2) 📦 발주 입력
#   - 1) 발주일 2) 제작부수 3) 권당 가격
#   - 4) 총 합계(= 부수 x 권당가격) 5) VAT(10%) 포함 총액
#   - 6) 제작처
# =========================================================
def render_order_input_page():
    st.header("📦 발주 입력")

    books = get_books()
    if not books:
        st.info("도서가 아직 없습니다. 먼저 도서 사양을 등록해 주세요.")
        return

    book_choice = st.selectbox(
        "도서 선택", options=books,
        format_func=lambda x: f"{x.title} ({x.format})",
        key="order_book_select"
    )

    with st.form("order_form_detail"):
        c1, c2, c3 = st.columns([1,1,1])
        with c1:
            qty = st.number_input("제작 부수", min_value=1, step=100, value=1000)
        with c2:
            order_date = st.date_input("발주일", value=date.today())
        with c3:
            vendor = st.text_input("제작처", "")
        u1, u2 = st.columns([1,1])
        with u1:
            unit_price = st.number_input("권당 가격", min_value=0, step=100, value=0)
        with u2:
            st.caption("권당 가격 입력 시 비용 항목 대신 단순계산(부수×권당가격)을 사용합니다.")

        # --- 비용 항목 ---
        with st.expander("표지 (CTP/인쇄/종이)", expanded=False):
            cc1, cc2, cc3, cc4, cc5, cc6 = st.columns(6)
            with cc1: cover_ctp_unit = st.number_input("CTP 단가", min_value=0, step=1, value=0)
            with cc2: cover_ctp_cost = st.number_input("CTP 비용", min_value=0, step=1000, value=0)
            with cc3: cover_print_unit = st.number_input("인쇄 단가", min_value=0, step=1, value=0)
            with cc4: cover_print_cost = st.number_input("인쇄 비용", min_value=0, step=1000, value=0)
            with cc5: cover_paper_unit = st.number_input("종이 단가", min_value=0, step=1, value=0)
            with cc6: cover_paper_cost = st.number_input("종이 비용", min_value=0, step=1000, value=0)

        with st.expander("본문1 (CTP/인쇄/종이)", expanded=False):
            i1c1, i1c2, i1c3, i1c4, i1c5, i1c6 = st.columns(6)
            with i1c1: inner1_ctp_unit = st.number_input("CTP 단가(1)", min_value=0, step=1, value=0)
            with i1c2: inner1_ctp_cost = st.number_input("CTP 비용(1)", min_value=0, step=1000, value=0)
            with i1c3: inner1_print_unit = st.number_input("인쇄 단가(1)", min_value=0, step=1, value=0)
            with i1c4: inner1_print_cost = st.number_input("인쇄 비용(1)", min_value=0, step=1000, value=0)
            with i1c5: inner1_paper_unit = st.number_input("종이 단가(1)", min_value=0, step=1, value=0)
            with i1c6: inner1_paper_cost = st.number_input("종이 비용(1)", min_value=0, step=1000, value=0)

        use_inner2 = st.checkbox("본문2 사용", value=False, key="use_inner2_checkbox")
        inner2_ctp_unit = inner2_ctp_cost = inner2_print_unit = inner2_print_cost = inner2_paper_unit = inner2_paper_cost = 0
        if use_inner2:
            with st.expander("본문2 (CTP/인쇄/종이)", expanded=False):
                i2c1, i2c2, i2c3, i2c4, i2c5, i2c6 = st.columns(6)
                with i2c1: inner2_ctp_unit = st.number_input("CTP 단가(2)", min_value=0, step=1, value=0)
                with i2c2: inner2_ctp_cost = st.number_input("CTP 비용(2)", min_value=0, step=1000, value=0)
                with i2c3: inner2_print_unit = st.number_input("인쇄 단가(2)", min_value=0, step=1, value=0)
                with i2c4: inner2_print_cost = st.number_input("인쇄 비용(2)", min_value=0, step=1000, value=0)
                with i2c5: inner2_paper_unit = st.number_input("종이 단가(2)", min_value=0, step=1, value=0)
                with i2c6: inner2_paper_cost = st.number_input("종이 비용(2)", min_value=0, step=1000, value=0)

        with st.expander("면지 / 제본", expanded=False):
            e1, e2, b1, b2 = st.columns(4)
            with e1: endpaper_unit = st.number_input("면지 단가", min_value=0, step=1, value=0)
            with e2: endpaper_cost = st.number_input("면지 비용", min_value=0, step=1000, value=0)
            with b1: binding_unit = st.number_input("제본 단가", min_value=0, step=1, value=0)
            with b2: binding_cost = st.number_input("제본 비용", min_value=0, step=1000, value=0)

        with st.expander("후가공 (라미/에폭시/제판/필름)", expanded=False):
            l1,l2,e3,e4,p1,p2,f1,f2 = st.columns(8)
            with l1: laminating_unit = st.number_input("라미 단가", min_value=0, step=1, value=0)
            with l2: laminating_cost = st.number_input("라미 비용", min_value=0, step=1000, value=0)
            with e3: epoxy_unit = st.number_input("에폭시 단가", min_value=0, step=1, value=0)
            with e4: epoxy_cost = st.number_input("에폭시 비용", min_value=0, step=1000, value=0)
            with p1: plate_unit = st.number_input("제판대 단가", min_value=0, step=1, value=0)
            with p2: plate_cost = st.number_input("제판대 비용", min_value=0, step=1000, value=0)
            with f1: film_unit = st.number_input("필름 단가", min_value=0, step=1, value=0)
            with f2: film_cost = st.number_input("필름 비용", min_value=0, step=1000, value=0)

        with st.expander("기타 (공과잡비/배송비)", expanded=False):
            m1,m2,d1,d2 = st.columns(4)
            with m1: misc_unit = st.number_input("공과잡비 단가", min_value=0, step=1, value=0)
            with m2: misc_cost = st.number_input("공과잡비 비용", min_value=0, step=1000, value=0)
            with d1: delivery_unit = st.number_input("배송비 단가", min_value=0, step=1, value=0)
            with d2: delivery_cost = st.number_input("배송비 비용", min_value=0, step=1000, value=0)

        # 합계 미리보기
        preview = {
            "cover_ctp_cost":cover_ctp_cost, "cover_print_cost":cover_print_cost, "cover_paper_cost":cover_paper_cost,
            "inner1_ctp_cost":inner1_ctp_cost, "inner1_print_cost":inner1_print_cost, "inner1_paper_cost":inner1_paper_cost,
            "inner2_ctp_cost":inner2_ctp_cost, "inner2_print_cost":inner2_print_cost, "inner2_paper_cost":inner2_paper_cost,
            "endpaper_cost":endpaper_cost, "binding_cost":binding_cost,
            "laminating_cost":laminating_cost, "epoxy_cost":epoxy_cost, "plate_cost":plate_cost, "film_cost":film_cost,
            "misc_cost":misc_cost, "delivery_cost":delivery_cost
        }

        # 권당가격이 있으면 단순 계산, 없으면 상세 비용 합산
        if unit_price and qty:
            sup = qty * unit_price
            vat = int(round(sup * 0.10))
            tot = sup + vat
        else:
            sup, vat, tot = calc_supply_and_vat(preview)

        st.markdown(
            f"**공급가(VAT 제외):** {sup:,}원 &nbsp;&nbsp; "
            f"**부가세(10%):** {vat:,}원 &nbsp;&nbsp; "
            f"**총액(VAT 포함):** {tot:,}원"
        )

        if st.form_submit_button("📝 발주 저장"):
            payload = {
                "book_id": book_choice.id, "qty": qty, "date": str(order_date), "vendor": vendor,
                "unit_price": unit_price,
                "cover_ctp_unit":cover_ctp_unit, "cover_ctp_cost":cover_ctp_cost,
                "cover_print_unit":cover_print_unit, "cover_print_cost":cover_print_cost,
                "cover_paper_unit":cover_paper_unit, "cover_paper_cost":cover_paper_cost,
                "inner1_ctp_unit":inner1_ctp_unit, "inner1_ctp_cost":inner1_ctp_cost,
                "inner1_print_unit":inner1_print_unit, "inner1_print_cost":inner1_print_cost,
                "inner1_paper_unit":inner1_paper_unit, "inner1_paper_cost":inner1_paper_cost,
                "inner2_ctp_unit":inner2_ctp_unit, "inner2_ctp_cost":inner2_ctp_cost,
                "inner2_print_unit":inner2_print_unit, "inner2_print_cost":inner2_print_cost,
                "inner2_paper_unit":inner2_paper_unit, "inner2_paper_cost":inner2_paper_cost,
                "endpaper_unit":endpaper_unit, "endpaper_cost":endpaper_cost,
                "binding_unit":binding_unit, "binding_cost":binding_cost,
                "laminating_unit":laminating_unit, "laminating_cost":laminating_cost,
                "epoxy_unit":epoxy_unit, "epoxy_cost":epoxy_cost,
                "plate_unit":plate_unit, "plate_cost":plate_cost,
                "film_unit":film_unit, "film_cost":film_cost,
                "misc_unit":misc_unit, "misc_cost":misc_cost,
                "delivery_unit":delivery_unit, "delivery_cost":delivery_cost,
            }
            add_order(payload)
            st.success("✅ 발주가 저장되었습니다!")
            st.rerun()

# =========================================================
# 페이지 3) 📘 도서 사양 등록
# =========================================================
def render_book_spec_page():
    st.header("📘 도서 사양 등록")

    with st.form("book_form"):
        col1, col2 = st.columns(2)
        with col1:
            title = st.text_input("도서명", "")
            format_ = st.text_input("판형 (예: 46판 / B5 / A5 / A4 등)", "")
            cover_paper = st.text_input("표지 용지 (예: 아르떼 / 스노우 등)", "")
            cover_color = st.text_input("표지 도수/양단면 (예: 4도 양면)", "")
        with col2:
            total_pages = st.number_input("총 페이지 수", min_value=0, step=1, value=0)
            endpaper = st.selectbox("면지 여부", ["없음", "있음"])
            wing = st.selectbox("날개 여부", ["없음", "있음"])
            binding = st.text_input("제본 방식 (예: 무선제본 등)", "")
        inner_spec = st.text_area("내지 사양(문자열, 분할 시 구분자로 작성)", "")

        if st.form_submit_button("➕ 도서 추가"):
            add_book({
                "title": title.strip(),
                "format": format_.strip(),
                "cover_paper": cover_paper.strip(),
                "cover_color": cover_color.strip(),
                "inner_spec": inner_spec.strip(),
                "total_pages": int(total_pages),
                "endpaper": endpaper,
                "wing": wing,
                "binding": binding.strip(),
                "postprocess": "",
            })
            st.success(f"'{title}' 도서를 등록했습니다.")
            st.rerun()

    st.subheader("📖 등록된 도서 목록")
    books = get_books()
    if not books:
        st.info("아직 등록된 도서가 없습니다.")
        return

    if "edit_mode" not in st.session_state:
        st.session_state["edit_mode"] = False
        st.session_state["edit_id"] = None

    for b in books:
        with st.expander(f"📘 {b.title} ({b.format})"):
            st.write(f"**표지:** {b.cover_paper}, {b.cover_color}")
            st.write(f"**내지:** {b.inner_spec} (총 {b.total_pages}쪽)")
            st.write(f"**면지:** {b.endpaper} · **날개:** {b.wing}")
            st.write(f"**제본:** {b.binding}")
            if b.postprocess:
                st.write(f"**후가공:** {b.postprocess}")

            c1, c2 = st.columns(2)
            with c1:
                if st.button("✏️ 수정", key=f"edit_button_{b.id}"):
                    st.session_state["edit_mode"] = True
                    st.session_state["edit_id"] = b.id
                    st.rerun()
            with c2:
                if st.button("❌ 삭제", key=f"delete_button_{b.id}"):
                    delete_book(b.id)
                    st.success("도서를 삭제했습니다.")
                    st.rerun()

            if st.session_state.get("edit_mode") and st.session_state.get("edit_id") == b.id:
                with st.form(f"edit_form_{b.id}"):
                    col1, col2 = st.columns(2)
                    with col1:
                        title_e = st.text_input("도서명(수정)", b.title)
                        format_e = st.text_input("판형(수정)", b.format or "")
                        cover_paper_e = st.text_input("표지 용지(수정)", b.cover_paper or "")
                        cover_color_e = st.text_input("표지 도수/양단면(수정)", b.cover_color or "")
                    with col2:
                        total_pages_e = st.number_input("총 페이지 수(수정)", min_value=0, step=1, value=int(b.total_pages or 0))
                        endpaper_e = st.selectbox("면지 여부(수정)", ["없음","있음"], index=(0 if (b.endpaper or "없음")=="없음" else 1), key=f"endpaper_{b.id}")
                        wing_e = st.selectbox("날개 여부(수정)", ["없음","있음"], index=(0 if (b.wing or "없음")=="없음" else 1), key=f"wing_{b.id}")
                        binding_e = st.text_input("제본 방식(수정)", b.binding or "")
                    inner_spec_e = st.text_area("내지 사양(수정)", b.inner_spec or "", key=f"inner_{b.id}")

                    ec1, ec2 = st.columns(2)
                    with ec1:
                        if st.form_submit_button("💾 저장"):
                            update_book(b.id, {
                                "title": title_e.strip(),
                                "format": format_e.strip(),
                                "cover_paper": cover_paper_e.strip(),
                                "cover_color": cover_color_e.strip(),
                                "inner_spec": inner_spec_e.strip(),
                                "total_pages": int(total_pages_e),
                                "endpaper": endpaper_e,
                                "wing": wing_e,
                                "binding": binding_e.strip(),
                            })
                            st.success("수정되었습니다.")
                            st.session_state["edit_mode"] = False
                            st.session_state["edit_id"] = None
                            st.rerun()
                    with ec2:
                        if st.form_submit_button("취소"):
                            st.session_state["edit_mode"] = False
                            st.session_state["edit_id"] = None
                            st.rerun()

# =========================================================
# 사이드바 네비게이션 / 라우팅
# =========================================================
with st.sidebar:
    st.markdown("## 메뉴")
    page = st.radio(
        "페이지 선택",
        ["🔍 발주 조회", "📦 발주 입력", "📘 도서 사양 등록"],
        index=0,
        key="sidebar_nav",
    )
    st.markdown("---")
    st.caption("옵셋 도서 제작 관리 · v2 (Supabase/SQLite)")

if page == "🔍 발주 조회":
    render_order_query_page()
elif page == "📦 발주 입력":
    render_order_input_page()
else:
    render_book_spec_page()
