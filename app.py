# -*- coding: utf-8 -*-
import os
from datetime import date

import streamlit as st
import pandas as pd

# 🔐 접근 제한 (세션 유지 + 시크릿 지원)
APP_PASSWORD = st.secrets.get("APP_PASSWORD", "qnzmzm1101!")

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

def login_form():
    st.title("🔒 접근 제한")
    pw = st.text_input("비밀번호를 입력하세요", type="password", key="pw_input")
    if st.button("접속", key="login_btn"):
        # 공백/개행, None 방지
        typed = (pw or "").strip()
        expect = str(APP_PASSWORD).strip()
        if typed == expect:
            st.session_state.authenticated = True
            st.success("✅ 인증되었습니다.")
            st.rerun()
        else:
            st.error("❌ 비밀번호가 올바르지 않습니다.")

# 비로그인 상태면 아래 코드 실행 중단
if not st.session_state.authenticated:
    login_form()
    st.stop()


# (선택) 로그아웃 버튼
with st.sidebar:
    if st.button("로그아웃"):
        st.session_state.authenticated = False
        st.rerun()


from sqlalchemy import create_engine, Column, Integer, String, Text
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy import text


# ---------------------------
# 페이지 설정
# ---------------------------
st.set_page_config(
    page_title="📚 옵셋 도서 제작 관리",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------
# DB 연결/모델
# ---------------------------
from sqlalchemy import create_engine, text
from urllib.parse import quote_plus
import streamlit as st

# Supabase 연결 함수
def build_engine_from_secrets():
    host = st.secrets["DB_HOST"].strip()
    port = str(st.secrets.get("DB_PORT", "6543")).strip()  # Session pooler 포트
    user = st.secrets.get("DB_USER", "postgres").strip()
    pwd  = quote_plus(str(st.secrets["DB_PASS"]))  # 특수문자 안전하게 처리
    name = st.secrets.get("DB_NAME", "postgres").strip()

    # PostgreSQL 접속 URL (SSL 적용)
    url  = f"postgresql+psycopg://{user}:{pwd}@{host}:{port}/{name}?sslmode=require"
    return create_engine(url, echo=False, pool_pre_ping=True)

engine = build_engine_from_secrets()

# DB 연결 테스트 (처음 배포 시 에러 확인용)
try:
    with engine.connect() as conn:
        conn.execute(text("select 1"))
except Exception as e:
    st.error("❌ DB 연결 실패: Secrets/호스트/포트/비번/sslmode를 확인하세요.")
    st.exception(e)
    st.stop()

# 도서(사양)
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

# 발주(주문)
class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    book_id = Column(Integer, nullable=False)
    qty = Column(Integer, nullable=False)
    date = Column(String, nullable=False)  # YYYY-MM-DD
    vendor = Column(String)                # 제작처
    unit_price = Column(Integer)           # 권당 가격(부가세 제외)
    invoice_issued = Column(Integer)       # 0/1
    total_override = Column(Integer)  # ✅ 총액 수동 입력(없으면 NULL/0)
    memo = Column(Text)               # ✅ 메모

    # 합계(공급가/부가세/총액)
    supply_price = Column(Integer)  # VAT 제외
    vat_price = Column(Integer)     # 10%
    total_price = Column(Integer)   # VAT 포함

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

Base.metadata.create_all(bind=engine)

# ✅ 여기에 아래 코드 한 번에 붙여넣기
from sqlalchemy import text

def _ensure_orders_override_and_memo():
    with engine.connect() as conn:
        cols = [r[1] for r in conn.execute(text("PRAGMA table_info(orders)")).fetchall()]
        if "total_override" not in cols:
            conn.execute(text("ALTER TABLE orders ADD COLUMN total_override INTEGER"))
        if "memo" not in cols:
            conn.execute(text("ALTER TABLE orders ADD COLUMN memo TEXT"))
        conn.commit()

_ensure_orders_override_and_memo()

# --- one-off migrations: 컬럼 없으면 추가 ---
def _pragma_cols(conn):
    return [r[1] for r in conn.execute(text("PRAGMA table_info(orders)")).fetchall()]

def _ensure_orders_vendor_column():
    with engine.connect() as conn:
        cols = _pragma_cols(conn)
        if "vendor" not in cols:
            conn.execute(text("ALTER TABLE orders ADD COLUMN vendor TEXT"))
            conn.commit()

def _ensure_orders_unit_price_column():
    with engine.connect() as conn:
        cols = _pragma_cols(conn)
        if "unit_price" not in cols:
            conn.execute(text("ALTER TABLE orders ADD COLUMN unit_price INTEGER"))
            conn.commit()

def _ensure_orders_invoice_column():
    with engine.connect() as conn:
        cols = _pragma_cols(conn)
        if "invoice_issued" not in cols:
            conn.execute(text("ALTER TABLE orders ADD COLUMN invoice_issued INTEGER DEFAULT 0"))
            conn.commit()

_ensure_orders_vendor_column()
_ensure_orders_unit_price_column()
_ensure_orders_invoice_column()

# ---------------------------
# 공용 함수
# ---------------------------
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
def get_effective_total(order: Order) -> int:
    """표시용 총액: 수동입력 값이 있으면 그 값을 우선."""
    ov = getattr(order, "total_override", 0) or 0
    return int(ov) if ov > 0 else int(order.total_price or 0)

def set_order_override_and_memo(order_id: int, override_value: int | None, memo_text: str | None):
    s = get_session()
    try:
        o = s.query(Order).filter(Order.id == order_id).first()
        if o:
            # 0 또는 빈 값이면 수동입력 해제
            o.total_override = int(override_value) if (override_value not in [None, "", 0]) else None
            o.memo = (memo_text or "").strip()
            s.commit()
    finally:
        s.close()


# ---------------------------
# Book CRUD
# ---------------------------
def add_book(book: dict):
    s = get_session()
    try:
        b = Book(**book)
        s.add(b)
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

# ---------------------------
# Order CRUD
# ---------------------------
def add_order(order_data: dict):
    """권당 가격(unit_price)이 주어지면 그것을 우선으로 계산.
       없으면 상세 비용 합산(calc_supply_and_vat) 사용."""
    s = get_session()
    try:
        qty = _to_int(order_data["qty"])
        unit_price = _to_int(order_data.get("unit_price", 0))

        if unit_price > 0:
            supply = qty * unit_price
            vat = int(round(supply * 0.10))
            total = supply + vat
        else:
            supply, vat, total = calc_supply_and_vat(order_data)

        o = Order(
            book_id=order_data["book_id"],
            qty=qty,
            date=order_data["date"],
            vendor=order_data.get("vendor", ""),
            unit_price=unit_price,
            invoice_issued=_to_int(order_data.get("invoice_issued", 0)),
            supply_price=supply, vat_price=vat, total_price=total,
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

def set_invoice_status(order_id: int, issued: bool):
    s = get_session()
    try:
        o = s.query(Order).filter(Order.id == order_id).first()
        if o:
            o.invoice_issued = 1 if issued else 0
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

# =========================================================
# 페이지 1) 🔍 발주 조회
# =========================================================
def render_order_query_page():
    st.header("🔍 발주 조회")

    # 0) 상태 초기화
    if "confirm_delete_order" not in st.session_state:
        st.session_state["confirm_delete_order"] = None

    # 1) 도서명 검색 + 도서 선택
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

    # 2) 부수(정확히 일치) 필터
    qty_filter_text = st.text_input("부수 검색 (숫자만 입력)", key="query_qty_filter")
    orders = get_orders(
        selected_book.id,
        int(qty_filter_text) if qty_filter_text.isdigit() else None
    )

    if not orders:
        st.info("발주 내역이 없습니다.")
        return

    # 3) 요약 표 (편집 가능, '계산서 발행' 체크박스)
    df_orig = pd.DataFrame([{
        "id": o.id,
        "발주일": o.date,
        "제작처": o.vendor or "",
        "부수": o.qty,
        "권당 가격": getattr(o, "unit_price", None) or "",  # 있으면 표시, 없으면 공란
        "공급가(VAT 제외)": o.supply_price,
        "부가세": o.vat_price,
        "총액(계산)": o.total_price,                   # 자동계산 원본
        "총액 수동입력": o.total_override or 0,        # ✅ 사용자가 직접 입력
        "표시 총액(수동값 우선)": get_effective_total(o), # ✅ 읽기 전용
        "메모": getattr(o, "memo", "") or "",           # ✅ 메모
    "계산서 발행": bool(getattr(o, "invoice_issued", 0))
    } for o in orders])

    edited = st.data_editor(
        df_orig,
        use_container_width=True,
        hide_index=True,
        column_order=[
        "발주일","제작처","부수","권당 가격",
        "공급가(VAT 제외)","부가세","총액(계산)",
        "총액 수동입력","표시 총액(수동값 우선)","메모","계산서 발행","id"
        ],
        column_config={
        "총액 수동입력": st.column_config.NumberColumn("총액 수동입력", help="입력하면 표시 총액이 이 값으로 대체됩니다.", step=1000, min_value=0),
        "표시 총액(수동값 우선)": st.column_config.NumberColumn("표시 총액(수동값 우선)", disabled=True, help="수동입력이 있으면 그 값, 없으면 자동계산 값"),
        "메모": st.column_config.TextColumn("메모", width="large"),
        "계산서 발행": st.column_config.CheckboxColumn("계산서 발행", help="발행 시 체크"),
        "id": st.column_config.Column("id", disabled=True),
        },
        key="order_invoice_editor"
    )

    # 변경 저장 버튼 (체크박스 변경만 반영)
    if st.button("변경 저장", key="order_invoice_save"):
    # 원본/수정본 인덱싱
        orig = df_orig.set_index("id")
        new = edited.set_index("id")

    changed_count = 0

    # 4-1) 계산서 발행 변경 사항 (기존 로직 그대로)
    if "계산서 발행" in new.columns and "계산서 발행" in orig.columns:
        for oid in new.index:
            old_val = bool(orig.at[oid, "계산서 발행"])
            new_val = bool(new.at[oid, "계산서 발행"])
            if old_val != new_val:
                # ⚠️ 기존에 쓰던 함수명이 있다면 그대로 호출 (예: set_invoice_status)
                try:
                    set_invoice_status(int(oid), new_val)
                    changed_count += 1
                except NameError:
                    # 함수가 없다면 무시하거나, 필요 시 구현하세요.
                    pass

    # 4-2) 총액 수동입력 & 메모 변경 사항
    for oid in new.index:
        old_override = int(orig.at[oid, "총액 수동입력"]) if "총액 수동입력" in orig.columns else 0
        new_override = int(new.at[oid, "총액 수동입력"]) if "총액 수동입력" in new.columns and str(new.at[oid, "총액 수동입력"]).isdigit() else 0

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

    # 4) 각 주문 상세 + 발주 취소
    for o in orders:
        eff_total = get_effective_total(o)
        header = f"📄 {o.date} · {o.qty}부 · 표시 총액 {eff_total:,}원"
        with st.expander(header, expanded=False):
            st.markdown(
                f"**공급가:** {(o.supply_price or 0):,}원 · "
                f"**부가세:** {(o.vat_price or 0):,}원 · "
                f"**총액(계산):** {(o.total_price or 0):,}원"
            )
        if (o.total_override or 0) > 0:
            st.info(f"총액 수동입력 적용: {(o.total_override or 0):,}원 (표시 총액은 이 값으로 대체됩니다)")
        if getattr(o, "memo", ""):
            st.write(f"📝 메모: {o.memo}")
            st.write(f"• 제작처: {o.vendor or '—'}")
            st.write(f"• 계산서 발행: {'✅ 발행됨' if getattr(o, 'invoice_issued', 0) else '❌ 미발행'}")

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
        # --- 상단 구조: 1) 발주일 2) 제작 부수 3) 권당 가격 ---
        r1c1, r1c2, r1c3 = st.columns([1,1,1])
        with r1c1:
            order_date = st.date_input("발주일", value=date.today(), key="order_date")
        with r1c2:
            qty = st.number_input("제작 부수", min_value=1, step=100, value=1000, key="order_qty")
        with r1c3:
            unit_price = st.number_input("권당 가격", min_value=0, step=100, value=0, key="unit_price")

        # --- 4) 총 합계(부가세 제외) 5) VAT 합산 가격(부가세 포함) 6) 제작처 ---
        subtotal = int(qty) * int(unit_price)
        total_with_vat = subtotal + int(round(subtotal * 0.10))

        r2c1, r2c2, r2c3 = st.columns([1,1,1])
        with r2c1:
            st.number_input("총 합계 (VAT 제외)", value=subtotal, step=0, format="%d", disabled=True, key="subtotal_preview")
        with r2c2:
            st.number_input("VAT 합산 가격 (VAT 포함)", value=total_with_vat, step=0, format="%d", disabled=True, key="vat_included_preview")
        with r2c3:
            vendor = st.text_input("제작처", "", key="vendor_name")
            st.caption("권당 가격을 입력하면 합계가 자동 계산됩니다.")

        # --- 상세 비용 섹션(선택 입력) ---
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
            l1,l2,e1,e2,p1,p2,f1,f2 = st.columns(8)
            with l1: laminating_unit = st.number_input("라미 단가", min_value=0, step=1, value=0)
            with l2: laminating_cost = st.number_input("라미 비용", min_value=0, step=1000, value=0)
            with e1: epoxy_unit = st.number_input("에폭시 단가", min_value=0, step=1, value=0)
            with e2: epoxy_cost = st.number_input("에폭시 비용", min_value=0, step=1000, value=0)
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

        # 저장
        if st.form_submit_button("📝 발주 저장"):
            payload = {
                "book_id": book_choice.id, "qty": qty, "date": str(order_date),
                "vendor": vendor, "unit_price": unit_price,
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
# 사이드бар 네비게이션 / 라우팅
# =========================================================
with st.sidebar:
    st.markdown("## 메뉴")
    page = st.radio(
        "페이지 선택",
        ["🔍 발주 조회", "📦 발주 입력", "📘 도서 사양 등록"],
        index=1,  # 새 구조 확인 편의상 기본을 발주 입력으로
        key="sidebar_nav",
    )
    st.markdown("---")
    st.caption("옵셋 도서 제작 관리 · v2 (unit price)")

if page == "🔍 발주 조회":
    render_order_query_page()
elif page == "📦 발주 입력":
    render_order_input_page()
else:
    render_book_spec_page()
