"""
AccounTech — Free Cloud Accounting (Tally Replacement)
Streamlit Cloud deployment
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, date
import calendar
from database import init_db, get_company, get_ledger_summary, get_transactions, get_accounts

st.set_page_config(
    page_title="AccounTech",
    page_icon="📒",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── INIT ──────────────────────────────────────────────────────────────────────
init_db()

# ── STYLES ────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
.stApp { background: #f8fafc; }
[data-testid="stSidebar"] { background: #0f172a !important; }
[data-testid="stSidebar"] * { color: #cbd5e1 !important; }
[data-testid="stSidebar"] .stSelectbox label { color: #94a3b8 !important; }

.metric-card {
    background: white;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 20px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}
.metric-label { font-size: 12px; color: #64748b; font-weight: 500; text-transform: uppercase; letter-spacing: 0.5px; }
.metric-value { font-size: 26px; font-weight: 700; font-family: 'JetBrains Mono'; margin-top: 4px; }
.metric-green { color: #16a34a; }
.metric-red   { color: #dc2626; }
.metric-blue  { color: #2563eb; }
.metric-amber { color: #d97706; }

.section-header {
    font-size: 18px; font-weight: 700; color: #0f172a;
    border-bottom: 2px solid #3b82f6;
    padding-bottom: 8px; margin-bottom: 16px;
    display: inline-block;
}
.party-chip {
    display: inline-block; padding: 2px 10px;
    background: #eff6ff; color: #1d4ed8;
    border-radius: 20px; font-size: 12px; font-weight: 500;
}
div[data-testid="stMetricValue"] > div { font-family: 'JetBrains Mono' !important; }
.stDataFrame { border-radius: 8px; overflow: hidden; }
</style>
""", unsafe_allow_html=True)

# ── SIDEBAR ───────────────────────────────────────────────────────────────────
company = get_company()

with st.sidebar:
    st.markdown(f"""
    <div style='padding:16px 0 8px'>
      <div style='color:#38bdf8;font-size:20px;font-weight:700;font-family:monospace'>📒 AccounTech</div>
      <div style='color:#64748b;font-size:12px;margin-top:2px'>{company.get('name','My Business')}</div>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    # Financial year selector
    current_year = datetime.today().year
    fy_options = [f"FY {y}-{str(y+1)[2:]}" for y in range(2022, current_year+2)]
    default_fy = f"FY {current_year}-{str(current_year+1)[2:]}" if datetime.today().month >= 4 else f"FY {current_year-1}-{str(current_year)[2:]}"
    selected_fy = st.selectbox("Financial Year", fy_options,
                                index=fy_options.index(default_fy) if default_fy in fy_options else 0)
    fy_year = int(selected_fy.split(" ")[1].split("-")[0])
    FY_START = date(fy_year, 4, 1)
    FY_END   = date(fy_year+1, 3, 31)
    st.session_state["fy_start"] = str(FY_START)
    st.session_state["fy_end"]   = str(FY_END)

    # Month filter
    months = ["All Months"] + [calendar.month_name[m] for m in range(1,13)]
    sel_month = st.selectbox("Month", months)
    if sel_month != "All Months":
        m_num = list(calendar.month_name).index(sel_month)
        m_year = fy_year if m_num >= 4 else fy_year+1
        _, last_day = calendar.monthrange(m_year, m_num)
        st.session_state["filter_start"] = str(date(m_year, m_num, 1))
        st.session_state["filter_end"]   = str(date(m_year, m_num, last_day))
    else:
        st.session_state["filter_start"] = str(FY_START)
        st.session_state["filter_end"]   = str(FY_END)

    st.divider()
    st.markdown("<div style='color:#94a3b8;font-size:11px;text-transform:uppercase;letter-spacing:1px;padding:4px 0'>Navigation</div>", unsafe_allow_html=True)

# ── DATE RANGE ────────────────────────────────────────────────────────────────
START = st.session_state.get("filter_start", str(FY_START))
END   = st.session_state.get("filter_end",   str(FY_END))

# ── MAIN DASHBOARD ────────────────────────────────────────────────────────────
st.markdown(f"<div class='section-header'>📊 Dashboard — {selected_fy} &nbsp; <span style='font-size:13px;color:#64748b;font-weight:400'>{START} to {END}</span></div>", unsafe_allow_html=True)

summary = get_ledger_summary(start=START, end=END)
txns    = get_transactions(start=START, end=END)

# KPIs
income   = sum(v["bal"] for v in summary.values() if v["type"]=="Income")
expenses = sum(v["bal"] for v in summary.values() if v["type"]=="Expense")
profit   = income - expenses
bank_bal = summary.get("Bank",{}).get("bal",0)
recv     = summary.get("Accounts Receivable",{}).get("bal",0)
pay      = summary.get("Accounts Payable",{}).get("bal",0)
out_gst  = summary.get("Output CGST",{}).get("bal",0) + summary.get("Output SGST",{}).get("bal",0) + summary.get("Output IGST",{}).get("bal",0)
in_gst   = summary.get("Input CGST",{}).get("bal",0)  + summary.get("Input SGST",{}).get("bal",0)  + summary.get("Input IGST",{}).get("bal",0)
net_gst  = out_gst - in_gst

c1,c2,c3,c4 = st.columns(4)
def kpi(col, label, value, color, prefix="₹"):
    col.markdown(f"""
    <div class='metric-card'>
      <div class='metric-label'>{label}</div>
      <div class='metric-value {color}'>{prefix}{abs(value):,.2f}</div>
    </div>""", unsafe_allow_html=True)

kpi(c1, "💰 Total Revenue",    income,   "metric-blue")
kpi(c2, "📈 Net Profit",       profit,   "metric-green" if profit>=0 else "metric-red")
kpi(c3, "💸 Total Expenses",   expenses, "metric-red")
kpi(c4, "🧾 Net GST Payable",  net_gst,  "metric-amber")

st.markdown("<br>", unsafe_allow_html=True)
c5,c6,c7,c8 = st.columns(4)
kpi(c5, "🏦 Bank Balance",    bank_bal, "metric-blue")
kpi(c6, "📬 Receivables",     recv,     "metric-green")
kpi(c7, "📤 Payables",        pay,      "metric-red")
kpi(c8, "🔢 Transactions",    len(txns),"metric-blue", prefix="")

st.markdown("<br>", unsafe_allow_html=True)

# ── CHARTS ────────────────────────────────────────────────────────────────────
if txns:
    df_txn = pd.DataFrame(txns)
    df_txn["date"] = pd.to_datetime(df_txn["date"])
    df_txn["month"] = df_txn["date"].dt.to_period("M").astype(str)

    col_chart1, col_chart2 = st.columns(2)

    with col_chart1:
        st.markdown("**📊 Monthly Income vs Expenses**")
        income_acc = [k for k,v in summary.items() if v["type"]=="Income"]
        expense_acc= [k for k,v in summary.items() if v["type"]=="Expense"]

        monthly_in  = df_txn[df_txn["account_cr"].isin(income_acc)].groupby("month")["amount"].sum()
        monthly_exp = df_txn[df_txn["account_dr"].isin(expense_acc)].groupby("month")["amount"].sum()

        all_months = sorted(set(list(monthly_in.index) + list(monthly_exp.index)))
        fig = go.Figure()
        fig.add_trace(go.Bar(x=all_months, y=[monthly_in.get(m,0) for m in all_months],
                             name="Income", marker_color="#3b82f6"))
        fig.add_trace(go.Bar(x=all_months, y=[monthly_exp.get(m,0) for m in all_months],
                             name="Expenses", marker_color="#ef4444"))
        fig.update_layout(barmode="group", height=300, margin=dict(t=10,b=10),
                          paper_bgcolor="white", plot_bgcolor="white",
                          legend=dict(orientation="h", yanchor="bottom", y=1.02))
        st.plotly_chart(fig, use_container_width=True)

    with col_chart2:
        st.markdown("**🥧 Expense Breakdown**")
        exp_data = {k: v["bal"] for k,v in summary.items() if v["type"]=="Expense" and v["bal"]>0}
        if exp_data:
            fig2 = px.pie(values=list(exp_data.values()), names=list(exp_data.keys()),
                          color_discrete_sequence=px.colors.qualitative.Set3, hole=0.4)
            fig2.update_layout(height=300, margin=dict(t=10,b=10), paper_bgcolor="white",
                               showlegend=True, legend=dict(font=dict(size=11)))
            st.plotly_chart(fig2, use_container_width=True)

    col_chart3, col_chart4 = st.columns(2)

    with col_chart3:
        st.markdown("**📈 Cumulative Profit Trend**")
        df_sorted = df_txn.sort_values("date")
        inc_set  = set(income_acc)
        exp_set  = set(expense_acc)
        df_sorted["profit_delta"] = df_sorted.apply(
            lambda r: r["amount"] if r["account_cr"] in inc_set
                     else (-r["amount"] if r["account_dr"] in exp_set else 0), axis=1)
        df_sorted["cumulative_profit"] = df_sorted["profit_delta"].cumsum()
        fig3 = go.Figure()
        fig3.add_trace(go.Scatter(x=df_sorted["date"], y=df_sorted["cumulative_profit"],
                                   mode="lines", fill="tozeroy",
                                   line=dict(color="#3b82f6", width=2),
                                   fillcolor="rgba(59,130,246,0.1)"))
        fig3.update_layout(height=280, margin=dict(t=10,b=10),
                           paper_bgcolor="white", plot_bgcolor="white",
                           yaxis=dict(gridcolor="#f1f5f9"))
        st.plotly_chart(fig3, use_container_width=True)

    with col_chart4:
        st.markdown("**💳 Cash Flow — Money In vs Out**")
        bank_in  = df_txn[df_txn["account_dr"]=="Bank"].groupby("month")["amount"].sum()
        bank_out = df_txn[df_txn["account_cr"]=="Bank"].groupby("month")["amount"].sum()
        all_m = sorted(set(list(bank_in.index)+list(bank_out.index)))
        fig4 = go.Figure()
        fig4.add_trace(go.Bar(x=all_m, y=[bank_in.get(m,0) for m in all_m],
                               name="Money In", marker_color="#22c55e"))
        fig4.add_trace(go.Bar(x=all_m, y=[-bank_out.get(m,0) for m in all_m],
                               name="Money Out", marker_color="#f97316"))
        fig4.update_layout(barmode="overlay", height=280, margin=dict(t=10,b=10),
                           paper_bgcolor="white", plot_bgcolor="white",
                           legend=dict(orientation="h", yanchor="bottom", y=1.02))
        st.plotly_chart(fig4, use_container_width=True)

# ── RECENT TRANSACTIONS ───────────────────────────────────────────────────────
st.markdown("<br>", unsafe_allow_html=True)
st.markdown("**🕐 Recent Transactions**")
if txns:
    recent = pd.DataFrame(txns[-20:][::-1])
    display_cols = ["date","voucher_type","party","description","account_dr","account_cr","amount","total"]
    available = [c for c in display_cols if c in recent.columns]
    st.dataframe(
        recent[available].rename(columns={
            "date":"Date","voucher_type":"Type","party":"Party",
            "description":"Description","account_dr":"Dr Account",
            "account_cr":"Cr Account","amount":"Amount","total":"Total"
        }),
        use_container_width=True, hide_index=True, height=300
    )
else:
    st.info("No transactions yet. Go to **📤 Upload Data** or **✏️ Entries** to add data.")

st.divider()
st.markdown(f"<div style='text-align:center;color:#94a3b8;font-size:12px'>AccounTech · {company.get('name','')} · {company.get('gstin','GSTIN not set')}</div>", unsafe_allow_html=True)
