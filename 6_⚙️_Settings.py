"""
Settings — Company Info + ITR Schedule
"""
import streamlit as st
import pandas as pd
import io
from datetime import datetime, date
from database import init_db, get_company, save_company, get_ledger_summary, get_transactions

init_db()
st.markdown("## ⚙️ Settings & ITR")

INDIAN_STATES = ["Andhra Pradesh","Arunachal Pradesh","Assam","Bihar","Chhattisgarh","Goa",
    "Gujarat","Haryana","Himachal Pradesh","Jharkhand","Karnataka","Kerala","Madhya Pradesh",
    "Maharashtra","Manipur","Meghalaya","Mizoram","Nagaland","Odisha","Punjab","Rajasthan",
    "Sikkim","Tamil Nadu","Telangana","Tripura","Uttar Pradesh","Uttarakhand","West Bengal",
    "Delhi","Jammu & Kashmir","Ladakh","Puducherry","Chandigarh","Other"]

tab_company, tab_itr, tab_data = st.tabs(["🏢 Company Info", "📑 ITR Schedule", "🗄️ Data Management"])

# ── COMPANY SETTINGS ──────────────────────────────────────────────────────────
with tab_company:
    st.markdown("#### Business / Company Details")
    company = get_company()

    col1, col2 = st.columns(2)
    with col1:
        name    = st.text_input("Business Name *",         value=company.get("name",""))
        gstin   = st.text_input("GSTIN",                   value=company.get("gstin",""), placeholder="22AAAAA0000A1Z5")
        pan     = st.text_input("PAN",                     value=company.get("pan",""),   placeholder="AAAAA0000A")
        email   = st.text_input("Email",                   value=company.get("email",""))
    with col2:
        phone   = st.text_input("Phone",                   value=company.get("phone",""))
        state   = st.selectbox("State", INDIAN_STATES,
                               index=INDIAN_STATES.index(company.get("state","Goa")) if company.get("state") in INDIAN_STATES else 0)
        address = st.text_area("Address",                  value=company.get("address",""), height=80)
        fy_start= st.selectbox("Financial Year Start Month", ["04 — April (Default)","01 — January"],
                                index=0 if company.get("fy_start","04")=="04" else 1)

    if st.button("💾 Save Company Details", type="primary"):
        save_company({
            "name": name, "gstin": gstin, "pan": pan,
            "email": email, "phone": phone, "state": state,
            "address": address, "fy_start": fy_start[:2]
        })
        st.session_state["company"] = {"name":name,"gstin":gstin,"state":state}
        st.success("✅ Company details saved!")

    if company.get("gstin"):
        st.markdown("---")
        st.markdown(f"""
        **GSTIN:** `{company.get('gstin','')}` &nbsp;|&nbsp; 
        **PAN:** `{company.get('pan','')}` &nbsp;|&nbsp; 
        **State:** {company.get('state','')}
        """)

# ── ITR SCHEDULE ──────────────────────────────────────────────────────────────
with tab_itr:
    st.markdown("### ITR Filing — Income & Expense Summary")
    st.caption("Summary for ITR-3 (Business Income) / ITR-4 (Presumptive)")

    START = st.session_state.get("filter_start", f"{datetime.today().year}-04-01")
    END   = st.session_state.get("filter_end",   str(date.today()))
    company = get_company()

    summary = get_ledger_summary(start=START, end=END)
    txns    = get_transactions(start=START, end=END)

    income_items  = {k:v["bal"] for k,v in summary.items() if v["type"]=="Income"}
    expense_items = {k:v["bal"] for k,v in summary.items() if v["type"]=="Expense"}
    total_income  = sum(income_items.values())
    total_expense = sum(expense_items.values())
    net_profit    = total_income - total_expense

    sales_txns = [t for t in txns if t["voucher_type"]=="Sales"]
    total_gst_collected = sum(t.get("gst_amount",0) for t in sales_txns)
    total_turnover = sum(t.get("total",0) for t in sales_txns)

    st.markdown(f"**Period:** {START} to {END} | **Business:** {company.get('name','')} | **PAN:** {company.get('pan','Not Set')}")
    st.divider()

    col1,col2 = st.columns(2)
    with col1:
        st.markdown("#### Schedule BP — Business Profit")
        bp_data = {
            "Particulars": [
                "Gross Turnover / Receipts",
                "Less: GST Collected (not income)",
                "Net Turnover (Taxable)",
                "",
                "EXPENSES",
            ] + [f"  {k}" for k in expense_items.keys()] + [
                "",
                "Total Expenses",
                "NET PROFIT (before tax)",
            ],
            "Amount (₹)": [
                f"{total_turnover:,.2f}",
                f"({total_gst_collected:,.2f})",
                f"{total_income:,.2f}",
                "",
                "",
            ] + [f"{v:,.2f}" for v in expense_items.values()] + [
                "",
                f"{total_expense:,.2f}",
                f"{net_profit:,.2f}",
            ]
        }
        st.dataframe(pd.DataFrame(bp_data), use_container_width=True, hide_index=True)

    with col2:
        st.markdown("#### Key Figures for ITR")
        st.metric("Gross Turnover",     f"₹{total_turnover:,.2f}")
        st.metric("Net Turnover",       f"₹{total_income:,.2f}")
        st.metric("Total Expenses",     f"₹{total_expense:,.2f}")
        st.metric("Net Profit",         f"₹{net_profit:,.2f}")
        st.metric("GST Collected",      f"₹{total_gst_collected:,.2f}")
        st.metric("Taxable Income",     f"₹{max(net_profit,0):,.2f}")

        # Presumptive income (44AD)
        presumptive_8 = round(total_income * 0.08, 2)
        presumptive_6 = round(total_income * 0.06, 2)
        st.divider()
        st.markdown("**Section 44AD (Presumptive)**")
        st.metric("8% of Turnover (Cash)", f"₹{presumptive_8:,.2f}")
        st.metric("6% of Turnover (Digital)", f"₹{presumptive_6:,.2f}")

    st.divider()
    if st.button("📥 Download ITR Summary Excel"):
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as w:
            pd.DataFrame(bp_data).to_excel(w, index=False, sheet_name="ITR Schedule BP")
            pd.DataFrame({
                "Income Account": list(income_items.keys()),
                "Amount": list(income_items.values())
            }).to_excel(w, index=False, sheet_name="Income Detail")
            pd.DataFrame({
                "Expense Account": list(expense_items.keys()),
                "Amount": list(expense_items.values())
            }).to_excel(w, index=False, sheet_name="Expense Detail")
        st.download_button("💾 ITR_Summary.xlsx", buf.getvalue(),
                           file_name=f"ITR_Summary_{START[:4]}.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# ── DATA MANAGEMENT ───────────────────────────────────────────────────────────
with tab_data:
    st.markdown("#### Export Full Data")
    txns = get_transactions()
    if txns:
        df = pd.DataFrame(txns)
        if st.button("📥 Export All Transactions"):
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine="openpyxl") as w:
                df.to_excel(w, index=False, sheet_name="All Transactions")
            st.download_button("💾 All_Transactions.xlsx", buf.getvalue(),
                               file_name="All_Transactions.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        st.dataframe(df[["id","date","voucher_type","party","description","amount","total","source"]].tail(20),
                     use_container_width=True, hide_index=True)
    else:
        st.info("No transactions to export.")

    st.divider()
    st.markdown("#### ⚠️ Danger Zone")
    confirm_del = st.text_input("Type DELETE to clear all data", key="del_all")
    if st.button("🗑️ Clear ALL Data", type="secondary"):
        if confirm_del == "DELETE":
            import sqlite3, os
            from database import DB_PATH
            conn = sqlite3.connect(DB_PATH)
            conn.execute("DELETE FROM transactions")
            conn.commit(); conn.close()
            st.success("All transactions deleted.")
            st.rerun()
        else:
            st.error("Type DELETE to confirm")
