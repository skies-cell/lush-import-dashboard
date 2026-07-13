import io
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(
    page_title="수입단가 현황 대시보드",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── 사이드바 ────────────────────────────────────────────────────
with st.sidebar:
    st.header("📦 수입단가 대시보드")
    uploaded = st.file_uploader(
        "Excel 파일 업로드",
        type=["xlsx", "xls"],
        help="'입고현황' 시트가 포함된 파일을 올려주세요.",
    )
    st.divider()
    threshold = st.slider("단가 이상 감지 기준 (%)", 1, 50, 10,
                          help="전 입고월 대비 변동률이 이 값을 초과하면 이상으로 표시합니다.")

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
    df["단위_정규"] = df["단위"].apply(
        lambda u: "G" if str(u).strip().upper() == "G"
        else ("EA" if str(u).strip().upper() == "EA" else str(u).strip().upper())
        if pd.notna(u) else "기타"
    )
    df["품목군"] = (
        df["품명"].str.extract(r"\(([^)]+)\)(?:\s*_\w+)?\s*$")
        .iloc[:, 0].str.upper().str.strip().fillna("기타")
    )
    df["국가"] = df["환종"].map(
        {"JPY": "일본", "GBP": "영국", "USD": "USD", "CAD": "CAD"}
    ).fillna(df["환종"])
    df = df[pd.to_numeric(df["입고수량"], errors="coerce") > 0].copy()
    df["외화단가"] = pd.to_numeric(df["외화단가"], errors="coerce")
    df["외화금액"] = pd.to_numeric(df["외화금액"], errors="coerce")
    df["입고수량"] = pd.to_numeric(df["입고수량"], errors="coerce")
    df = df.dropna(subset=["외화단가", "입고수량"])
    return df


df = load_data(uploaded.read())
all_months = sorted(df["연월"].unique())

# ── KPI 헤더 ────────────────────────────────────────────────────
st.title("📦 수입단가 현황 대시보드")
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("데이터 기간", f"{all_months[0][:7]} ~ {all_months[-1][:7]}")
k2.metric("총 입고 건수", f"{len(df):,}건")
k3.metric("품목 수", f"{df['품명'].nunique():,}개")
k4.metric("품목군 수", f"{df['품목군'].nunique()}개")
k5.metric("공급처 수", f"{df['거래처'].nunique()}개")
st.divider()

COLOR_MAP = {"일본": "#4E79A7", "영국": "#E15759", "USD": "#59A14F", "CAD": "#F28E2B"}

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 품목군별 월별 현황",
    "📦 품목별 입고수량",
    "⚠️ 단가 이상 감지",
    "💱 국가별 추이",
    "🔍 신규 / 중단 품목",
])


# ════════════════════════════════════════════════
# TAB 1: 품목군별 월별 현황 — 선 차트
# ════════════════════════════════════════════════
with tab1:
    st.subheader("품목군별 월별 수입 현황")

    col_f1, col_f2, col_f3, col_f4 = st.columns([1, 1, 1, 1])
    with col_f1:
        units1 = st.multiselect("단위", sorted(df["단위_정규"].unique()),
                                default=sorted(df["단위_정규"].unique()), key="u1")
    with col_f2:
        countries1 = st.multiselect("국가", sorted(df["국가"].unique()),
                                    default=sorted(df["국가"].unique()), key="c1")
    with col_f3:
        metric1 = st.radio("보기 기준", ["수량", "금액"], horizontal=True, key="m1")
    with col_f4:
        top_n1 = st.slider("상위 품목군", 3, 15, 8, key="n1")

    df1 = df[df["단위_정규"].isin(units1) & df["국가"].isin(countries1)]
    val_col1 = "입고수량" if metric1 == "수량" else "외화금액"
    val_label1 = "입고수량" if metric1 == "수량" else "외화금액"

    if df1.empty:
        st.warning("선택한 조건에 해당하는 데이터가 없습니다.")
    else:
        top_g1 = df1.groupby("품목군")[val_col1].sum().nlargest(top_n1).index.tolist()
        monthly1 = (
            df1[df1["품목군"].isin(top_g1)]
            .groupby(["연월", "품목군"])[val_col1]
            .sum().reset_index()
        )

        # 선 차트 (추세 파악에 적합)
        fig1 = px.line(
            monthly1, x="연월", y=val_col1, color="품목군",
            markers=True,
            title=f"품목군별 월별 {val_label1} 추이 (상위 {top_n1}개)",
            labels={"연월": "", val_col1: val_label1, "품목군": "품목군"},
        )
        fig1.update_layout(height=420, xaxis_tickangle=-45,
                           legend=dict(orientation="v", x=1.01, y=1))
        fig1.update_traces(line=dict(width=2))
        st.plotly_chart(fig1, use_container_width=True)

        # 연도 소계 테이블
        st.caption("연도별 품목군 소계")
        df1y = df1.copy()
        df1y["연도"] = df1y["입고일자"].dt.year
        tbl1 = (
            df1y[df1y["품목군"].isin(top_g1)]
            .groupby(["품목군", "연도"])[val_col1]
            .sum().unstack(fill_value=0).reset_index()
        )
        tbl1.columns.name = None
        num_cols = [c for c in tbl1.columns if isinstance(c, int)]
        tbl1["합계"] = tbl1[num_cols].sum(axis=1)
        st.dataframe(tbl1.sort_values("합계", ascending=False),
                     use_container_width=True, height=260)


# ════════════════════════════════════════════════
# TAB 2: 품목별 입고수량
# ════════════════════════════════════════════════
with tab2:
    st.subheader("품목별 입고수량 상세")

    col_f1, col_f2, col_f3 = st.columns([1, 1, 2])
    with col_f1:
        units2 = st.multiselect("단위", sorted(df["단위_정규"].unique()),
                                default=sorted(df["단위_정규"].unique()), key="u2")
    with col_f2:
        countries2 = st.multiselect("국가", sorted(df["국가"].unique()),
                                    default=sorted(df["국가"].unique()), key="c2")
    with col_f3:
        group2 = st.selectbox("품목군", ["(전체)"] + sorted(df["품목군"].unique()), key="g2")

    df2 = df[df["단위_정규"].isin(units2) & df["국가"].isin(countries2)]
    if group2 != "(전체)":
        df2 = df2[df2["품목군"] == group2]

    if df2.empty:
        st.warning("선택한 조건에 해당하는 데이터가 없습니다.")
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
            labels={"연월": "", "입고수량": "입고수량", "품명": "품명"},
        )
        fig2.update_layout(height=420, xaxis_tickangle=-45,
                           legend=dict(orientation="v", x=1.01, y=1))
        st.plotly_chart(fig2, use_container_width=True)

        st.caption("품목별 월별 피벗 테이블")
        pivot2 = (
            df2.groupby(["품명", "단위_정규"])["입고수량"]
            .sum().reset_index()
            .rename(columns={"입고수량": "합계", "단위_정규": "단위"})
            .sort_values("합계", ascending=False)
        )
        st.dataframe(pivot2.reset_index(drop=True), use_container_width=True, height=320)


# ════════════════════════════════════════════════
# TAB 3: 단가 이상 감지
# ════════════════════════════════════════════════
with tab3:
    st.subheader(f"⚠️ 수입단가 이상 변동 감지")
    st.caption(f"전 입고월 대비 ±{threshold}% 초과 변동 품목 (이전단가 0원 건 제외)")

    col_f1, col_f2, col_f3 = st.columns([1, 1, 2])
    with col_f1:
        units3 = st.multiselect("단위", sorted(df["단위_정규"].unique()),
                                default=sorted(df["단위_정규"].unique()), key="u3")
    with col_f2:
        countries3 = st.multiselect("국가", sorted(df["국가"].unique()),
                                    default=sorted(df["국가"].unique()), key="c3")
    with col_f3:
        groups3 = st.multiselect("품목군 필터 (미선택=전체)",
                                 sorted(df["품목군"].unique()), key="g3")

    df3 = df[df["단위_정규"].isin(units3) & df["국가"].isin(countries3)]
    if groups3:
        df3 = df3[df3["품목군"].isin(groups3)]

    if df3.empty:
        st.warning("선택한 조건에 해당하는 데이터가 없습니다.")
    else:
        pm = (
            df3.groupby(["품명", "국가", "환종", "단위_정규", "연월"])["외화단가"]
            .mean().reset_index().sort_values(["품명", "연월"])
        )
        pm["이전단가"] = pm.groupby(["품명", "환종"])["외화단가"].shift(1)
        pm["변동률(%)"] = (
            (pm["외화단가"] - pm["이전단가"]) / pm["이전단가"] * 100
        ).round(2)

        anom = (
            pm[(pm["변동률(%)"].abs() > threshold) & (pm["이전단가"] > 0)]
            .dropna(subset=["변동률(%)"])
            .sort_values("변동률(%)", key=abs, ascending=False)
        )

        if anom.empty:
            st.success(f"✅ ±{threshold}% 이상 변동 품목이 없습니다.")
        else:
            m1, m2, m3 = st.columns(3)
            m1.metric("이상 감지", f"{len(anom)}건")
            m2.metric("↑ 단가 상승", f"{(anom['변동률(%)'] > 0).sum()}건")
            m3.metric("↓ 단가 하락", f"{(anom['변동률(%)'] < 0).sum()}건")

            disp = anom[["품명", "국가", "단위_정규", "연월",
                          "이전단가", "외화단가", "변동률(%)"]].copy()
            disp.columns = ["품명", "국가", "단위", "연월",
                            "이전단가", "현재단가", "변동률(%)"]

            # pandas 버전 호환: applymap → map (2.1+)
            try:
                styled = disp.style.map(
                    lambda v: "color:#E15759;font-weight:bold" if isinstance(v, float) and v > 0
                    else ("color:#4E79A7;font-weight:bold" if isinstance(v, float) and v < 0 else ""),
                    subset=["변동률(%)"]
                )
            except AttributeError:
                styled = disp.style.applymap(
                    lambda v: "color:#E15759;font-weight:bold" if isinstance(v, float) and v > 0
                    else ("color:#4E79A7;font-weight:bold" if isinstance(v, float) and v < 0 else ""),
                    subset=["변동률(%)"]
                )
            st.dataframe(styled, use_container_width=True, height=380)

            # 이상 상위 5개 품목 단가 추이
            top5 = anom["품명"].value_counts().head(5).index.tolist()
            if top5:
                st.divider()
                st.caption("이상 변동 상위 5개 품목 단가 추이")
                pm_top = pm[pm["품명"].isin(top5)].dropna(subset=["외화단가"])
                fig3 = px.line(
                    pm_top, x="연월", y="외화단가", color="품명",
                    markers=True,
                    labels={"연월": "", "외화단가": "외화단가", "품명": "품명"},
                )
                fig3.update_layout(height=350, xaxis_tickangle=-45,
                                   legend=dict(orientation="v", x=1.01, y=1))
                st.plotly_chart(fig3, use_container_width=True)


# ════════════════════════════════════════════════
# TAB 4: 국가별 추이 — 선 차트
# ════════════════════════════════════════════════
with tab4:
    st.subheader("💱 국가(환종)별 수입 추이")

    col_f1, col_f2 = st.columns(2)
    with col_f1:
        units4 = st.multiselect("단위", sorted(df["단위_정규"].unique()),
                                default=sorted(df["단위_정규"].unique()), key="u4")
    with col_f2:
        countries4 = st.multiselect("국가", sorted(df["국가"].unique()),
                                    default=sorted(df["국가"].unique()), key="c4")

    df4 = df[df["단위_정규"].isin(units4) & df["국가"].isin(countries4)]

    if df4.empty:
        st.warning("선택한 조건에 해당하는 데이터가 없습니다.")
    else:
        mc4 = (
            df4.groupby(["연월", "국가"])
            .agg(수량=("입고수량", "sum"), 금액=("외화금액", "sum"))
            .reset_index()
        )

        col1, col2 = st.columns(2)
        with col1:
            fig4a = px.line(
                mc4, x="연월", y="수량", color="국가",
                color_discrete_map=COLOR_MAP,
                markers=True,
                title="월별 입고수량 추이",
                labels={"연월": "", "수량": "입고수량", "국가": "국가"},
            )
            fig4a.update_layout(height=360, xaxis_tickangle=-45)
            st.plotly_chart(fig4a, use_container_width=True)
        with col2:
            fig4b = px.line(
                mc4, x="연월", y="금액", color="국가",
                color_discrete_map=COLOR_MAP,
                markers=True,
                title="월별 외화금액 추이",
                labels={"연월": "", "금액": "외화금액", "국가": "국가"},
            )
            fig4b.update_layout(height=360, xaxis_tickangle=-45)
            st.plotly_chart(fig4b, use_container_width=True)

        # YoY (12개월 이상 데이터 있을 때만)
        if len(all_months) >= 13:
            st.divider()
            st.caption("전년 동월 대비 수량 변화 (%)")
            yoy_frames = []
            for country in countries4:
                cdf = mc4[mc4["국가"] == country].copy().sort_values("연월")
                cdf["YoY(%)"] = (cdf["수량"].pct_change(12) * 100).round(1)
                yoy_frames.append(cdf)

            if yoy_frames:
                yoy_all = pd.concat(yoy_frames).dropna(subset=["YoY(%)"])
                if not yoy_all.empty:
                    fig4c = px.bar(
                        yoy_all, x="연월", y="YoY(%)", color="국가",
                        color_discrete_map=COLOR_MAP,
                        barmode="group",
                        title="수량 YoY (%)",
                        labels={"연월": "", "YoY(%)": "YoY (%)"},
                    )
                    fig4c.add_hline(y=0, line_dash="dash", line_color="gray")
                    fig4c.update_layout(height=300, xaxis_tickangle=-45)
                    st.plotly_chart(fig4c, use_container_width=True)


# ════════════════════════════════════════════════
# TAB 5: 신규 / 중단 품목
# ════════════════════════════════════════════════
with tab5:
    st.subheader("🔍 신규 / 중단 품목 현황")

    col_f1, col_f2 = st.columns(2)
    with col_f1:
        units5 = st.multiselect("단위", sorted(df["단위_정규"].unique()),
                                default=sorted(df["단위_정규"].unique()), key="u5")
    with col_f2:
        countries5 = st.multiselect("국가", sorted(df["국가"].unique()),
                                    default=sorted(df["국가"].unique()), key="c5")

    df5 = df[df["단위_정규"].isin(units5) & df["국가"].isin(countries5)]

    if df5.empty or len(all_months) < 2:
        st.warning("데이터가 부족합니다.")
    else:
        all_m5 = sorted(df5["연월"].unique())
        item5 = (
            df5.groupby(["품명", "품목군", "국가", "단위_정규"])["연월"]
            .agg(첫입고월="min", 마지막입고월="max")
            .reset_index()
        )
        recent_cut = all_m5[-3] if len(all_m5) >= 3 else all_m5[0]
        disc_cut   = all_m5[-4] if len(all_m5) >= 4 else all_m5[0]

        new_items  = item5[item5["첫입고월"] >= recent_cut].sort_values("첫입고월", ascending=False)
        disc_items = item5[item5["마지막입고월"] <= disc_cut].sort_values("마지막입고월", ascending=False)

        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"#### 🆕 신규 품목 — 최근 3개월 내 첫 입고")
            st.metric("신규 품목 수", f"{len(new_items)}개")
            if not new_items.empty:
                st.dataframe(new_items.reset_index(drop=True),
                             use_container_width=True, height=400)
            else:
                st.info("신규 품목이 없습니다.")
        with c2:
            st.markdown(f"#### 🚫 중단 의심 — 4개월 이상 미입고")
            st.metric("중단 의심 품목 수", f"{len(disc_items)}개")
            if not disc_items.empty:
                st.dataframe(disc_items.reset_index(drop=True),
                             use_container_width=True, height=400)
            else:
                st.info("중단 의심 품목이 없습니다.")
