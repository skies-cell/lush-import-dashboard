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

# ── 글로벌 CSS ─────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;600;700&display=swap');

html, body, [class*="css"], .stMarkdown, button, input, select, textarea,
div[data-testid="stAppViewContainer"] {
    font-family: 'Noto Sans KR', sans-serif !important;
}

/* 사이드바 배경 */
section[data-testid="stSidebar"] > div:first-child {
    background: #1e2130 !important;
}
/* 사이드바 일반 텍스트 (파일업로더 제외) */
section[data-testid="stSidebar"] h1,
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3,
section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] span:not([data-testid*="File"]),
section[data-testid="stSidebar"] div[class*="stRadio"] *,
section[data-testid="stSidebar"] div[class*="stMultiSelect"] *,
section[data-testid="stSidebar"] div[class*="stSlider"] *,
section[data-testid="stSidebar"] hr {
    color: #d8ddf0 !important;
    font-family: 'Noto Sans KR', sans-serif !important;
}

/* 파일업로더 — 별도 흰 배경이므로 글씨 어둡게 */
section[data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"],
section[data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] *,
section[data-testid="stSidebar"] [data-testid="stFileUploaderDropzoneInstructions"],
section[data-testid="stSidebar"] [data-testid="stFileUploaderDropzoneInstructions"] *,
section[data-testid="stSidebar"] [data-testid="stFileUploader"] small,
section[data-testid="stSidebar"] [data-testid="stFileUploader"] span {
    color: #374151 !important;
}
section[data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] {
    background: #ffffff !important;
    border: 1.5px dashed #6b7280 !important;
    border-radius: 8px !important;
}

/* KPI 카드 */
div[data-testid="metric-container"] {
    background: #ffffff;
    border: 1px solid #e8eaf0;
    border-radius: 12px;
    padding: 14px 16px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.06);
    overflow: hidden;
    min-width: 0;
}
div[data-testid="metric-container"] label {
    font-size: 12px !important;
    color: #6b7280 !important;
    font-weight: 500 !important;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    display: block;
}
div[data-testid="metric-container"] [data-testid="stMetricValue"] {
    font-size: 17px !important;
    font-weight: 700 !important;
    color: #111827 !important;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

/* 데이터프레임 */
div[data-testid="stDataFrame"] * {
    font-family: 'Noto Sans KR', sans-serif !important;
    font-size: 13.5px !important;
}
div[data-testid="stDataFrame"] th {
    font-size: 13px !important;
    font-weight: 700 !important;
    background: #eef2ff !important;
    color: #1e3a5f !important;
}

/* 탭 */
button[data-baseweb="tab"] {
    font-family: 'Noto Sans KR', sans-serif !important;
    font-size: 14px !important;
    font-weight: 600 !important;
}

/* 섹션 박스 */
.section-box {
    background: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 12px;
    padding: 18px 22px;
    margin-bottom: 14px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.04);
}
.section-title {
    font-family: 'Noto Sans KR', sans-serif;
    font-size: 14px;
    font-weight: 700;
    color: #1e3a5f;
    margin-bottom: 10px;
    border-left: 3px solid #4E79A7;
    padding-left: 8px;
}
</style>
""", unsafe_allow_html=True)

# ── 색상 팔레트 & 공통 함수 ─────────────────────────────────────
COLORS = [
    "#4E79A7","#E15759","#59A14F","#F28E2B","#76B7B2",
    "#B07AA1","#EDC948","#FF9DA7","#9C755F","#499894",
    "#D37295","#BAB0AC","#A0CBE8","#FFBE7D","#8CD17D",
]
COLOR_MAP = {"일본": "#4E79A7", "영국": "#E15759"}
_FONT = dict(family="Noto Sans KR, sans-serif", size=13, color="#374151")

def apply_base(fig, height=420, yformat=","):
    fig.update_layout(
        height=height,
        paper_bgcolor="white",
        plot_bgcolor="white",
        font=_FONT,
        xaxis=dict(showgrid=False, tickangle=-40, tickfont=dict(size=11)),
        yaxis=dict(gridcolor="#f0f0f0", gridwidth=1,
                   tickfont=dict(size=11), tickformat=yformat),
        legend=dict(bgcolor="rgba(255,255,255,0.95)", bordercolor="#e5e7eb",
                    borderwidth=1, font=dict(size=11)),
        margin=dict(l=60, r=40, t=50, b=70),
        hovermode="x unified",
        title_font=dict(size=14, color="#111827", family="Noto Sans KR, sans-serif"),
    )
    return fig

def safe_gradient(styler, subset, cmap="Blues"):
    try:
        return styler.background_gradient(subset=subset, cmap=cmap, low=0.05, high=0.75)
    except Exception:
        return styler

def tbl_style(styler):
    return styler.set_table_styles([{
        "selector": "th",
        "props": [("font-size","13px"),("font-weight","700"),
                  ("background-color","#eef2ff"),("color","#1e3a5f"),
                  ("text-align","center"), ("white-space","nowrap")],
    }]).set_properties(**{"font-size": "13.5px"})

# ── 사이드바 ───────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📦 수입단가 대시보드")
    st.markdown("---")
    uploaded = st.file_uploader(
        "Excel 파일 업로드", type=["xlsx", "xls"],
        help="'입고현황' 시트가 포함된 파일을 업로드하세요",
    )
    if uploaded:
        st.markdown("### 전역 필터")
        global_unit = st.radio("단위", ["EA (완제품)", "G (원자재)"], index=0)
        global_country = st.multiselect("국가", ["일본", "영국"], default=["일본", "영국"])
        st.markdown("---")
        threshold = st.slider("단가 이상 감지 기준 (%)", 1, 50, 10)

if not uploaded:
    st.markdown("""
    <div style='text-align:center;padding:100px 0;font-family:Noto Sans KR,sans-serif'>
        <h1 style='color:#1e3a5f'>📦 수입단가 현황 대시보드</h1>
        <p style='color:#6b7280;font-size:16px;margin-top:16px'>
            왼쪽 사이드바에서 Excel 파일을 업로드하면 대시보드가 생성됩니다.
        </p>
    </div>""", unsafe_allow_html=True)
    st.stop()

# ── 데이터 로드 ────────────────────────────────────────────────
@st.cache_data(show_spinner="📂 데이터 불러오는 중...")
def load_data(file_bytes: bytes) -> pd.DataFrame:
    df = pd.read_excel(
        io.BytesIO(file_bytes), sheet_name="입고현황",
        usecols="A:O", header=0, engine="openpyxl",
    )
    df.columns = [
        "입고일자","입고번호","거래처","거래구분","환종","담당자",
        "No","품번","품명","규격","단위","입고수량","외화단가","외화금액","해당월",
    ]
    df = df.dropna(subset=["해당월", "품명"])
    df["연월"] = (df["해당월"].astype(str).str.strip()
                 .str[:7].str.replace("-", "/", regex=False))
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
    for c in ["외화단가", "외화금액", "입고수량"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["외화단가", "입고수량"])
    return df

# uploaded.read()는 매 실행마다 한 번만 호출
_file_bytes = uploaded.read()
df_raw = load_data(_file_bytes)

sel_unit = "EA" if "EA" in global_unit else "G"
if not global_country:
    st.warning("국가를 하나 이상 선택해주세요.")
    st.stop()

df = df_raw[
    (df_raw["단위_정규"] == sel_unit) &
    (df_raw["국가"].isin(global_country))
].copy()

all_months = sorted(df_raw["연월"].unique())
UNIT_LABEL = "수량 (EA)" if sel_unit == "EA" else "중량 (G)"

if df.empty:
    st.warning("선택한 필터 조건에 해당하는 데이터가 없습니다.")
    st.stop()

# ── KPI 카드 ───────────────────────────────────────────────────
st.markdown(
    "<h2 style='font-family:Noto Sans KR,sans-serif;margin-bottom:4px;color:#111827'>"
    "📦 수입단가 현황 대시보드</h2>",
    unsafe_allow_html=True,
)
st.markdown(
    f"<p style='color:#6b7280;font-family:Noto Sans KR,sans-serif;margin-top:0'>"
    f"단위: <b>{sel_unit}</b> &nbsp;|&nbsp; 국가: <b>{', '.join(global_country)}</b></p>",
    unsafe_allow_html=True,
)

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("📅 기간", f"{all_months[0][:7]} ~ {all_months[-1][:7]}")
k2.metric("📋 입고건수", f"{len(df):,}건")
k3.metric("🏷️ 품목수", f"{df['품명'].nunique():,}개")
k4.metric("📁 품목군수", f"{df['품목군'].nunique()}개")
k5.metric("🏭 공급처수", f"{df['거래처'].nunique()}개")
st.markdown("<div style='margin:14px 0'></div>", unsafe_allow_html=True)

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 품목군별 현황",
    "📦 품목별 입고수량",
    "⚠️ 단가 이상 감지",
    "💱 국가별 추이",
    "🔍 신규 / 중단 품목",
])


# ════════════════════════════════════════════════
# TAB 1: 품목군별 월별 현황 — 스택 바 기본
# ════════════════════════════════════════════════
with tab1:
    c_opt, c_main = st.columns([1, 6])
    with c_opt:
        st.markdown('<div class="section-box">', unsafe_allow_html=True)
        top_n   = st.slider("상위 품목군", 3, 30, 15, key="n1")
        metric1 = st.radio("집계 기준", ["수량", "금액"], key="m1")
        chart1  = st.radio("차트 유형", ["스택 바", "라인"], key="ct1")
        st.markdown('</div>', unsafe_allow_html=True)

    val_col = "입고수량" if metric1 == "수량" else "외화금액"
    val_lbl = UNIT_LABEL if metric1 == "수량" else "외화금액"
    top_g   = df.groupby("품목군")[val_col].sum().nlargest(top_n).index.tolist()
    monthly = (
        df[df["품목군"].isin(top_g)]
        .groupby(["연월", "품목군"])[val_col].sum().reset_index()
    )

    with c_main:
        if chart1 == "스택 바":
            fig1 = px.bar(
                monthly, x="연월", y=val_col, color="품목군",
                barmode="stack",
                color_discrete_sequence=COLORS,
                labels={"연월": "", "품목군": "품목군", val_col: val_lbl},
            )
            fig1.update_traces(marker_line_width=0)
        else:
            fig1 = px.line(
                monthly, x="연월", y=val_col, color="품목군",
                markers=True,
                color_discrete_sequence=COLORS,
                labels={"연월": "", "품목군": "품목군", val_col: val_lbl},
            )
            fig1.update_traces(line=dict(width=2), marker=dict(size=4))

        apply_base(fig1, height=500)
        fig1.update_layout(
            title=f"품목군별 월별 {val_lbl} 추이 (상위 {top_n}개)",
            legend=dict(
                orientation="v", x=1.01, y=1,
                font=dict(size=10),
                bgcolor="rgba(255,255,255,0.95)",
                title_text="품목군",
            ),
            margin=dict(l=60, r=180, t=50, b=70),
        )
        st.plotly_chart(fig1, use_container_width=True)

    # 연도 소계 테이블
    st.markdown('<div class="section-box">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">품목군별 연도 소계</div>', unsafe_allow_html=True)
    df1y = df.copy()
    df1y["연도"] = df1y["연월"].str[:4]
    tbl1 = (
        df1y[df1y["품목군"].isin(top_g)]
        .groupby(["품목군", "연도"])[val_col].sum()
        .unstack(fill_value=0).reset_index()
    )
    tbl1.columns.name = None
    num_c1 = [c for c in tbl1.columns if c != "품목군"]
    tbl1["합계"] = tbl1[num_c1].sum(axis=1)
    tbl1 = tbl1.sort_values("합계", ascending=False).reset_index(drop=True)
    tbl1.index += 1
    styled1 = tbl1.style.format({c: "{:,.0f}" for c in num_c1 + ["합계"]})
    styled1 = safe_gradient(styled1, num_c1 + ["합계"])
    styled1 = tbl_style(styled1).set_properties(**{"text-align": "right"})
    styled1 = styled1.set_properties(subset=["품목군"], **{"text-align": "left"})
    st.dataframe(styled1, use_container_width=True, height=500)
    st.markdown('</div>', unsafe_allow_html=True)


# ════════════════════════════════════════════════
# TAB 2: 품목별 입고수량
# ════════════════════════════════════════════════
with tab2:
    st.markdown('<div class="section-box">', unsafe_allow_html=True)
    fa, fb, fc = st.columns(3)
    with fa:
        group2 = st.selectbox("품목군", ["(전체)"] + sorted(df["품목군"].unique()), key="g2")
    with fb:
        avail = sorted(
            df[df["품목군"] == group2]["품명"].unique()
            if group2 != "(전체)" else df["품명"].unique()
        )
        sel_items = st.multiselect("품목 선택 (미선택=상위 15개)", avail, key="items2")
    with fc:
        kw2 = st.text_input("품명 검색", placeholder="예: SOAP", key="kw2")
    st.markdown('</div>', unsafe_allow_html=True)

    df2 = df.copy()
    if group2 != "(전체)":
        df2 = df2[df2["품목군"] == group2]
    if sel_items:
        df2 = df2[df2["품명"].isin(sel_items)]
    if kw2:
        df2 = df2[df2["품명"].str.contains(kw2, case=False, na=False)]

    if df2.empty:
        st.warning("해당 조건에 데이터가 없습니다.")
    else:
        # 기간 합계 수평 바 (랭킹 Overview)
        rank_df = (df2.groupby("품명")["입고수량"].sum()
                   .sort_values(ascending=False).head(20).reset_index())
        rank_df.columns = ["품명", "총수량"]

        c_bar, c_trend = st.columns([1, 1])
        with c_bar:
            fig2a = px.bar(
                rank_df, y="품명", x="총수량", orientation="h",
                color="총수량", color_continuous_scale="Blues",
                labels={"총수량": UNIT_LABEL, "품명": ""},
            )
            fig2a.update_layout(
                height=480, title="기간 합계 Top 20",
                paper_bgcolor="white", plot_bgcolor="white",
                font=_FONT, showlegend=False,
                coloraxis_showscale=False,
                yaxis=dict(autorange="reversed", tickfont=dict(size=11)),
                xaxis=dict(tickformat=",", gridcolor="#f0f0f0"),
                margin=dict(l=150, r=30, t=50, b=50),
                title_font=dict(size=14, color="#111827"),
            )
            st.plotly_chart(fig2a, use_container_width=True)

        with c_trend:
            top_items = rank_df["품명"].head(10).tolist()
            show_items = sel_items if sel_items else top_items
            chart2 = (
                df2[df2["품명"].isin(show_items)]
                .groupby(["품명", "연월"])["입고수량"].sum().reset_index()
            )
            if not chart2.empty:
                fig2b = px.line(
                    chart2, x="연월", y="입고수량", color="품명",
                    markers=True, color_discrete_sequence=COLORS,
                    labels={"연월": "", "입고수량": UNIT_LABEL, "품명": ""},
                )
                fig2b.update_traces(line=dict(width=2), marker=dict(size=4))
                apply_base(fig2b, height=480)
                fig2b.update_layout(
                    title=f"월별 추이 ({'선택 품목' if sel_items else '상위 10개'})",
                    legend=dict(orientation="v", x=1.01, y=1, font=dict(size=10)),
                    margin=dict(l=60, r=160, t=50, b=70),
                )
                st.plotly_chart(fig2b, use_container_width=True)

        st.markdown('<div class="section-box">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">품목별 합계</div>', unsafe_allow_html=True)
        tbl2 = (
            df2.groupby(["품목군", "품명"]).agg(
                총수량=("입고수량", "sum"),
                평균단가=("외화단가", "mean"),
                입고횟수=("입고수량", "count"),
            ).reset_index()
            .sort_values("총수량", ascending=False).reset_index(drop=True)
        )
        tbl2.index += 1
        s2 = tbl2.style.format({"총수량": "{:,.0f}", "평균단가": "{:,.1f}", "입고횟수": "{:,.0f}"})
        s2 = safe_gradient(s2, ["총수량"])
        st.dataframe(tbl_style(s2), use_container_width=True, height=380)
        st.markdown('</div>', unsafe_allow_html=True)


# ════════════════════════════════════════════════
# TAB 3: 단가 이상 감지
# ════════════════════════════════════════════════
with tab3:
    col_tbl, col_flt = st.columns([3, 1])
    with col_flt:
        st.markdown('<div class="section-box">', unsafe_allow_html=True)
        countries3 = st.multiselect("국가", global_country, default=global_country, key="c3")
        groups3    = st.multiselect("품목군 (미선택=전체)", sorted(df["품목군"].unique()), key="g3")
        st.markdown('</div>', unsafe_allow_html=True)

    df3 = df[df["국가"].isin(countries3)] if countries3 else df.iloc[:0]
    if groups3:
        df3 = df3[df3["품목군"].isin(groups3)]

    if df3.empty:
        with col_tbl:
            st.warning("해당 조건에 데이터가 없습니다.")
    else:
        pm = (
            df3.groupby(["품명", "국가", "환종", "연월"])["외화단가"]
            .mean().reset_index().sort_values(["품명", "연월"])
        )
        pm["이전단가"] = pm.groupby(["품명", "환종"])["외화단가"].shift(1)
        pm["변동률"]   = ((pm["외화단가"] - pm["이전단가"]) / pm["이전단가"] * 100).round(1)
        anom = (
            pm[(pm["변동률"].abs() > threshold) & (pm["이전단가"] > 0)]
            .dropna(subset=["변동률"])
            .sort_values("변동률", key=abs, ascending=False)
        )

        with col_tbl:
            if anom.empty:
                st.success(f"✅ ±{threshold}% 이상 변동 품목이 없습니다.")
            else:
                m1, m2, m3 = st.columns(3)
                m1.metric("이상 감지", f"{len(anom)}건")
                m2.metric("↑ 단가 상승", f"{(anom['변동률'] > 0).sum()}건")
                m3.metric("↓ 단가 하락", f"{(anom['변동률'] < 0).sum()}건")

                disp = anom[["품명", "국가", "연월", "이전단가", "외화단가", "변동률"]].copy()
                disp.columns = ["품명", "국가", "연월", "이전단가", "현재단가", "변동률(%)"]
                disp = disp.reset_index(drop=True)
                disp.index += 1

                def color_pct(v):
                    try:
                        fv = float(v)
                        if fv > 0: return "color:#E15759;font-weight:bold"
                        if fv < 0: return "color:#4E79A7;font-weight:bold"
                    except Exception:
                        pass
                    return ""

                try:
                    s3 = disp.style.map(color_pct, subset=["변동률(%)"])
                except AttributeError:
                    s3 = disp.style.applymap(color_pct, subset=["변동률(%)"])
                s3 = s3.format({
                    "이전단가": "{:,.2f}", "현재단가": "{:,.2f}", "변동률(%)": "{:+.1f}%"
                })
                st.dataframe(tbl_style(s3), use_container_width=True, height=400)

        if not anom.empty:
            top5 = anom["품명"].value_counts().head(5).index.tolist()
            pm_top = pm[pm["품명"].isin(top5)].dropna(subset=["외화단가"])
            if not pm_top.empty:
                st.divider()
                st.markdown(
                    '<div class="section-title">이상 변동 상위 5개 품목 — 단가 추이</div>',
                    unsafe_allow_html=True,
                )
                chart_cols3 = st.columns(min(len(countries3), 2)) if countries3 else []
                for ci, country in enumerate(countries3):
                    pm_c = pm_top[pm_top["국가"] == country]
                    if pm_c.empty:
                        continue
                    with chart_cols3[ci] if chart_cols3 else st.container():
                        fig3 = px.line(
                            pm_c, x="연월", y="외화단가", color="품명",
                            markers=True, color_discrete_sequence=COLORS,
                            labels={"연월": "", "외화단가": "단가", "품명": ""},
                            title=f"[{country}] 이상 품목 단가 추이",
                        )
                        fig3.update_traces(line=dict(width=2), marker=dict(size=5))
                        apply_base(fig3, height=340)
                        fig3.update_layout(
                            legend=dict(orientation="v", x=1.01, y=1, font=dict(size=10)),
                            margin=dict(l=60, r=140, t=50, b=70),
                        )
                        st.plotly_chart(fig3, use_container_width=True)


# ════════════════════════════════════════════════
# TAB 4: 국가별 추이 — 금액 기준, 국가별 분리
# ════════════════════════════════════════════════
with tab4:
    st.caption("💡 영국(GBP)·일본(JPY)은 환종이 달라 같은 축에 표시하지 않고 국가별로 분리합니다.")

    mc4 = (
        df.groupby(["연월", "국가"])
        .agg(금액=("외화금액", "sum"), 수량=("입고수량", "sum"))
        .reset_index()
    )

    # 국가별 면적 차트 — 좌우 배치
    if global_country:
        cols4 = st.columns(len(global_country))
        for i, country in enumerate(global_country):
            cdf = mc4[mc4["국가"] == country].sort_values("연월")
            if cdf.empty:
                continue
            환종 = "JPY" if country == "일본" else "GBP"
            clr  = COLOR_MAP.get(country, "#4E79A7")
            fill = "rgba(78,121,167,0.12)" if country == "일본" else "rgba(225,87,89,0.12)"
            with cols4[i]:
                fig4 = go.Figure(go.Scatter(
                    x=cdf["연월"], y=cdf["금액"],
                    mode="lines+markers",
                    name=f"{country}",
                    line=dict(color=clr, width=2.5),
                    marker=dict(size=6, color=clr),
                    fill="tozeroy",
                    fillcolor=fill,
                    hovertemplate="%{x}<br>입고금액: %{y:,.0f}<extra></extra>",
                ))
                apply_base(fig4, height=360)
                fig4.update_layout(
                    title=f"【{country}】 월별 입고금액 ({환종})",
                    showlegend=False,
                    hovermode="x",
                )
                st.plotly_chart(fig4, use_container_width=True)

    # YoY 바 차트 (금액 기준)
    if len(all_months) >= 13:
        st.divider()
        st.markdown('<div class="section-title">입고금액 전년 동월 대비 (%)</div>',
                    unsafe_allow_html=True)
        yoy_list = []
        for country in global_country:
            cdf = mc4[mc4["국가"] == country].copy().sort_values("연월")
            cdf["YoY"] = (cdf["금액"].pct_change(12) * 100).round(1)
            yoy_list.append(cdf)
        if yoy_list:
            yoy_all = pd.concat(yoy_list).dropna(subset=["YoY"])
            if not yoy_all.empty:
                fig4c = px.bar(
                    yoy_all, x="연월", y="YoY", color="국가",
                    color_discrete_map=COLOR_MAP, barmode="group",
                    labels={"연월": "", "YoY": "YoY (%)"},
                )
                fig4c.add_hline(y=0, line_dash="dash", line_color="#9ca3af", line_width=1.5)
                apply_base(fig4c, height=300)
                fig4c.update_layout(title="입고금액 전년 동월 대비 (%)")
                st.plotly_chart(fig4c, use_container_width=True)

    # 국가별 월별 상세 테이블
    st.markdown('<div class="section-box">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">국가별 월별 입고금액 상세</div>', unsafe_allow_html=True)
    try:
        tbl4 = mc4.pivot_table(
            index="연월", columns="국가", values="금액", aggfunc="sum", fill_value=0
        )
        tbl4.columns.name = None
        tbl4["합계"] = tbl4.sum(axis=1)
        num_c4 = [c for c in tbl4.columns if c != "합계"]
        s4 = tbl4.style.format("{:,.0f}")
        s4 = safe_gradient(s4, ["합계"])
        st.dataframe(tbl_style(s4).set_properties(**{"text-align": "right"}),
                     use_container_width=True, height=380)
    except Exception as e:
        st.warning(f"테이블 렌더링 오류: {e}")
    st.markdown('</div>', unsafe_allow_html=True)


# ════════════════════════════════════════════════
# TAB 5: 신규 / 중단 품목
# ════════════════════════════════════════════════
with tab5:
    all_m5 = sorted(df["연월"].unique())
    if len(all_m5) < 2:
        st.warning("데이터가 부족합니다.")
        st.stop()

    item5 = (
        df.groupby(["품명", "품목군", "국가"]).agg(
            첫입고월=("연월", "min"),
            마지막입고월=("연월", "max"),
            입고횟수=("연월", "count"),
        ).reset_index()
    )
    recent_cut = all_m5[-3] if len(all_m5) >= 3 else all_m5[0]
    disc_cut   = all_m5[-4] if len(all_m5) >= 4 else all_m5[0]

    new_items  = (item5[item5["첫입고월"] >= recent_cut]
                  .sort_values("첫입고월", ascending=False).reset_index(drop=True))
    disc_items = (item5[item5["마지막입고월"] <= disc_cut]
                  .sort_values("마지막입고월", ascending=False).reset_index(drop=True))
    new_items.index  += 1
    disc_items.index += 1

    c1, c2 = st.columns(2)
    with c1:
        st.markdown('<div class="section-box">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">🆕 신규 품목 — 최근 3개월 내 첫 입고</div>',
                    unsafe_allow_html=True)
        st.metric("신규 품목 수", f"{len(new_items)}개")
        if not new_items.empty:
            st.dataframe(tbl_style(new_items.style), use_container_width=True, height=400)
        else:
            st.info("신규 품목이 없습니다.")
        st.markdown('</div>', unsafe_allow_html=True)

    with c2:
        st.markdown('<div class="section-box">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">🚫 중단 의심 — 4개월 이상 미입고</div>',
                    unsafe_allow_html=True)
        st.metric("중단 의심 품목 수", f"{len(disc_items)}개")
        if not disc_items.empty:
            st.dataframe(tbl_style(disc_items.style), use_container_width=True, height=400)
        else:
            st.info("중단 의심 품목이 없습니다.")
        st.markdown('</div>', unsafe_allow_html=True)
