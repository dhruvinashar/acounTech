"""
Accounting Reports — P&L, Balance Sheet, Trial Balance, Ledger
"""
import streamlit as st
import pandas as pd
import io
from datetime import datetime, date
from database import init_db, get_ledger_summary, get_transactions, get_accounts

init_db()
st.markdown("## 📊 Accounting Reports")

START = st.session_state.get("filter_start", f"{datetime.today().year}-04-01")
END   = st.session_state.get("filter_end",   str(date.today()))
st.caption(f"Period: {START} to {END} — change in sidebar")

summary = get_ledger_summary(start=START, end=END)
accounts= get_accounts()
acc_map = {a["name"]: a for a in accounts}

def get_bal(acc_name): return summary.get(acc_name,{}).get("bal",0)

tab_pl, tab_bs, tab_tb, tab_ledger = st.tabs(["📈 Profit & Loss", "🏛️ Balance Sheet", "⚖️ Trial Balance", "📒 Account Ledger"])

# ── P&L ───────────────────────────────────────────────────────────────────────
with tab_pl:
    st.markdown("### Profit & Loss Statement")
    st.caption(f"For the period {START} to {END}")

    income_items  = {k:v for k,v in summary.items() if v["type"]=="Income"}
    expense_items = {k:v for k,v in summary.items() if v["type"]=="Expense"}
    total_income  = sum(v["bal"] for v in income_items.values())
    total_expense = sum(v["bal"] for v in expense_items.values())
    gross_profit  = total_income - sum(v["bal"] for k,v in expense_items.items() if v.get("group") in ("Direct Expense","Cost of Goods"))
    net_profit    = total_income - total_expense
    margin        = round(net_profit/total_income*100,1) if total_income else 0

    # KPIs
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Total Revenue",    f"₹{total_income:,.2f}")
    c2.metric("Total Expenses",   f"₹{total_expense:,.2f}")
    c3.metric("Net Profit/Loss",  f"₹{net_profit:,.2f}",
              delta=f"{margin}% margin", delta_color="normal" if net_profit>=0 else "inverse")
    c4.metric("Profit Margin",    f"{margin}%")

    col1,col2 = st.columns(2)

    with col1:
        st.markdown("#### 💰 Income")
        inc_rows = []
        for group in ["Direct Income","Indirect Income"]:
            items = [(k,v["bal"]) for k,v in income_items.items() if v.get("group")==group]
            if items:
                inc_rows.append({"Account":f"— {group} —","Amount (₹)":""})
                for name,bal in items:
                    inc_rows.append({"Account":f"  {name}","Amount (₹)":f"{bal:,.2f}"})
        inc_rows.append({"Account":"TOTAL INCOME","Amount (₹)":f"{total_income:,.2f}"})
        st.dataframe(pd.DataFrame(inc_rows), use_container_width=True, hide_index=True)

    with col2:
        st.markdown("#### 💸 Expenses")
        exp_rows = []
        for group in ["Direct Expense","Indirect Expense"]:
            items = [(k,v["bal"]) for k,v in expense_items.items() if v.get("group")==group]
            if items:
                exp_rows.append({"Account":f"— {group} —","Amount (₹)":""})
                for name,bal in items:
                    exp_rows.append({"Account":f"  {name}","Amount (₹)":f"{bal:,.2f}"})
        exp_rows.append({"Account":"TOTAL EXPENSES","Amount (₹)":f"{total_expense:,.2f}"})
        st.dataframe(pd.DataFrame(exp_rows), use_container_width=True, hide_index=True)

    # Net profit box
    profit_color = "🟢" if net_profit >= 0 else "🔴"
    label = "NET PROFIT" if net_profit >= 0 else "NET LOSS"
    st.markdown(f"""
    <div style='background:{"#f0fdf4" if net_profit>=0 else "#fef2f2"};
                border:2px solid {"#16a34a" if net_profit>=0 else "#dc2626"};
                border-radius:10px;padding:16px 24px;margin:12px 0;
                display:flex;justify-content:space-between;align-items:center'>
      <span style='font-size:18px;font-weight:700;color:{"#15803d" if net_profit>=0 else "#b91c1c"}'>{profit_color} {label}</span>
      <span style='font-size:24px;font-weight:700;font-family:monospace;color:{"#15803d" if net_profit>=0 else "#b91c1c"}'>₹{abs(net_profit):,.2f} ({margin}%)</span>
    </div>
    """, unsafe_allow_html=True)

    if st.button("📥 Download P&L Excel"):
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as w:
            pd.DataFrame(inc_rows + [{}] + exp_rows + [{"Account":label,"Amount (₹)":f"{abs(net_profit):,.2f}"}])\
              .to_excel(w, index=False, sheet_name="Profit & Loss")
        st.download_button("💾 ProfitLoss.xlsx", buf.getvalue(),
                           file_name=f"PL_{START[:7]}_{END[:7]}.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# ── BALANCE SHEET ─────────────────────────────────────────────────────────────
with tab_bs:
    st.markdown("### Balance Sheet")
    st.caption(f"As on {END}")

    total_income  = sum(v["bal"] for v in summary.values() if v["type"]=="Income")
    total_expense = sum(v["bal"] for v in summary.values() if v["type"]=="Expense")
    net_profit    = total_income - total_expense

    assets      = {k:v for k,v in summary.items() if v["type"]=="Asset"}
    liabilities = {k:v for k,v in summary.items() if v["type"]=="Liability"}
    equity      = {k:v for k,v in summary.items() if v["type"]=="Equity"}
    equity["Retained Earnings"] = {"bal":net_profit,"type":"Equity","group":"Reserves","dr":0,"cr":0}

    total_assets = sum(v["bal"] for v in assets.values())
    total_liab   = sum(v["bal"] for v in liabilities.values())
    total_equity = sum(v["bal"] for v in equity.values())

    col1,col2 = st.columns(2)

    def bs_section(items, title, color):
        rows = [{"Account":f"— {title} —","Amount (₹)":""}]
        for name,data in items.items():
            rows.append({"Account":f"  {name}","Amount (₹)":f"{data['bal']:,.2f}"})
        return rows

    with col1:
        st.markdown("#### 📦 Assets")
        a_rows = bs_section(assets,"Assets","blue")
        a_rows.append({"Account":"TOTAL ASSETS","Amount (₹)":f"{total_assets:,.2f}"})
        st.dataframe(pd.DataFrame(a_rows), use_container_width=True, hide_index=True)
        st.metric("Total Assets", f"₹{total_assets:,.2f}")

    with col2:
        st.markdown("#### 💳 Liabilities + Equity")
        l_rows = bs_section(liabilities,"Liabilities","red")
        l_rows.append({"Account":"TOTAL LIABILITIES","Amount (₹)":f"{total_liab:,.2f}"})
        l_rows.append({"Account":"","Amount (₹)":""})
        e_rows = bs_section(equity,"Equity","green")
        e_rows.append({"Account":"TOTAL EQUITY","Amount (₹)":f"{total_equity:,.2f}"})
        all_rows = l_rows + e_rows
        all_rows.append({"Account":"TOTAL L+E","Amount (₹)":f"{total_liab+total_equity:,.2f}"})
        st.dataframe(pd.DataFrame(all_rows), use_container_width=True, hide_index=True)

    bal_diff = abs(total_assets - (total_liab + total_equity))
    if bal_diff < 1:
        st.success("✅ Balance Sheet is balanced!")
    else:
        st.warning(f"⚠️ Difference: ₹{bal_diff:,.2f} — check your entries")

# ── TRIAL BALANCE ─────────────────────────────────────────────────────────────
with tab_tb:
    st.markdown("### Trial Balance")
    st.caption(f"As on {END}")

    rows = []; tdr = tcr = 0
    for acc, data in sorted(summary.items()):
        b = data["bal"]
        if b >= 0:
            rows.append({"Account":acc,"Group":data.get("group",""),"Type":data["type"],
                         "Debit (Dr)":round(b,2),"Credit (Cr)":0.0})
            tdr += b
        else:
            rows.append({"Account":acc,"Group":data.get("group",""),"Type":data["type"],
                         "Debit (Dr)":0.0,"Credit (Cr)":round(abs(b),2)})
            tcr += abs(b)

    rows.append({"Account":"TOTAL","Group":"","Type":"","Debit (Dr)":round(tdr,2),"Credit (Cr)":round(tcr,2)})
    df_tb = pd.DataFrame(rows)
    st.dataframe(df_tb, use_container_width=True, hide_index=True, height=500)

    balanced = abs(tdr-tcr) < 1
    if balanced:
        st.success(f"✅ Books are balanced! Total: ₹{tdr:,.2f}")
    else:
        st.error(f"⚠️ Imbalance: Dr={tdr:,.2f} Cr={tcr:,.2f} Diff=₹{abs(tdr-tcr):,.2f}")

    if st.button("📥 Download Trial Balance"):
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as w:
            df_tb.to_excel(w, index=False, sheet_name="Trial Balance")
        st.download_button("💾 TrialBalance.xlsx", buf.getvalue(),
                           file_name=f"TrialBalance_{END[:10]}.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# ── ACCOUNT LEDGER ────────────────────────────────────────────────────────────
with tab_ledger:
    st.markdown("### Account Ledger")

    acc_names = sorted(summary.keys()) if summary else [a["name"] for a in get_accounts()]
    selected_acc = st.selectbox("Select Account", acc_names)

    if selected_acc:
        txns = get_transactions(start=START, end=END, account=selected_acc)

        if not txns:
            st.info(f"No transactions for {selected_acc} in selected period.")
        else:
            data = summary.get(selected_acc, {})
            c1,c2,c3,c4 = st.columns(4)
            c1.metric("Total Debit",   f"₹{data.get('dr',0):,.2f}")
            c2.metric("Total Credit",  f"₹{data.get('cr',0):,.2f}")
            c3.metric("Balance",       f"₹{abs(data.get('bal',0)):,.2f}")
            c4.metric("Type",          data.get("type",""))

            running = 0.0
            rows = []
            acc_type = data.get("type","")
            for t in txns:
                dr = t["amount"] if t["account_dr"]==selected_acc else 0
                cr = t["amount"] if t["account_cr"]==selected_acc else 0
                if acc_type in ("Asset","Expense"):
                    running += dr - cr
                else:
                    running += cr - dr
                rows.append({
                    "Date":        t["date"],
                    "Voucher Type":t["voucher_type"],
                    "Party":       t.get("party",""),
                    "Description": (t.get("description","") or "")[:45],
                    "Debit (Dr)":  f"₹{dr:,.2f}" if dr else "—",
                    "Credit (Cr)": f"₹{cr:,.2f}" if cr else "—",
                    "Balance":     f"₹{abs(running):,.2f} {'Dr' if running>=0 else 'Cr'}",
                })

            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True, height=450)

            if st.button(f"📥 Download {selected_acc} Ledger"):
                buf = io.BytesIO()
                with pd.ExcelWriter(buf, engine="openpyxl") as w:
                    pd.DataFrame(rows).to_excel(w, index=False, sheet_name=selected_acc[:30])
                st.download_button("💾 Download", buf.getvalue(),
                                   file_name=f"Ledger_{selected_acc}_{END[:10]}.xlsx",
                                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
