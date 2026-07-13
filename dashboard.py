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

# ── 사이드바: 전역 필터 ────────────────────────────────────────
with st.sidebar:
    st.header("📦 수입단가 대시보드")
    uploaded = st.file_uploader(
        "Excel 파일 업로드",
        type=["xlsx", "xls"],
        help="'입고현황' 시트가 포함된 파일을 올려주세요.",
    )
    if uploaded:
        st.divider()
        st.markdown("**전역 필터**")
        global_unit = st.radio(
            "단위 선택",
            ["EA (완제품)", "G (원자재)"],
            index=0,
            help="EA와 G는 단위가 달라 같은 차트에 표시할 수 없습니다.",
        )
        global_country = st.multiselect(
            "국가",
            ["일본", "영국"],
            default=["일본", "영국"],
        )
        st.divider()
        threshold = st.slider("단가 이상 감지 기준 (%)", 1, 50, 10)

if not uploaded:
    st.title("📦 수입단가 현황 대시보드")
    st.info("👈 왼쪽 사이드바에서 Excel 파일을 업로드하면 대시보드가 생성됩니다.")
    st.stop()


# ── 데이터 로드 ─────────────────────────────────────────────────
@st.cache_data(show_spinner="데이터 불러오는 중...")
def load_data(file_bytes: bytes) -> pd.DataFrame:
    df = pd.read_excel(
        io.BytesIO(file_bytes),
        sheet_name="입고현황",
        usecols="A:O",
        header=0,
        engine="openpyxl",
    )
    df.columns = [
        "입고일자", "입고번호", "거래처", "거래구분", "환종", "담당자",
        "No", "품번", "품명", "규격", "단위", "입고수량", "외화단가", "외화금액",
        "해당월",
    ]
    df = df.dropna(subset=["해당월", "품명"])
    # 해당월 형식 통일: 2026-04 / 2026/04 → 2026/04
    df["연월"] = (
        df["해당월"].astype(str).str.strip()
        .str[:7]
        .str.replace("-", "/", regex=False)
    )
    df["단위_정규"] = df["단위"].apply(
        lambda u: "G" if pd.notna(u) and str(u).strip().upper() == "G"
        else ("EA" if pd.notna(u) and str(u).strip().upper() == "EA" else "기타")
    )
    df["품목군"] = (
        df["품명"].str.extract(r"\(([^)]+)\)(?:\s*_\w+)?\s*$")
        .iloc[:, 0].str.upper().str.strip().fillna("기타")
    )
    df["국가"] = df["환종"].map({"JPY": "일본", "GBP": "영국"}).fillna("기타")
    df = df[pd.to_numeric(df["입고수량"], errors="coerce") > 0].copy()
    for col in ["외화단가", "외화금액", "입고수량"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["외화단가", "입고수량"])
    return df


df_raw = load_data(uploaded.read())

# 전역 필터 적용
sel_unit = "EA" if "EA" in global_unit else "G"
df = df_raw[
    (df_raw["단위_정규"] == sel_unit) &
    (df_raw["국가"].isin(global_country))
].copy()

all_months = sorted(df_raw["연월"].unique())

# ── 숫자 포맷 헬퍼 ─────────────────────────────────────────────
def fmt_num(x, decimal=0):
    """천단위 콤마, 소수점 지정"""
    if pd.isna(x):
        return "-"
    return f"{x:,.{decimal}f}"

def fmt_df(df_in, int_cols=None, dec1_cols=None):
    """DataFrame 컬럼별 포맷 적용"""
    fmt = {}
    if int_cols:
        for c in int_cols:
            if c in df_in.columns:
                fmt[c] = lambda v: fmt_num(v, 0)
    if dec1_cols:
        for c in dec1_cols:
            if c in df_in.columns:
                fmt[c] = lambda v: fmt_num(v, 1)
    if not fmt:
        return df_in
    return df_in.style.format(fmt, na_rep="-")

# ── 차트 공통 설정 ─────────────────────────────────────────────
UNIT_LABEL = "수량 (EA)" if sel_unit == "EA" else "중량 (G)"
PRICE_LABEL = "단가 (JPY)" if sel_unit == "EA" else "단가 (GBP/KG 환산)"
COLOR_MAP = {"일본": "#4E79A7", "영국": "#E15759"}

# ── KPI ────────────────────────────────────────────────────────
st.title("📦 수입단가 현황 대시보드")
st.caption(f"단위: **{sel_unit}** | 국가: **{', '.join(global_country)}** | 기간: **{all_months[0]} ~ {all_months[-1]}**")

if df.empty:
    st.warning("선택한 필터 조건에 해당하는 데이터가 없습니다. 사이드바 필터를 확인해주세요.")
    st.stop()

k1, k2, k3, k4 = st.columns(4)
k1.metric("기간", f"{all_months[0]} ~ {all_months[-1]}")
k2.metric("총 입고 건수", f"{len(df):,}건")
k3.metric("품목 수", f"{df['품명'].nunique():,}개")
k4.metric("품목군 수", f"{df['품목군'].nunique()}개")
st.divider()

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 품목군별 월별 현황",
    "📦 품목별 입고수량",
    "⚠️ 단가 이상 감지",
    "💱 국가별 추이",
    "🔍 신규 / 중단 품목",
])


# ════════════════════════════════════════════════
# TAB 1: 품목군별 월별 현황
# ════════════════════════════════════════════════
with tab1:
    st.subheader(f"품목군별 월별 {UNIT_LABEL} 추이")

    col1, col2 = st.columns([3, 1])
    with col2:
        top_n = st.slider("상위 품목군 수", 3, 30, 20, key="n1")
        metric1 = st.radio("기준", ["수량", "금액"], key="m1")

    val_col = "입고수량" if metric1 == "수량" else "외화금액"
    top_g = df.groupby("품목군")[val_col].sum().nlargest(top_n).index.tolist()
    monthly = (
        df[df["품목군"].isin(top_g)]
        .groupby(["연월", "품목군"])[val_col]
        .sum().reset_index()
    )

    with col1:
        fig1 = px.line(
            monthly, x="연월", y=val_col, color="품목군",
            markers=True,
            labels={"연월": "", val_col: UNIT_LABEL if metric1 == "수량" else "외화금액"},
        )
        fig1.update_layout(
            height=400,
            xaxis_tickangle=-45,
            yaxis_tickformat=",",
            legend=dict(orientation="v", x=1.01, y=1),
            margin=dict(r=150),
        )
        fig1.update_traces(line=dict(width=2))
        st.plotly_chart(fig1, use_container_width=True)

    # 연도 소계 테이블
    df1y = df.copy()
    df1y["연도"] = df1y["연월"].str[:4].astype(int)
    tbl1 = (
        df1y[df1y["품목군"].isin(top_g)]
        .groupby(["품목군", "연도"])[val_col]
        .sum().unstack(fill_value=0).reset_index()
    )
    tbl1.columns.name = None
    num_cols = [c for c in tbl1.columns if isinstance(c, int)]
    tbl1["합계"] = tbl1[num_cols].sum(axis=1)
    tbl1 = tbl1.sort_values("합계", ascending=False).reset_index(drop=True)
    tbl1.index = tbl1.index + 1  # 1부터 시작
    st.caption("품목군별 연도 소계")
    st.dataframe(
        tbl1.style.format({c: "{:,.0f}" for c in num_cols + ["합계"]}),
        use_container_width=True, height=480,
    )


# ════════════════════════════════════════════════
# TAB 2: 품목별 입고수량
# ════════════════════════════════════════════════
with tab2:
    st.subheader(f"품목별 입고수량 상세 ({sel_unit})")

    col1, col2 = st.columns([1, 2])
    with col1:
        group2 = st.selectbox(
            "품목군 선택",
            ["(전체)"] + sorted(df["품목군"].unique()),
            key="g2",
        )
    with col2:
        keyword2 = st.text_input("품명 검색 (부분 입력)", key="kw2", placeholder="예: SOAP")

    df2 = df.copy()
    if group2 != "(전체)":
        df2 = df2[df2["품목군"] == group2]
    if keyword2:
        df2 = df2[df2["품명"].str.contains(keyword2, case=False, na=False)]

    if df2.empty:
        st.warning("해당 조건에 데이터가 없습니다.")
    else:
        top15 = df2.groupby("품명")["입고수량"].sum().nlargest(15).index.tolist()
        chart2 = (
            df2[df2["품명"].isin(top15)]
            .groupby(["품명", "연월"])["입고수량"]
            .sum().reset_index()
        )
        title2 = group2 if group2 != "(전체)" else "전체"
        fig2 = px.line(
            chart2, x="연월", y="입고수량", color="품명",
            markers=True,
            title=f"[{title2}] 품목별 월별 입고수량 (상위 15개)",
            labels={"연월": "", "입고수량": UNIT_LABEL},
        )
        fig2.update_layout(
            height=420, xaxis_tickangle=-45,
            yaxis_tickformat=",",
            legend=dict(orientation="v", x=1.01, y=1),
            margin=dict(r=200),
        )
        st.plotly_chart(fig2, use_container_width=True)

        # 품목별 합계 테이블
        st.caption("품목별 전체 기간 합계")
        tbl2 = (
            df2.groupby(["품목군", "품명"])
            .agg(총수량=("입고수량", "sum"), 평균단가=("외화단가", "mean"))
            .reset_index()
            .sort_values("총수량", ascending=False)
        )
        tbl2["총수량"] = tbl2["총수량"].map(lambda v: f"{v:,.0f}")
        tbl2["평균단가"] = tbl2["평균단가"].map(lambda v: f"{v:,.1f}")
        st.dataframe(tbl2.reset_index(drop=True), use_container_width=True, height=340)


# ════════════════════════════════════════════════
# TAB 3: 단가 이상 감지
# ════════════════════════════════════════════════
with tab3:
    st.subheader("⚠️ 수입단가 이상 변동 감지")
    st.caption(f"기준: 전 입고월 대비 ±{threshold}% 초과 (이전단가 0 건 제외) | 단위: {sel_unit}")

    col1, col2 = st.columns([2, 1])
    with col2:
        countries3 = st.multiselect(
            "국가",
            global_country,
            default=global_country,
            key="c3",
        )
        groups3 = st.multiselect(
            "품목군 (미선택=전체)",
            sorted(df["품목군"].unique()),
            key="g3",
        )

    df3 = df[df["국가"].isin(countries3)]
    if groups3:
        df3 = df3[df3["품목군"].isin(groups3)]

    if df3.empty:
        st.warning("해당 조건에 데이터가 없습니다.")
    else:
        pm = (
            df3.groupby(["품명", "국가", "환종", "연월"])["외화단가"]
            .mean().reset_index().sort_values(["품명", "연월"])
        )
        pm["이전단가"] = pm.groupby(["품명", "환종"])["외화단가"].shift(1)
        pm["변동률"] = (
            (pm["외화단가"] - pm["이전단가"]) / pm["이전단가"] * 100
        ).round(1)

        anom = (
            pm[(pm["변동률"].abs() > threshold) & (pm["이전단가"] > 0)]
            .dropna(subset=["변동률"])
            .sort_values("변동률", key=abs, ascending=False)
        )

        with col1:
            if anom.empty:
                st.success(f"✅ ±{threshold}% 이상 변동 품목 없음")
            else:
                m1, m2, m3 = st.columns(3)
                m1.metric("이상 감지", f"{len(anom)}건")
                m2.metric("↑ 상승", f"{(anom['변동률'] > 0).sum()}건")
                m3.metric("↓ 하락", f"{(anom['변동률'] < 0).sum()}건")

                disp = anom[["품명", "국가", "연월", "이전단가", "외화단가", "변동률"]].copy()
                disp.columns = ["품명", "국가", "연월", "이전단가", "현재단가", "변동률(%)"]
                disp["이전단가"] = disp["이전단가"].map(lambda v: f"{v:,.1f}")
                disp["현재단가"] = disp["현재단가"].map(lambda v: f"{v:,.1f}")

                def color_pct(v):
                    try:
                        v = float(v)
                        if v > 0:
                            return "color:#E15759;font-weight:bold"
                        if v < 0:
                            return "color:#4E79A7;font-weight:bold"
                    except Exception:
                        pass
                    return ""

                try:
                    styled = disp.style.map(color_pct, subset=["변동률(%)"])
                except AttributeError:
                    styled = disp.style.applymap(color_pct, subset=["변동률(%)"])

                st.dataframe(styled, use_container_width=True, height=400)

        # 이상 상위 5개 품목 단가 추이 (국가별 분리)
        if not anom.empty:
            top5 = anom["품명"].value_counts().head(5).index.tolist()
            pm_top = pm[pm["품명"].isin(top5)].dropna(subset=["외화단가"])
            if not pm_top.empty:
                st.divider()
                st.caption("이상 변동 상위 5개 품목 — 국가별 단가 추이")
                for country in countries3:
                    pm_c = pm_top[pm_top["국가"] == country]
                    if pm_c.empty:
                        continue
                    fig3 = px.line(
                        pm_c, x="연월", y="외화단가", color="품명",
                        markers=True,
                        title=f"{country} 단가 추이",
                        labels={"연월": "", "외화단가": "외화단가"},
                    )
                    fig3.update_layout(
                        height=320, xaxis_tickangle=-45,
                        yaxis_tickformat=",",
                        legend=dict(orientation="v", x=1.01, y=1),
                        margin=dict(r=200),
                    )
                    st.plotly_chart(fig3, use_container_width=True)


# ════════════════════════════════════════════════
# TAB 4: 국가별 추이
# ════════════════════════════════════════════════
with tab4:
    st.subheader(f"💱 국가별 수입 추이 ({sel_unit})")
    st.caption("국가별로 단위·환종이 같은 데이터를 비교합니다.")

    mc4 = (
        df.groupby(["연월", "국가"])
        .agg(수량=("입고수량", "sum"), 금액=("외화금액", "sum"))
        .reset_index()
    )

    col1, col2 = st.columns(2)
    with col1:
        fig4a = px.line(
            mc4, x="연월", y="수량", color="국가",
            color_discrete_map=COLOR_MAP,
            markers=True,
            title=f"월별 입고수량 ({sel_unit})",
            labels={"연월": "", "수량": UNIT_LABEL},
        )
        fig4a.update_layout(
            height=360, xaxis_tickangle=-45,
            yaxis_tickformat=",",
        )
        st.plotly_chart(fig4a, use_container_width=True)

    with col2:
        fig4b = px.line(
            mc4, x="연월", y="금액", color="국가",
            color_discrete_map=COLOR_MAP,
            markers=True,
            title="월별 외화금액",
            labels={"연월": "", "금액": "외화금액"},
        )
        fig4b.update_layout(
            height=360, xaxis_tickangle=-45,
            yaxis_tickformat=",",
        )
        st.plotly_chart(fig4b, use_container_width=True)

    # YoY (13개월 이상일 때만)
    if len(all_months) >= 13:
        st.divider()
        yoy_frames = []
        for country in global_country:
            cdf = mc4[mc4["국가"] == country].copy().sort_values("연월")
            cdf["YoY(%)"] = (cdf["수량"].pct_change(12) * 100).round(1)
            yoy_frames.append(cdf)
        yoy_all = pd.concat(yoy_frames).dropna(subset=["YoY(%)"])
        if not yoy_all.empty:
            fig4c = px.bar(
                yoy_all, x="연월", y="YoY(%)", color="국가",
                color_discrete_map=COLOR_MAP,
                barmode="group",
                title="수량 전년 동월 대비 (%)",
                labels={"연월": "", "YoY(%)": "YoY (%)"},
            )
            fig4c.add_hline(y=0, line_dash="dash", line_color="gray")
            fig4c.update_layout(height=300, xaxis_tickangle=-45)
            st.plotly_chart(fig4c, use_container_width=True)

    # 국가별 월별 수량 테이블
    st.divider()
    st.caption("국가별 월별 수량 상세")
    tbl4 = mc4.pivot(index="연월", columns="국가", values="수량").fillna(0)
    tbl4.columns.name = None
    tbl4["합계"] = tbl4.sum(axis=1)
    num_cols4 = list(tbl4.columns)
    st.dataframe(
        tbl4.style.format("{:,.0f}", subset=num_cols4),
        use_container_width=True, height=320,
    )


# ════════════════════════════════════════════════
# TAB 5: 신규 / 중단 품목
# ════════════════════════════════════════════════
with tab5:
    st.subheader(f"🔍 신규 / 중단 품목 현황 ({sel_unit})")

    all_m5 = sorted(df["연월"].unique())
    if len(all_m5) < 2:
        st.warning("데이터가 부족합니다.")
        st.stop()

    item5 = (
        df.groupby(["품명", "품목군", "국가"])["연월"]
        .agg(첫입고월="min", 마지막입고월="max", 입고횟수="count")
        .reset_index()
    )
    recent_cut = all_m5[-3] if len(all_m5) >= 3 else all_m5[0]
    disc_cut   = all_m5[-4] if len(all_m5) >= 4 else all_m5[0]

    new_items  = item5[item5["첫입고월"] >= recent_cut].sort_values("첫입고월", ascending=False)
    disc_items = item5[item5["마지막입고월"] <= disc_cut].sort_values("마지막입고월", ascending=False)

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("#### 🆕 신규 품목 (최근 3개월 내 첫 입고)")
        st.metric("신규 품목 수", f"{len(new_items)}개")
        if not new_items.empty:
            st.dataframe(new_items.reset_index(drop=True),
                         use_container_width=True, height=420)
        else:
            st.info("신규 품목이 없습니다.")
    with c2:
        st.markdown("#### 🚫 중단 의심 (4개월 이상 미입고)")
        st.metric("중단 의심 품목 수", f"{len(disc_items)}개")
        if not disc_items.empty:
            st.dataframe(disc_items.reset_index(drop=True),
                         use_container_width=True, height=420)
        else:
            st.info("중단 의심 품목이 없습니다.")
