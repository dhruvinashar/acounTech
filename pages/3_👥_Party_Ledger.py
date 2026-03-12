"""
Party Ledger — Tally-style Sundry Debtors & Creditors
"""
import streamlit as st
import pandas as pd
from datetime import datetime, date
from database import init_db, get_transactions, get_parties, upsert_party

init_db()
st.markdown("## 👥 Party Ledger")
st.caption("Tally-style party-wise accounts — debtors, creditors, running balance")

START = st.session_state.get("filter_start", f"{datetime.today().year}-04-01")
END   = st.session_state.get("filter_end",   str(date.today()))

# ── BUILD PARTY SUMMARY ───────────────────────────────────────────────────────
txns = get_transactions(start=START, end=END)

party_data = {}
for t in txns:
    party = (t.get("party") or "").strip()
    if not party or party.lower() in ["nan","none",""]: continue
    if party not in party_data:
        party_data[party] = {"txns": [], "total_dr": 0.0, "total_cr": 0.0}

    # Determine dr/cr from party's perspective
    dr = cr = 0.0
    if t["voucher_type"] in ("Sales","Receipt"):
        dr = t["total"]   # party owes us
    elif t["voucher_type"] in ("Purchase","Payment"):
        cr = t["total"]   # we paid party / owe party
    elif t["voucher_type"] == "Credit Note":
        cr = t["total"]
    elif t["voucher_type"] == "Debit Note":
        dr = t["total"]
    else:
        dr = t.get("amount",0)

    party_data[party]["txns"].append({**t, "party_dr": dr, "party_cr": cr})
    party_data[party]["total_dr"] += dr
    party_data[party]["total_cr"] += cr

# ── TABS ──────────────────────────────────────────────────────────────────────
tab_summary, tab_detail, tab_manage = st.tabs(["📊 Summary", "📋 Party Detail", "⚙️ Manage Parties"])

with tab_summary:
    if not party_data:
        st.info("No party data found. Upload data or add entries first.")
    else:
        rows = []
        for name, data in sorted(party_data.items()):
            bal   = data["total_dr"] - data["total_cr"]
            ptype = "🟢 Debtor"  if bal > 0 else ("🔴 Creditor" if bal < 0 else "⚪ Settled")
            rows.append({
                "Party": name,
                "Transactions": len(data["txns"]),
                "Total Dr (₹)": round(data["total_dr"],2),
                "Total Cr (₹)": round(data["total_cr"],2),
                "Balance (₹)": round(abs(bal),2),
                "Type": ptype,
                "Dr/Cr": "Dr" if bal>=0 else "Cr"
            })

        df = pd.DataFrame(rows)

        # KPI row
        total_debtors  = df[df["Dr/Cr"]=="Dr"]["Balance (₹)"].sum()
        total_creditors= df[df["Dr/Cr"]=="Cr"]["Balance (₹)"].sum()
        c1,c2,c3 = st.columns(3)
        c1.metric("Total Parties", len(df))
        c2.metric("Total Receivable (Debtors)",  f"₹{total_debtors:,.2f}")
        c3.metric("Total Payable (Creditors)",   f"₹{total_creditors:,.2f}")

        # Filter
        filter_type = st.radio("Show", ["All","Debtors only","Creditors only"], horizontal=True)
        if filter_type == "Debtors only":   df = df[df["Dr/Cr"]=="Dr"]
        elif filter_type == "Creditors only": df = df[df["Dr/Cr"]=="Cr"]

        st.dataframe(
            df.drop(columns=["Dr/Cr"]),
            use_container_width=True, hide_index=True, height=450
        )

with tab_detail:
    if not party_data:
        st.info("No party data available.")
    else:
        selected_party = st.selectbox("Select Party", sorted(party_data.keys()))

        if selected_party:
            data = party_data[selected_party]
            bal  = data["total_dr"] - data["total_cr"]

            c1,c2,c3,c4 = st.columns(4)
            c1.metric("Total Debit (Dr)",  f"₹{data['total_dr']:,.2f}")
            c2.metric("Total Credit (Cr)", f"₹{data['total_cr']:,.2f}")
            c3.metric("Balance",  f"₹{abs(bal):,.2f}")
            c4.metric("Type", "Debtor (Dr)" if bal>=0 else "Creditor (Cr)")

            # Running balance table
            running = 0.0
            rows = []
            for t in sorted(data["txns"], key=lambda x: x["date"]):
                running += t["party_dr"] - t["party_cr"]
                rows.append({
                    "Date":        t["date"],
                    "Type":        t["voucher_type"],
                    "Invoice":     t.get("invoice_no",""),
                    "Description": (t.get("description") or "")[:45],
                    "Debit (Dr)":  f"₹{t['party_dr']:,.2f}" if t["party_dr"] else "—",
                    "Credit (Cr)": f"₹{t['party_cr']:,.2f}" if t["party_cr"] else "—",
                    "Balance":     f"₹{abs(running):,.2f} {'Dr' if running>=0 else 'Cr'}",
                })

            st.markdown(f"**📋 {selected_party} — Transaction History**")
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True, height=450)

            # Download
            if st.button("📥 Download Party Ledger", key="dl_party"):
                df_exp = pd.DataFrame(rows)
                buf = __import__("io").BytesIO()
                with __import__("pandas").ExcelWriter(buf, engine="openpyxl") as w:
                    df_exp.to_excel(w, index=False, sheet_name=selected_party[:30])
                st.download_button(f"💾 {selected_party}.xlsx",
                                   buf.getvalue(),
                                   file_name=f"{selected_party}_ledger.xlsx",
                                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

with tab_manage:
    st.markdown("#### Add / Update Party Details")
    st.caption("Store GSTIN, PAN, contact info for each party")

    col1, col2 = st.columns(2)
    with col1:
        p_name   = st.text_input("Party Name *")
        p_gstin  = st.text_input("GSTIN", placeholder="22AAAAA0000A1Z5")
        p_pan    = st.text_input("PAN", placeholder="AAAAA0000A")
        p_type   = st.selectbox("Party Type", ["both","customer","vendor"])
    with col2:
        p_phone  = st.text_input("Phone")
        p_email  = st.text_input("Email")
        p_state  = st.text_input("State")
        p_addr   = st.text_area("Address", height=80)

    if st.button("💾 Save Party", type="primary"):
        if not p_name:
            st.error("Party name is required")
        else:
            upsert_party({"name":p_name,"gstin":p_gstin,"pan":p_pan,
                           "phone":p_phone,"email":p_email,"state":p_state,
                           "address":p_addr,"type":p_type})
            st.success(f"✅ Party '{p_name}' saved!")

    st.divider()
    st.markdown("#### Existing Parties")
    parties = get_parties()
    if parties:
        st.dataframe(pd.DataFrame(parties)[["name","gstin","pan","phone","email","state","type"]],
                     use_container_width=True, hide_index=True)
    else:
        st.info("No parties added yet. They are auto-created when you import data.")
