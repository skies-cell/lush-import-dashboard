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
/* Noto Sans KR 폰트 로드 */
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;600;700&display=swap');

html, body, [class*="css"], .stMarkdown, .stText, button, input, select, textarea {
    font-family: 'Noto Sans KR', sans-serif !important;
}

/* 사이드바 */
section[data-testid="stSidebar"] { background: #1e2130 !important; }
section[data-testid="stSidebar"] * { color: #e0e4ef !important; font-family: 'Noto Sans KR', sans-serif !important; }

/* KPI 카드 — 박스 넘침 방지 */
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
}
div[data-testid="metric-container"] [data-testid="stMetricValue"] {
    font-size: 18px !important;
    font-weight: 700 !important;
    color: #111827 !important;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

/* 데이터프레임 */
div[data-testid="stDataFrame"] * {
    font-family: 'Noto Sans KR', sans-serif !important;
    font-size: 14.5px !important;
}
div[data-testid="stDataFrame"] th {
    font-size: 14px !important;
    font-weight: 700 !important;
    background: #f0f4ff !important;
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
    border-radius: 14px;
    padding: 20px 24px;
    margin-bottom: 16px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.05);
}
.section-title {
    font-family: 'Noto Sans KR', sans-serif;
    font-size: 15px;
    font-weight: 700;
    color: #1e3a5f;
    margin-bottom: 12px;
    border-left: 4px solid #4E79A7;
    padding-left: 10px;
}
</style>
""", unsafe_allow_html=True)

# ── Plotly 공통 ────────────────────────────────────────────────
COLORS = ["#4E79A7","#E15759","#76B7B2","#59A14F",
          "#EDC948","#B07AA1","#FF9DA7","#9C755F",
          "#F28E2B","#499894","#D37295","#BAB0AC"]
COLOR_MAP = {"일본":"#4E79A7","영국":"#E15759"}
FONT_CFG  = dict(family="Noto Sans KR, sans-serif", size=13, color="#374151")

def apply_base(fig, height=420, yformat=","):
    fig.update_layout(
        height=height,
        paper_bgcolor="white", plot_bgcolor="white",
        font=FONT_CFG,
        xaxis=dict(showgrid=False, tickangle=-40, tickfont=dict(size=12)),
        yaxis=dict(gridcolor="#f0f0f0", gridwidth=1, tickfont=dict(size=12), tickformat=yformat),
        legend=dict(bgcolor="rgba(255,255,255,0.9)", bordercolor="#e5e7eb",
                    borderwidth=1, font=dict(size=12)),
        margin=dict(l=60, r=40, t=50, b=60),
        hovermode="x unified",
        title_font=dict(size=15, color="#111827", family="Noto Sans KR, sans-serif"),
    )
    return fig

# ── 사이드바 ───────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📦 수입단가 대시보드")
    st.markdown("---")
    uploaded = st.file_uploader("Excel 파일 업로드", type=["xlsx","xls"],
                                help="'입고현황' 시트가 포함된 파일")
    if uploaded:
        st.markdown("### 전역 필터")
        global_unit    = st.radio("📐 단위", ["EA (완제품)","G (원자재)"], index=0)
        global_country = st.multiselect("🌏 국가", ["일본","영국"], default=["일본","영국"])
        st.markdown("---")
        threshold = st.slider("⚠️ 단가 이상 감지 기준 (%)", 1, 50, 10)

if not uploaded:
    st.markdown("""
    <div style='text-align:center;padding:80px 0;font-family:Noto Sans KR,sans-serif'>
        <h1>📦 수입단가 현황 대시보드</h1>
        <p style='color:#6b7280;font-size:16px'>왼쪽 사이드바에서 Excel 파일을 업로드하면 대시보드가 생성됩니다.</p>
    </div>""", unsafe_allow_html=True)
    st.stop()


# ── 데이터 로드 ────────────────────────────────────────────────
@st.cache_data(show_spinner="📂 데이터 불러오는 중...")
def load_data(file_bytes: bytes) -> pd.DataFrame:
    df = pd.read_excel(io.BytesIO(file_bytes), sheet_name="입고현황",
                       usecols="A:O", header=0, engine="openpyxl")
    df.columns = ["입고일자","입고번호","거래처","거래구분","환종","담당자",
                  "No","품번","품명","규격","단위","입고수량","외화단가","외화금액","해당월"]
    df = df.dropna(subset=["해당월","품명"])
    df["연월"] = (df["해당월"].astype(str).str.strip()
                 .str[:7].str.replace("-","/",regex=False))
    df["단위_정규"] = df["단위"].apply(
        lambda u: "G"  if pd.notna(u) and str(u).strip().upper()=="G"
        else ("EA" if pd.notna(u) and str(u).strip().upper()=="EA" else "기타"))
    df["품목군"] = (df["품명"].str.extract(r"\(([^)]+)\)(?:\s*_\w+)?\s*$")
                  .iloc[:,0].str.upper().str.strip().fillna("기타"))
    df["국가"] = df["환종"].map({"JPY":"일본","GBP":"영국"}).fillna("기타")
    df = df[pd.to_numeric(df["입고수량"], errors="coerce") > 0].copy()
    for c in ["외화단가","외화금액","입고수량"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["외화단가","입고수량"])
    return df

df_raw = load_data(uploaded.read())
sel_unit    = "EA" if "EA" in global_unit else "G"
df = df_raw[(df_raw["단위_정규"]==sel_unit) &
            (df_raw["국가"].isin(global_country))].copy()
all_months  = sorted(df_raw["연월"].unique())
UNIT_LABEL  = "수량 (EA)" if sel_unit=="EA" else "중량 (G)"

# ── KPI 카드 ───────────────────────────────────────────────────
st.markdown("<h2 style='font-family:Noto Sans KR,sans-serif;margin-bottom:4px'>📦 수입단가 현황 대시보드</h2>", unsafe_allow_html=True)
st.markdown(f"<p style='color:#6b7280;font-family:Noto Sans KR,sans-serif;margin-top:0'>단위: <b>{sel_unit}</b> &nbsp;|&nbsp; 국가: <b>{', '.join(global_country)}</b></p>", unsafe_allow_html=True)

if df.empty:
    st.warning("선택한 필터 조건에 해당하는 데이터가 없습니다.")
    st.stop()

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("📅 기간", f"{all_months[0]} ~ {all_months[-1]}")
k2.metric("📋 총 입고건수", f"{len(df):,}건")
k3.metric("🏷️ 품목수", f"{df['품명'].nunique():,}개")
k4.metric("📁 품목군수", f"{df['품목군'].nunique()}개")
k5.metric("🏭 공급처수", f"{df['거래처'].nunique()}개")
st.markdown("<div style='margin:16px 0'></div>", unsafe_allow_html=True)

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
    col_ctrl, col_chart = st.columns([1, 5])
    with col_ctrl:
        st.markdown('<div class="section-box">', unsafe_allow_html=True)
        st.markdown("**필터**")
        top_n   = st.slider("상위 품목군", 3, 30, 20, key="n1")
        metric1 = st.radio("기준", ["수량","금액"], key="m1")
        st.markdown('</div>', unsafe_allow_html=True)

    val_col  = "입고수량" if metric1=="수량" else "외화금액"
    val_lbl  = UNIT_LABEL if metric1=="수량" else "외화금액"
    top_g    = df.groupby("품목군")[val_col].sum().nlargest(top_n).index.tolist()
    monthly  = (df[df["품목군"].isin(top_g)]
                .groupby(["연월","품목군"])[val_col].sum().reset_index())

    with col_chart:
        fig1 = px.line(monthly, x="연월", y=val_col, color="품목군",
                       markers=True, color_discrete_sequence=COLORS,
                       labels={"연월":"","품목군":"품목군", val_col: val_lbl})
        fig1.update_traces(line=dict(width=2.5), marker=dict(size=5))
        apply_base(fig1, height=520)          # ← 세로축 넓힘
        fig1.update_layout(
            title=f"품목군별 월별 {val_lbl} 추이 (상위 {top_n}개)",
            legend=dict(orientation="v", x=1.01, y=1,
                        font=dict(size=11), bgcolor="rgba(255,255,255,0.9)"),
            margin=dict(l=60, r=180, t=50, b=60),
        )
        st.plotly_chart(fig1, use_container_width=True)

    # 연도 소계 테이블 — 색상 히트맵
    st.markdown('<div class="section-box">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">품목군별 연도 소계</div>', unsafe_allow_html=True)
    df1y = df.copy()
    df1y["연도"] = df1y["연월"].str[:4].astype(int)
    tbl1 = (df1y[df1y["품목군"].isin(top_g)]
            .groupby(["품목군","연도"])[val_col].sum()
            .unstack(fill_value=0).reset_index())
    tbl1.columns.name = None
    num_cols1 = [c for c in tbl1.columns if isinstance(c, int)]
    tbl1["합계"] = tbl1[num_cols1].sum(axis=1)
    tbl1 = tbl1.sort_values("합계", ascending=False).reset_index(drop=True)
    tbl1.index = tbl1.index + 1
    styled1 = (tbl1.style
        .format({c: "{:,.0f}" for c in num_cols1+["합계"]})
        .background_gradient(subset=num_cols1+["합계"], cmap="Blues", low=0.05, high=0.8)
        .set_properties(**{"font-size":"14px", "text-align":"right"})
        .set_properties(subset=["품목군"], **{"text-align":"left"})
        .set_table_styles([{
            "selector":"th",
            "props":[("font-size","14px"),("font-weight","700"),
                     ("background-color","#e8f0fe"),("color","#1e3a5f"),
                     ("text-align","center")]
        }])
    )
    st.dataframe(styled1, use_container_width=True, height=540)
    st.markdown('</div>', unsafe_allow_html=True)


# ════════════════════════════════════════════════
# TAB 2: 품목별 입고수량
# ════════════════════════════════════════════════
with tab2:
    st.markdown('<div class="section-box">', unsafe_allow_html=True)
    st.markdown("**필터**")
    f1, f2, f3 = st.columns(3)
    with f1:
        group2 = st.selectbox("품목군", ["(전체)"]+sorted(df["품목군"].unique()), key="g2")
    with f2:
        avail_items = sorted(
            df[df["품목군"]==group2]["품명"].unique()
            if group2!="(전체)" else df["품명"].unique()
        )
        sel_items = st.multiselect("품목 선택 (미선택=전체)", avail_items, key="items2")
    with f3:
        keyword2 = st.text_input("품명 검색", key="kw2", placeholder="예: SOAP")
    st.markdown('</div>', unsafe_allow_html=True)

    df2 = df.copy()
    if group2!="(전체)": df2 = df2[df2["품목군"]==group2]
    if sel_items:        df2 = df2[df2["품명"].isin(sel_items)]
    if keyword2:         df2 = df2[df2["품명"].str.contains(keyword2, case=False, na=False)]

    if df2.empty:
        st.warning("해당 조건에 데이터가 없습니다.")
    else:
        top15  = df2.groupby("품명")["입고수량"].sum().nlargest(15).index.tolist()
        chart2 = (df2[df2["품명"].isin(top15)]
                  .groupby(["품명","연월"])["입고수량"].sum().reset_index())
        title2 = group2 if group2!="(전체)" else "전체"
        fig2 = px.line(chart2, x="연월", y="입고수량", color="품명",
                       markers=True, color_discrete_sequence=COLORS,
                       labels={"연월":"","입고수량":UNIT_LABEL,"품명":"품명"})
        fig2.update_traces(line=dict(width=2.5), marker=dict(size=5))
        apply_base(fig2, height=450)
        fig2.update_layout(
            title=f"[{title2}] 품목별 월별 입고수량 (상위 15개)",
            legend=dict(orientation="v", x=1.01, y=1, font=dict(size=11)),
            margin=dict(l=60, r=180, t=50, b=60),
        )
        st.plotly_chart(fig2, use_container_width=True)

        st.markdown('<div class="section-box">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">품목별 합계</div>', unsafe_allow_html=True)
        tbl2 = (df2.groupby(["품목군","품명"])
                .agg(총수량=("입고수량","sum"), 평균단가=("외화단가","mean"), 입고횟수=("입고수량","count"))
                .reset_index().sort_values("총수량", ascending=False).reset_index(drop=True))
        tbl2.index = tbl2.index + 1
        styled2 = (tbl2.style
            .format({"총수량":"{:,.0f}","평균단가":"{:,.1f}","입고횟수":"{:,.0f}"})
            .background_gradient(subset=["총수량"], cmap="Blues", low=0.05, high=0.8)
            .set_properties(**{"font-size":"14px"})
            .set_table_styles([{"selector":"th","props":[
                ("font-size","14px"),("font-weight","700"),
                ("background-color","#e8f0fe"),("color","#1e3a5f")]}])
        )
        st.dataframe(styled2, use_container_width=True, height=400)
        st.markdown('</div>', unsafe_allow_html=True)


# ════════════════════════════════════════════════
# TAB 3: 단가 이상 감지
# ════════════════════════════════════════════════
with tab3:
    f1, f2 = st.columns([3,1])
    with f2:
        st.markdown('<div class="section-box">', unsafe_allow_html=True)
        st.markdown("**필터**")
        countries3 = st.multiselect("국가", global_country, default=global_country, key="c3")
        groups3    = st.multiselect("품목군 (미선택=전체)", sorted(df["품목군"].unique()), key="g3")
        st.markdown('</div>', unsafe_allow_html=True)

    df3 = df[df["국가"].isin(countries3)]
    if groups3: df3 = df3[df3["품목군"].isin(groups3)]

    if df3.empty:
        with f1: st.warning("해당 조건에 데이터가 없습니다.")
    else:
        pm = (df3.groupby(["품명","국가","환종","연월"])["외화단가"]
              .mean().reset_index().sort_values(["품명","연월"]))
        pm["이전단가"] = pm.groupby(["품명","환종"])["외화단가"].shift(1)
        pm["변동률"]   = ((pm["외화단가"]-pm["이전단가"])/pm["이전단가"]*100).round(1)
        anom = (pm[(pm["변동률"].abs()>threshold)&(pm["이전단가"]>0)]
                .dropna(subset=["변동률"])
                .sort_values("변동률", key=abs, ascending=False))

        with f1:
            if anom.empty:
                st.success(f"✅ ±{threshold}% 이상 변동 품목이 없습니다.")
            else:
                m1,m2,m3 = st.columns(3)
                m1.metric("이상 감지",  f"{len(anom)}건")
                m2.metric("↑ 단가 상승", f"{(anom['변동률']>0).sum()}건")
                m3.metric("↓ 단가 하락", f"{(anom['변동률']<0).sum()}건")
                st.markdown("<div style='margin:8px 0'></div>", unsafe_allow_html=True)

                disp = anom[["품명","국가","연월","이전단가","외화단가","변동률"]].copy()
                disp.columns = ["품명","국가","연월","이전단가","현재단가","변동률(%)"]
                disp = disp.reset_index(drop=True)
                disp.index = disp.index + 1

                def color_pct(v):
                    try:
                        v = float(v)
                        if v > 0: return "color:#E15759;font-weight:bold"
                        if v < 0: return "color:#4E79A7;font-weight:bold"
                    except: pass
                    return ""

                try:    styled3 = disp.style.map(color_pct, subset=["변동률(%)"])
                except: styled3 = disp.style.applymap(color_pct, subset=["변동률(%)"])
                styled3 = (styled3
                    .format({"이전단가":"{:,.1f}","현재단가":"{:,.1f}","변동률(%)":"{:+.1f}%"})
                    .set_properties(**{"font-size":"14px"})
                    .set_table_styles([{"selector":"th","props":[
                        ("font-size","14px"),("font-weight","700"),
                        ("background-color","#e8f0fe"),("color","#1e3a5f")]}])
                )
                st.dataframe(styled3, use_container_width=True, height=420)

        if not anom.empty:
            top5 = anom["품명"].value_counts().head(5).index.tolist()
            pm_top = pm[pm["품명"].isin(top5)].dropna(subset=["외화단가"])
            if not pm_top.empty:
                st.divider()
                st.markdown('<div class="section-title">이상 변동 상위 5개 품목 단가 추이</div>',
                            unsafe_allow_html=True)
                for country in countries3:
                    pm_c = pm_top[pm_top["국가"]==country]
                    if pm_c.empty: continue
                    fig3 = px.line(pm_c, x="연월", y="외화단가", color="품명",
                                   markers=True, color_discrete_sequence=COLORS,
                                   labels={"연월":"","외화단가":"외화단가"},
                                   title=country)
                    fig3.update_traces(line=dict(width=2.5), marker=dict(size=5))
                    apply_base(fig3, height=320)
                    st.plotly_chart(fig3, use_container_width=True)


# ════════════════════════════════════════════════
# TAB 4: 국가별 추이 — 금액 기준, 국가별 분리
# ════════════════════════════════════════════════
with tab4:
    st.markdown("<div style='font-family:Noto Sans KR,sans-serif;color:#6b7280;font-size:13px;margin-bottom:8px'>💡 영국(GBP)·일본(JPY)은 환종이 달라 같은 축에 표시하지 않고 국가별로 분리합니다.</div>", unsafe_allow_html=True)

    # 국가별 월별 금액 집계
    mc4 = (df.groupby(["연월","국가"])
           .agg(금액=("외화금액","sum"), 수량=("입고수량","sum"))
           .reset_index())

    # 국가별 차트 — 좌우 분리
    cols4 = st.columns(len(global_country)) if global_country else [st.container()]
    for i, country in enumerate(global_country):
        cdf = mc4[mc4["국가"]==country]
        if cdf.empty: continue
        환종 = "JPY" if country=="일본" else "GBP"
        color = COLOR_MAP.get(country, "#4E79A7")
        with cols4[i]:
            fig4 = go.Figure()
            fig4.add_trace(go.Scatter(
                x=cdf["연월"], y=cdf["금액"],
                mode="lines+markers",
                name=f"{country} 입고금액",
                line=dict(color=color, width=2.5),
                marker=dict(size=6, color=color),
                fill="tozeroy",
                fillcolor="rgba(78,121,167,0.08)" if country=="일본" else "rgba(225,87,89,0.08)",
            ))
            apply_base(fig4, height=380)
            fig4.update_layout(
                title=f"{country} 월별 입고금액 ({환종})",
                hovermode="x",
                showlegend=False,
            )
            fig4.update_yaxes(tickformat=",")
            st.plotly_chart(fig4, use_container_width=True)

    # 입고금액 YoY (금액 기준)
    if len(all_months) >= 13:
        st.divider()
        st.markdown('<div class="section-title">입고금액 전년 동월 대비 (%)</div>',
                    unsafe_allow_html=True)
        yoy_frames = []
        for country in global_country:
            cdf = mc4[mc4["국가"]==country].copy().sort_values("연월")
            cdf["YoY(%)"] = (cdf["금액"].pct_change(12)*100).round(1)
            yoy_frames.append(cdf)
        yoy_all = pd.concat(yoy_frames).dropna(subset=["YoY(%)"])
        if not yoy_all.empty:
            fig4c = px.bar(yoy_all, x="연월", y="YoY(%)", color="국가",
                           color_discrete_map=COLOR_MAP, barmode="group",
                           labels={"연월":"","YoY(%)":"YoY (%)"})
            fig4c.add_hline(y=0, line_dash="dash", line_color="#9ca3af", line_width=1.5)
            apply_base(fig4c, height=300)
            fig4c.update_layout(title="입고금액 전년 동월 대비 (%)")
            st.plotly_chart(fig4c, use_container_width=True)

    # 국가별 월별 금액 테이블
    st.markdown('<div class="section-box">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">국가별 월별 입고금액 상세</div>', unsafe_allow_html=True)
    tbl4 = mc4.pivot(index="연월", columns="국가", values="금액").fillna(0)
    tbl4.columns.name = None
    tbl4["합계"] = tbl4.sum(axis=1)
    num_cols4 = list(tbl4.columns)

    # 행 색 교차
    def row_style(row):
        idx = row.name
        all_idx = list(tbl4.index)
        pos = all_idx.index(idx)
        bg = "#f8faff" if pos % 2 == 0 else "#ffffff"
        return [f"background-color:{bg}" for _ in row]

    styled4 = (tbl4.style
        .format("{:,.0f}", subset=num_cols4)
        .apply(row_style, axis=1)
        .background_gradient(subset=["합계"], cmap="Blues", low=0.1, high=0.7)
        .set_properties(**{"font-size":"14px", "text-align":"right"})
        .set_properties(subset=tbl4.index[:0], **{})
        .set_table_styles([{"selector":"th","props":[
            ("font-size","14px"),("font-weight","700"),
            ("background-color","#e8f0fe"),("color","#1e3a5f"),
            ("text-align","center")]}])
    )
    st.dataframe(styled4, use_container_width=True, height=400)
    st.markdown('</div>', unsafe_allow_html=True)


# ════════════════════════════════════════════════
# TAB 5: 신규 / 중단 품목
# ════════════════════════════════════════════════
with tab5:
    all_m5 = sorted(df["연월"].unique())
    if len(all_m5) < 2:
        st.warning("데이터가 부족합니다.")
        st.stop()

    item5 = (df.groupby(["품명","품목군","국가"])["연월"]
             .agg(첫입고월="min", 마지막입고월="max", 입고횟수="count")
             .reset_index())
    recent_cut = all_m5[-3] if len(all_m5)>=3 else all_m5[0]
    disc_cut   = all_m5[-4] if len(all_m5)>=4 else all_m5[0]

    new_items  = item5[item5["첫입고월"]>=recent_cut].sort_values("첫입고월",ascending=False).reset_index(drop=True)
    disc_items = item5[item5["마지막입고월"]<=disc_cut].sort_values("마지막입고월",ascending=False).reset_index(drop=True)
    new_items.index  = new_items.index + 1
    disc_items.index = disc_items.index + 1

    def style_tbl5(df_in):
        def zebra(row):
            all_idx = list(df_in.index)
            pos = all_idx.index(row.name)
            bg = "#f8faff" if pos%2==0 else "#ffffff"
            return [f"background-color:{bg}" for _ in row]
        return (df_in.style
            .apply(zebra, axis=1)
            .set_properties(**{"font-size":"14px"})
            .set_table_styles([{"selector":"th","props":[
                ("font-size","14px"),("font-weight","700"),
                ("background-color","#e8f0fe"),("color","#1e3a5f")]}])
        )

    c1, c2 = st.columns(2)
    with c1:
        st.markdown('<div class="section-box">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">🆕 신규 품목 — 최근 3개월 내 첫 입고</div>', unsafe_allow_html=True)
        st.metric("신규 품목 수", f"{len(new_items)}개")
        if not new_items.empty:
            st.dataframe(style_tbl5(new_items), use_container_width=True, height=420)
        else:
            st.info("신규 품목이 없습니다.")
        st.markdown('</div>', unsafe_allow_html=True)

    with c2:
        st.markdown('<div class="section-box">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">🚫 중단 의심 — 4개월 이상 미입고</div>', unsafe_allow_html=True)
        st.metric("중단 의심 품목 수", f"{len(disc_items)}개")
        if not disc_items.empty:
            st.dataframe(style_tbl5(disc_items), use_container_width=True, height=420)
        else:
            st.info("중단 의심 품목이 없습니다.")
        st.markdown('</div>', unsafe_allow_html=True)
