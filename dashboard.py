import io
import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(
    page_title="수입단가 현황 대시보드",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("📦 수입단가 현황 대시보드")
st.caption("입고현황 시트에 Raw Data를 붙여넣은 후 파일을 업로드하면 모든 차트가 자동으로 갱신됩니다.")

# ─── 사이드바 ──────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ 설정")
    uploaded = st.file_uploader(
        "수입단가현황 Excel 파일",
        type=["xlsx", "xls"],
        help="'입고현황' 시트에 Raw Data가 있는 파일을 업로드하세요.",
    )
    st.divider()
    threshold = st.slider(
        "단가 이상 감지 기준 (%)",
        min_value=1, max_value=50, value=10, step=1,
        help="전 입고월 대비 단가 변동률이 이 기준을 초과하면 이상으로 표시합니다.",
    )
    st.divider()
    st.caption("💡 음수 수량(반품)은 자동으로 제외됩니다.")

if not uploaded:
    st.info("👈 왼쪽 사이드바에서 Excel 파일을 업로드해주세요.")
    st.stop()


# ─── 데이터 로드 ───────────────────────────────────────────────────
@st.cache_data(show_spinner="데이터 로딩 중...")
def load_data(file_bytes: bytes) -> pd.DataFrame:
    df = pd.read_excel(
        io.BytesIO(file_bytes),
        sheet_name="입고현황",
        usecols="A:N",
        header=0,
        engine="openpyxl",
    )
    df.columns = [
        "입고일자", "입고번호", "거래처", "거래구분", "환종", "담당자",
        "No", "품번", "품명", "규격", "단위", "입고수량", "외화단가", "외화금액",
    ]
    df = df.dropna(subset=["입고일자", "품명"])
    df["입고일자"] = pd.to_datetime(df["입고일자"], errors="coerce")
    df = df.dropna(subset=["입고일자"])
    df["연월"] = df["입고일자"].dt.to_period("M").astype(str)

    # 단위 정규화: G/g → G, EA/ea → EA, 나머지 그대로
    def norm_unit(u):
        if pd.isna(u):
            return "기타"
        u = str(u).strip()
        if u.upper() == "G":
            return "G"
        if u.upper() == "EA":
            return "EA"
        return u.upper()
    df["단위_정규"] = df["단위"].apply(norm_unit)

    # 품목군: 품명 마지막 괄호 안 텍스트
    df["품목군"] = (
        df["품명"]
        .str.extract(r"\(([^)]+)\)(?:\s*_\w+)?\s*$")
        .iloc[:, 0]
        .str.upper()
        .str.strip()
        .fillna("기타")
    )

    # 국가
    df["국가"] = df["환종"].map({
        "JPY": "일본",
        "GBP": "영국",
        "USD": "USD",
        "CAD": "CAD",
    }).fillna(df["환종"])

    # 음수 수량(반품) 제외
    df = df[pd.to_numeric(df["입고수량"], errors="coerce") > 0].copy()
    df["외화단가"] = pd.to_numeric(df["외화단가"], errors="coerce")
    df["외화금액"] = pd.to_numeric(df["외화금액"], errors="coerce")
    df["입고수량"] = pd.to_numeric(df["입고수량"], errors="coerce")
    df = df.dropna(subset=["외화단가", "입고수량"])
    return df


df = load_data(uploaded.read())
all_months = sorted(df["연월"].unique())

# ─── 공통 필터 헬퍼 ────────────────────────────────────────────────
def unit_filter(key: str) -> list:
    units = sorted(df["단위_정규"].unique())
    return st.multiselect("단위 필터", units, default=units, key=key)

def country_filter(key: str) -> list:
    countries = sorted(df["국가"].unique())
    return st.multiselect("국가(환종)", countries, default=countries, key=key)

# ─── KPI ───────────────────────────────────────────────────────────
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("기간", f"{all_months[0]} ~ {all_months[-1]}")
c2.metric("총 입고 건수", f"{len(df):,}건")
c3.metric("품목 수", f"{df['품명'].nunique():,}개")
c4.metric("품목군 수", f"{df['품목군'].nunique()}개")
c5.metric("공급처 수", f"{df['거래처'].nunique()}개")
st.divider()

# ─── 탭 ────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 품목군별 월별 현황",
    "📦 품목별 입고수량",
    "⚠️ 단가 이상 감지",
    "💱 국가별 추이",
    "🔍 신규 / 중단 품목",
])

COLOR_MAP = {"일본": "#4E79A7", "영국": "#E15759", "USD": "#59A14F", "CAD": "#F28E2B"}


# ══════════════════════════════════════════════════
# TAB 1: 품목군별 월별 현황
# ══════════════════════════════════════════════════
with tab1:
    st.subheader("품목군별 월별 수입 현황")

    c1, c2, c3 = st.columns([2, 2, 1])
    with c1:
        sel_units1 = unit_filter("t1_unit")
    with c2:
        sel_countries1 = country_filter("t1_country")
    with c3:
        top_n = st.slider("상위 품목군 수", 5, 20, 10, key="t1_topn")

    df1 = df[df["단위_정규"].isin(sel_units1) & df["국가"].isin(sel_countries1)]
    unit_label1 = "수량/중량"

    top_groups = df1.groupby("품목군")["입고수량"].sum().nlargest(top_n).index.tolist()
    monthly_g = (
        df1[df1["품목군"].isin(top_groups)]
        .groupby(["연월", "품목군"])["입고수량"]
        .sum()
        .reset_index()
    )

    fig1 = px.bar(
        monthly_g, x="연월", y="입고수량", color="품목군",
        title=f"품목군별 월별 입고수량 (상위 {top_n}개)",
        labels={"연월": "", "입고수량": unit_label1},
    )
    fig1.update_layout(height=430, xaxis_tickangle=-45, legend_title="품목군")
    st.plotly_chart(fig1, use_container_width=True)

    # 연도 소계 테이블
    st.caption("📋 품목군별 연도 소계")
    df1c = df1.copy()
    df1c["연도"] = df1c["입고일자"].dt.year
    tbl = (
        df1c[df1c["품목군"].isin(top_groups)]
        .groupby(["품목군", "연도"])["입고수량"]
        .sum()
        .unstack(fill_value=0)
        .reset_index()
    )
    tbl.columns.name = None
    tbl["합계"] = tbl.iloc[:, 1:].sum(axis=1)
    tbl = tbl.sort_values("합계", ascending=False)
    st.dataframe(tbl, use_container_width=True, height=280)


# ══════════════════════════════════════════════════
# TAB 2: 품목별 입고수량
# ══════════════════════════════════════════════════
with tab2:
    st.subheader("품목별 입고수량 상세")

    c1, c2, c3, c4 = st.columns([2, 2, 2, 1])
    with c1:
        sel_units2 = unit_filter("t2_unit")
    with c2:
        sel_countries2 = country_filter("t2_country")
    with c3:
        groups_all = sorted(df["품목군"].unique())
        sel_group2 = st.selectbox("품목군 선택", ["(전체)"] + groups_all, key="t2_group")
    with c4:
        chart_type = st.radio("차트", ["선", "막대"], key="t2_chart")

    df2 = df[df["단위_정규"].isin(sel_units2) & df["국가"].isin(sel_countries2)]
    if sel_group2 != "(전체)":
        df2 = df2[df2["품목군"] == sel_group2]

    if df2.empty:
        st.warning("선택한 조건에 해당하는 데이터가 없습니다.")
    else:
        top15 = df2.groupby("품명")["입고수량"].sum().nlargest(15).index.tolist()
        item_chart = (
            df2[df2["품명"].isin(top15)]
            .groupby(["품명", "연월"])["입고수량"]
            .sum()
            .reset_index()
        )
        title2 = sel_group2 if sel_group2 != "(전체)" else "전체"
        if chart_type == "선":
            fig2 = px.line(item_chart, x="연월", y="입고수량", color="품명",
                           title=f"[{title2}] 품목별 월별 입고수량 (상위 15개)", markers=True)
        else:
            fig2 = px.bar(item_chart, x="연월", y="입고수량", color="품명",
                          title=f"[{title2}] 품목별 월별 입고수량 (상위 15개)", barmode="stack")
        fig2.update_layout(height=430, xaxis_tickangle=-45, legend_title="품명")
        st.plotly_chart(fig2, use_container_width=True)

        st.caption("📋 전체 피벗 테이블")
        pivot = (
            df2.groupby(["품명", "단위_정규", "연월"])["입고수량"]
            .sum()
            .unstack(fill_value=0)
            .reset_index()
        )
        pivot.columns.name = None
        pivot["합계"] = pivot.select_dtypes("number").sum(axis=1)
        pivot = pivot.sort_values("합계", ascending=False)
        st.dataframe(pivot, use_container_width=True, height=380)


# ══════════════════════════════════════════════════
# TAB 3: 단가 이상 감지
# ══════════════════════════════════════════════════
with tab3:
    st.subheader(f"⚠️ 수입단가 이상 변동 감지 (기준: ±{threshold}%)")

    c1, c2, c3 = st.columns(3)
    with c1:
        sel_units3 = unit_filter("t3_unit")
    with c2:
        sel_countries3 = country_filter("t3_country")
    with c3:
        sel_groups3 = st.multiselect(
            "품목군 필터 (미선택=전체)", sorted(df["품목군"].unique()), key="t3_group"
        )

    df3 = df[df["단위_정규"].isin(sel_units3) & df["국가"].isin(sel_countries3)]
    if sel_groups3:
        df3 = df3[df3["품목군"].isin(sel_groups3)]

    price_m = (
        df3.groupby(["품명", "환종", "단위_정규", "연월"])["외화단가"]
        .mean()
        .reset_index()
        .sort_values(["품명", "연월"])
    )
    price_m["이전단가"] = price_m.groupby(["품명", "환종"])["외화단가"].shift(1)
    price_m["변동률(%)"] = (
        (price_m["외화단가"] - price_m["이전단가"]) / price_m["이전단가"] * 100
    ).round(2)

    anomalies = (
        price_m[
            (price_m["변동률(%)"].abs() > threshold) &
            (price_m["이전단가"] > 0)  # 이전단가 0 건 제외 (데이터 이슈)
        ]
        .dropna(subset=["변동률(%)"])
        .sort_values("변동률(%)", key=abs, ascending=False)
    )

    if anomalies.empty:
        st.success(f"✅ 기준 ±{threshold}% 이상 변동한 품목이 없습니다.")
    else:
        m1, m2, m3 = st.columns(3)
        m1.metric("이상 감지 건수", f"{len(anomalies)}건")
        m2.metric("↑ 단가 상승", f"{(anomalies['변동률(%)'] > 0).sum()}건")
        m3.metric("↓ 단가 하락", f"{(anomalies['변동률(%)'] < 0).sum()}건")

        def color_변동률(val):
            if pd.isna(val):
                return ""
            return "color: #E15759; font-weight:bold" if val > 0 else "color: #4E79A7; font-weight:bold"

        disp = anomalies[["품명", "환종", "단위_정규", "연월", "이전단가", "외화단가", "변동률(%)"]].copy()
        disp.columns = ["품명", "환종", "단위", "연월", "이전단가", "현재단가", "변동률(%)"]
        st.dataframe(
            disp.style.applymap(color_변동률, subset=["변동률(%)"]),
            use_container_width=True,
            height=380,
        )

        # 이상 상위 5개 품목 단가 추이
        st.divider()
        top5 = anomalies["품명"].value_counts().head(5).index.tolist()
        if top5:
            fig3 = px.line(
                price_m[price_m["품명"].isin(top5)],
                x="연월", y="외화단가", color="품명",
                title="이상 변동 상위 5개 품목 단가 추이",
                markers=True,
                facet_col="환종",
            )
            fig3.update_layout(height=370, xaxis_tickangle=-45)
            st.plotly_chart(fig3, use_container_width=True)


# ══════════════════════════════════════════════════
# TAB 4: 국가별 추이
# ══════════════════════════════════════════════════
with tab4:
    st.subheader("💱 국가(환종)별 수입 추이")

    c1, c2 = st.columns(2)
    with c1:
        sel_units4 = unit_filter("t4_unit")
    with c2:
        sel_countries4 = country_filter("t4_country")

    df4 = df[df["단위_정규"].isin(sel_units4) & df["국가"].isin(sel_countries4)]

    monthly_c = (
        df4.groupby(["연월", "국가"])
        .agg(수량=("입고수량", "sum"), 금액=("외화금액", "sum"))
        .reset_index()
    )

    c1, c2 = st.columns(2)
    with c1:
        fig4a = px.bar(
            monthly_c, x="연월", y="수량", color="국가",
            color_discrete_map=COLOR_MAP,
            title="월별 입고수량 비교",
            barmode="group",
            labels={"연월": "", "수량": "입고수량"},
        )
        fig4a.update_layout(height=350, xaxis_tickangle=-45)
        st.plotly_chart(fig4a, use_container_width=True)
    with c2:
        fig4b = px.bar(
            monthly_c, x="연월", y="금액", color="국가",
            color_discrete_map=COLOR_MAP,
            title="월별 외화금액 비교",
            barmode="group",
            labels={"연월": "", "금액": "외화금액"},
        )
        fig4b.update_layout(height=350, xaxis_tickangle=-45)
        st.plotly_chart(fig4b, use_container_width=True)

    # YoY
    st.caption("📋 전년 동월 대비 수량 변화 (%)")
    for country in sel_countries4:
        cdf = monthly_c[monthly_c["국가"] == country].copy()
        cdf["전년동월"] = cdf["수량"].shift(12)
        cdf["YoY(%)"] = ((cdf["수량"] - cdf["전년동월"]) / cdf["전년동월"] * 100).round(1)
        has_yoy = cdf.dropna(subset=["YoY(%)"])
        if not has_yoy.empty:
            fig_yoy = px.bar(
                has_yoy, x="연월", y="YoY(%)",
                title=f"{country} 입고수량 YoY (%)",
                color_discrete_sequence=[COLOR_MAP.get(country, "#888")],
                labels={"연월": ""},
            )
            fig_yoy.add_hline(y=0, line_dash="dash", line_color="gray")
            fig_yoy.update_layout(height=250, xaxis_tickangle=-45)
            st.plotly_chart(fig_yoy, use_container_width=True)


# ══════════════════════════════════════════════════
# TAB 5: 신규 / 중단 품목
# ══════════════════════════════════════════════════
with tab5:
    st.subheader("🔍 신규 / 중단 품목 현황")

    c1, c2 = st.columns(2)
    with c1:
        sel_units5 = unit_filter("t5_unit")
    with c2:
        sel_countries5 = country_filter("t5_country")

    df5 = df[df["단위_정규"].isin(sel_units5) & df["국가"].isin(sel_countries5)]
    all_months5 = sorted(df5["연월"].unique())

    if len(all_months5) < 2:
        st.warning("데이터가 부족합니다.")
        st.stop()

    item_summary = (
        df5.groupby(["품명", "품목군", "국가", "단위_정규"])["연월"]
        .agg(첫입고월="min", 마지막입고월="max")
        .reset_index()
    )

    recent_cutoff = all_months5[-3] if len(all_months5) >= 3 else all_months5[0]
    disc_cutoff = all_months5[-4] if len(all_months5) >= 4 else all_months5[0]

    new_items = item_summary[item_summary["첫입고월"] >= recent_cutoff].sort_values("첫입고월", ascending=False)
    discontinued = item_summary[item_summary["마지막입고월"] <= disc_cutoff].sort_values("마지막입고월", ascending=False)

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("#### 🆕 신규 품목 (최근 3개월 내 첫 입고)")
        st.metric("신규 품목 수", f"{len(new_items)}개")
        if not new_items.empty:
            st.dataframe(new_items.reset_index(drop=True), use_container_width=True, height=400)
        else:
            st.info("신규 품목이 없습니다.")

    with c2:
        st.markdown("#### 🚫 중단 의심 품목 (4개월 이상 미입고)")
        st.metric("중단 의심 품목 수", f"{len(discontinued)}개")
        if not discontinued.empty:
            st.dataframe(discontinued.reset_index(drop=True), use_container_width=True, height=400)
        else:
            st.info("중단 의심 품목이 없습니다.")
