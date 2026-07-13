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
/* 전체 폰트 */
html, body, [class*="css"] { font-family: 'Pretendard', 'Apple SD Gothic Neo', sans-serif; }

/* 사이드바 */
section[data-testid="stSidebar"] { background: #1e2130; }
section[data-testid="stSidebar"] * { color: #e0e4ef !important; }
section[data-testid="stSidebar"] .stRadio label { color: #e0e4ef !important; }

/* KPI 카드 */
div[data-testid="metric-container"] {
    background: #ffffff;
    border: 1px solid #e8eaf0;
    border-radius: 12px;
    padding: 16px 20px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}
div[data-testid="metric-container"] label {
    font-size: 13px !important;
    color: #6b7280 !important;
    font-weight: 500 !important;
}
div[data-testid="metric-container"] [data-testid="stMetricValue"] {
    font-size: 22px !important;
    font-weight: 700 !important;
    color: #111827 !important;
}

/* 데이터프레임 폰트 */
.stDataFrame iframe { min-height: 200px; }
div[data-testid="stDataFrame"] * { font-size: 13.5px !important; }
div[data-testid="stDataFrame"] th {
    background: #f3f4f6 !important;
    font-weight: 600 !important;
    color: #374151 !important;
}

/* 탭 */
button[data-baseweb="tab"] {
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
    font-size: 15px;
    font-weight: 700;
    color: #374151;
    margin-bottom: 10px;
    border-left: 4px solid #4E79A7;
    padding-left: 10px;
}
.highlight-box {
    background: #f0f4ff;
    border: 1px solid #c7d2fe;
    border-radius: 10px;
    padding: 14px 18px;
    margin-bottom: 12px;
}

/* 경고/성공 메시지 */
div[data-testid="stAlert"] { border-radius: 10px; }
</style>
""", unsafe_allow_html=True)

# ── Plotly 공통 설정 ────────────────────────────────────────────
COLORS = ["#4E79A7", "#E15759", "#76B7B2", "#59A14F",
          "#EDC948", "#B07AA1", "#FF9DA7", "#9C755F",
          "#BAB0AC", "#F28E2B", "#499894", "#D37295"]
COLOR_MAP   = {"일본": "#4E79A7", "영국": "#E15759"}

def base_layout(height=400):
    return dict(
        height=height,
        paper_bgcolor="white",
        plot_bgcolor="white",
        font=dict(family="Apple SD Gothic Neo, sans-serif", size=13, color="#374151"),
        xaxis=dict(showgrid=False, tickangle=-40, tickfont=dict(size=12)),
        yaxis=dict(gridcolor="#f0f0f0", gridwidth=1, tickfont=dict(size=12)),
        legend=dict(bgcolor="rgba(255,255,255,0.9)", bordercolor="#e5e7eb",
                    borderwidth=1, font=dict(size=12)),
        margin=dict(l=60, r=40, t=50, b=60),
        hovermode="x unified",
    )

def apply_base(fig, height=400, yformat=","):
    fig.update_layout(**base_layout(height))
    fig.update_yaxes(tickformat=yformat)
    return fig

# ── 사이드바 ────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📦 수입단가 대시보드")
    st.markdown("---")
    uploaded = st.file_uploader("Excel 파일 업로드", type=["xlsx","xls"],
                                help="'입고현황' 시트가 포함된 파일")
    if uploaded:
        st.markdown("### 전역 필터")
        global_unit = st.radio("📐 단위", ["EA (완제품)", "G (원자재)"], index=0)
        global_country = st.multiselect("🌏 국가", ["일본","영국"],
                                        default=["일본","영국"])
        st.markdown("---")
        threshold = st.slider("⚠️ 단가 이상 감지 기준 (%)", 1, 50, 10)

if not uploaded:
    st.markdown("""
    <div style='text-align:center; padding: 80px 0;'>
        <h1>📦 수입단가 현황 대시보드</h1>
        <p style='color:#6b7280; font-size:16px;'>
            왼쪽 사이드바에서 Excel 파일을 업로드하면 대시보드가 생성됩니다.
        </p>
    </div>
    """, unsafe_allow_html=True)
    st.stop()


# ── 데이터 로드 ─────────────────────────────────────────────────
@st.cache_data(show_spinner="📂 데이터 불러오는 중...")
def load_data(file_bytes: bytes) -> pd.DataFrame:
    df = pd.read_excel(io.BytesIO(file_bytes), sheet_name="입고현황",
                       usecols="A:O", header=0, engine="openpyxl")
    df.columns = ["입고일자","입고번호","거래처","거래구분","환종","담당자",
                  "No","품번","품명","규격","단위","입고수량","외화단가","외화금액","해당월"]
    df = df.dropna(subset=["해당월","품명"])
    df["연월"] = (df["해당월"].astype(str).str.strip()
                 .str[:7].str.replace("-", "/", regex=False))
    df["단위_정규"] = df["단위"].apply(
        lambda u: "G" if pd.notna(u) and str(u).strip().upper()=="G"
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

# ── KPI 카드 ────────────────────────────────────────────────────
st.markdown(f"# 📦 수입단가 현황 대시보드")
st.markdown(f"<p style='color:#6b7280;margin-top:-10px'>단위: <b>{sel_unit}</b> &nbsp;|&nbsp; 국가: <b>{', '.join(global_country)}</b> &nbsp;|&nbsp; 기간: <b>{all_months[0]} ~ {all_months[-1]}</b></p>", unsafe_allow_html=True)

if df.empty:
    st.warning("선택한 필터 조건에 해당하는 데이터가 없습니다.")
    st.stop()

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("📅 기간", f"{all_months[0]} ~ {all_months[-1]}")
k2.metric("📋 총 입고 건수", f"{len(df):,}건")
k3.metric("🏷️ 품목 수", f"{df['품명'].nunique():,}개")
k4.metric("📁 품목군 수", f"{df['품목군'].nunique()}개")
k5.metric("🏭 공급처 수", f"{df['거래처'].nunique()}개")
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
    col_ctrl, col_chart = st.columns([1, 4])
    with col_ctrl:
        st.markdown('<div class="section-box">', unsafe_allow_html=True)
        st.markdown("**필터**")
        top_n  = st.slider("상위 품목군", 3, 30, 20, key="n1")
        metric1 = st.radio("기준", ["수량","금액"], key="m1")
        st.markdown('</div>', unsafe_allow_html=True)

    val_col   = "입고수량" if metric1=="수량" else "외화금액"
    top_g     = df.groupby("품목군")[val_col].sum().nlargest(top_n).index.tolist()
    monthly   = (df[df["품목군"].isin(top_g)]
                 .groupby(["연월","품목군"])[val_col].sum().reset_index())

    with col_chart:
        fig1 = px.line(monthly, x="연월", y=val_col, color="품목군",
                       markers=True, color_discrete_sequence=COLORS,
                       labels={"연월":"","품목군":"품목군", val_col: UNIT_LABEL if metric1=="수량" else "외화금액"})
        fig1.update_traces(line=dict(width=2.5), marker=dict(size=5))
        apply_base(fig1, height=430)
        fig1.update_layout(title=dict(text=f"품목군별 월별 {UNIT_LABEL if metric1=='수량' else '외화금액'} 추이 (상위 {top_n}개)",
                                      font=dict(size=15, color="#111827")))
        st.plotly_chart(fig1, use_container_width=True)

    # 연도 소계 테이블
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
    st.dataframe(
        tbl1.style.format({c: "{:,.0f}" for c in num_cols1+["합계"]})
            .set_properties(**{"font-size":"13px"})
            .set_table_styles([{"selector":"th","props":[("font-size","13px"),("font-weight","bold"),("background-color","#f3f4f6")]}]),
        use_container_width=True, height=520,
    )
    st.markdown('</div>', unsafe_allow_html=True)


# ════════════════════════════════════════════════
# TAB 2: 품목별 입고수량
# ════════════════════════════════════════════════
with tab2:
    # 필터 박스
    st.markdown('<div class="section-box">', unsafe_allow_html=True)
    st.markdown("**필터**")
    f1, f2, f3 = st.columns(3)
    with f1:
        group2 = st.selectbox("품목군", ["(전체)"]+sorted(df["품목군"].unique()), key="g2")
    with f2:
        # 품목군 선택 시 해당 품목만 표시
        if group2 != "(전체)":
            avail_items = sorted(df[df["품목군"]==group2]["품명"].unique())
        else:
            avail_items = sorted(df["품명"].unique())
        sel_items = st.multiselect("품목 선택 (미선택=전체)", avail_items, key="items2")
    with f3:
        keyword2 = st.text_input("품명 검색", key="kw2", placeholder="예: SOAP")
    st.markdown('</div>', unsafe_allow_html=True)

    df2 = df.copy()
    if group2 != "(전체)":
        df2 = df2[df2["품목군"]==group2]
    if sel_items:
        df2 = df2[df2["품명"].isin(sel_items)]
    if keyword2:
        df2 = df2[df2["품명"].str.contains(keyword2, case=False, na=False)]

    if df2.empty:
        st.warning("해당 조건에 데이터가 없습니다.")
    else:
        top15 = df2.groupby("품명")["입고수량"].sum().nlargest(15).index.tolist()
        chart2 = (df2[df2["품명"].isin(top15)]
                  .groupby(["품명","연월"])["입고수량"].sum().reset_index())

        title2 = group2 if group2!="(전체)" else "전체"
        fig2 = px.line(chart2, x="연월", y="입고수량", color="품명",
                       markers=True, color_discrete_sequence=COLORS,
                       labels={"연월":"","입고수량":UNIT_LABEL,"품명":"품명"})
        fig2.update_traces(line=dict(width=2.5), marker=dict(size=5))
        apply_base(fig2, height=430)
        fig2.update_layout(title=dict(text=f"[{title2}] 품목별 월별 입고수량 (상위 15개)",
                                      font=dict(size=15,color="#111827")))
        st.plotly_chart(fig2, use_container_width=True)

        # 품목별 합계 테이블
        st.markdown('<div class="section-box">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">품목별 합계</div>', unsafe_allow_html=True)
        tbl2 = (df2.groupby(["품목군","품명"])
                .agg(총수량=("입고수량","sum"), 평균단가=("외화단가","mean"), 입고횟수=("입고수량","count"))
                .reset_index().sort_values("총수량", ascending=False).reset_index(drop=True))
        tbl2.index = tbl2.index + 1
        st.dataframe(
            tbl2.style.format({"총수량":"{:,.0f}","평균단가":"{:,.1f}","입고횟수":"{:,.0f}"})
                .set_properties(**{"font-size":"13px"}),
            use_container_width=True, height=400,
        )
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
    if groups3:
        df3 = df3[df3["품목군"].isin(groups3)]

    if df3.empty:
        with f1:
            st.warning("해당 조건에 데이터가 없습니다.")
    else:
        pm = (df3.groupby(["품명","국가","환종","연월"])["외화단가"]
              .mean().reset_index().sort_values(["품명","연월"]))
        pm["이전단가"] = pm.groupby(["품명","환종"])["외화단가"].shift(1)
        pm["변동률"]   = ((pm["외화단가"]-pm["이전단가"])/pm["이전단가"]*100).round(1)

        anom = (pm[(pm["변동률"].abs()>threshold) & (pm["이전단가"]>0)]
                .dropna(subset=["변동률"])
                .sort_values("변동률", key=abs, ascending=False))

        with f1:
            if anom.empty:
                st.success(f"✅ ±{threshold}% 이상 변동 품목이 없습니다.")
            else:
                m1, m2, m3 = st.columns(3)
                m1.metric("이상 감지", f"{len(anom)}건")
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

                styled3 = (disp.style
                    .format({"이전단가":"{:,.1f}","현재단가":"{:,.1f}","변동률(%)":"{:+.1f}%"})
                    .map(color_pct, subset=["변동률(%)"])
                    .set_properties(**{"font-size":"13px"}))
                st.dataframe(styled3, use_container_width=True, height=420)

        # 이상 상위 품목 단가 추이
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
                                   labels={"연월":"","외화단가":"외화단가","품명":"품명"},
                                   title=f"{country}")
                    fig3.update_traces(line=dict(width=2.5), marker=dict(size=5))
                    apply_base(fig3, height=320)
                    st.plotly_chart(fig3, use_container_width=True)


# ════════════════════════════════════════════════
# TAB 4: 국가별 추이
# ════════════════════════════════════════════════
with tab4:
    mc4 = (df.groupby(["연월","국가"])
           .agg(수량=("입고수량","sum"), 금액=("외화금액","sum"))
           .reset_index())

    col1, col2 = st.columns(2)
    with col1:
        fig4a = px.line(mc4, x="연월", y="수량", color="국가",
                        color_discrete_map=COLOR_MAP, markers=True,
                        labels={"연월":"","수량":UNIT_LABEL,"국가":"국가"})
        fig4a.update_traces(line=dict(width=2.5), marker=dict(size=5))
        apply_base(fig4a, height=360)
        fig4a.update_layout(title=dict(text=f"월별 입고수량 ({sel_unit})",font=dict(size=15,color="#111827")))
        st.plotly_chart(fig4a, use_container_width=True)

    with col2:
        fig4b = px.line(mc4, x="연월", y="금액", color="국가",
                        color_discrete_map=COLOR_MAP, markers=True,
                        labels={"연월":"","금액":"외화금액","국가":"국가"})
        fig4b.update_traces(line=dict(width=2.5), marker=dict(size=5))
        apply_base(fig4b, height=360)
        fig4b.update_layout(title=dict(text="월별 외화금액",font=dict(size=15,color="#111827")))
        st.plotly_chart(fig4b, use_container_width=True)

    # YoY
    if len(all_months) >= 13:
        yoy_frames = []
        for country in global_country:
            cdf = mc4[mc4["국가"]==country].copy().sort_values("연월")
            cdf["YoY(%)"] = (cdf["수량"].pct_change(12)*100).round(1)
            yoy_frames.append(cdf)
        yoy_all = pd.concat(yoy_frames).dropna(subset=["YoY(%)"])
        if not yoy_all.empty:
            fig4c = px.bar(yoy_all, x="연월", y="YoY(%)", color="국가",
                           color_discrete_map=COLOR_MAP, barmode="group",
                           labels={"연월":"","YoY(%)":"YoY (%)"})
            fig4c.add_hline(y=0, line_dash="dash", line_color="#9ca3af", line_width=1.5)
            apply_base(fig4c, height=300)
            fig4c.update_layout(title=dict(text="수량 전년 동월 대비 (%)",font=dict(size=15,color="#111827")))
            st.plotly_chart(fig4c, use_container_width=True)

    # 국가별 월별 테이블
    st.markdown('<div class="section-box">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">국가별 월별 수량 상세</div>', unsafe_allow_html=True)
    tbl4 = mc4.pivot(index="연월", columns="국가", values="수량").fillna(0)
    tbl4.columns.name = None
    tbl4["합계"] = tbl4.sum(axis=1)
    num_cols4 = list(tbl4.columns)
    st.dataframe(
        tbl4.style.format("{:,.0f}", subset=num_cols4)
            .set_properties(**{"font-size":"13px"}),
        use_container_width=True, height=340,
    )
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

    new_items  = item5[item5["첫입고월"]>=recent_cut].sort_values("첫입고월", ascending=False).reset_index(drop=True)
    disc_items = item5[item5["마지막입고월"]<=disc_cut].sort_values("마지막입고월", ascending=False).reset_index(drop=True)
    new_items.index  = new_items.index + 1
    disc_items.index = disc_items.index + 1

    c1, c2 = st.columns(2)
    with c1:
        st.markdown('<div class="section-box">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">🆕 신규 품목 — 최근 3개월 내 첫 입고</div>', unsafe_allow_html=True)
        st.metric("신규 품목 수", f"{len(new_items)}개")
        if not new_items.empty:
            st.dataframe(new_items.style.set_properties(**{"font-size":"13px"}),
                         use_container_width=True, height=420)
        else:
            st.info("신규 품목이 없습니다.")
        st.markdown('</div>', unsafe_allow_html=True)

    with c2:
        st.markdown('<div class="section-box">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">🚫 중단 의심 — 4개월 이상 미입고</div>', unsafe_allow_html=True)
        st.metric("중단 의심 품목 수", f"{len(disc_items)}개")
        if not disc_items.empty:
            st.dataframe(disc_items.style.set_properties(**{"font-size":"13px"}),
                         use_container_width=True, height=420)
        else:
            st.info("중단 의심 품목이 없습니다.")
        st.markdown('</div>', unsafe_allow_html=True)
