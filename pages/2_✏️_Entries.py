"""
Manual Entries — Add, Edit, Delete vouchers like Tally
"""
import streamlit as st
import pandas as pd
from datetime import datetime, date
from database import init_db, add_transaction, get_transactions, update_transaction, delete_transaction, get_account_names

init_db()
st.markdown("## ✏️ Journal Entries")
st.caption("Add, edit or delete any entry — full double-entry bookkeeping")

accounts  = get_account_names()
VOUCHER_TYPES = ["Sales","Purchase","Receipt","Payment","Journal","Contra","Debit Note","Credit Note"]
GST_RATES = [0, 5, 12, 18, 28]

tab_add, tab_view = st.tabs(["➕ New Entry", "📋 View / Edit / Delete"])

# ── ADD ENTRY ─────────────────────────────────────────────────────────────────
with tab_add:
    st.markdown("#### New Voucher Entry")

    col1, col2, col3 = st.columns(3)
    with col1:
        v_date = st.date_input("Date", value=date.today())
        v_type = st.selectbox("Voucher Type", VOUCHER_TYPES)
    with col2:
        v_party = st.text_input("Party Name", placeholder="Customer / Vendor name")
        v_invoice = st.text_input("Invoice / Bill No", placeholder="INV-001")
    with col3:
        v_dr_acc = st.selectbox("Debit Account (Dr)", accounts, index=accounts.index("Bank") if "Bank" in accounts else 0)
        v_cr_acc = st.selectbox("Credit Account (Cr)", accounts, index=accounts.index("Sales Revenue") if "Sales Revenue" in accounts else 1)

    col4, col5, col6 = st.columns(3)
    with col4:
        v_amount = st.number_input("Taxable Amount (₹)", min_value=0.0, step=100.0, format="%.2f")
    with col5:
        v_gst_rate = st.selectbox("GST Rate %", GST_RATES, index=3)
        v_gst_amt  = round(v_amount * v_gst_rate / 100, 2)
        st.info(f"GST Amount: ₹{v_gst_amt:,.2f}  |  Total: ₹{v_amount+v_gst_amt:,.2f}")
    with col6:
        v_hsn = st.text_input("HSN/SAC Code", placeholder="e.g. 9965")

    v_desc = st.text_area("Description / Narration", placeholder="Description of transaction", height=80)

    if st.button("💾 Save Entry", type="primary"):
        if v_amount <= 0:
            st.error("Amount must be greater than 0")
        elif v_dr_acc == v_cr_acc:
            st.error("Debit and Credit accounts cannot be same")
        else:
            half = round(v_gst_amt/2, 2)
            add_transaction({
                "date": str(v_date),
                "voucher_type": v_type,
                "party": v_party,
                "description": v_desc or f"{v_type} entry",
                "account_dr": v_dr_acc,
                "account_cr": v_cr_acc,
                "amount": v_amount,
                "gst_amount": v_gst_amt,
                "gst_rate": v_gst_rate,
                "cgst": half,
                "sgst": half,
                "invoice_no": v_invoice,
                "hsn_sac": v_hsn,
                "total": v_amount + v_gst_amt,
                "narration": v_desc,
                "source": "manual"
            })
            st.success("✅ Entry saved!")
            st.rerun()

# ── VIEW / EDIT / DELETE ──────────────────────────────────────────────────────
with tab_view:
    st.markdown("#### All Entries")

    # Filters
    fc1, fc2, fc3, fc4 = st.columns(4)
    with fc1:
        f_type = st.selectbox("Filter by Type", ["All"] + VOUCHER_TYPES, key="f_type")
    with fc2:
        f_party = st.text_input("Search Party", key="f_party", placeholder="Type to search...")
    with fc3:
        f_start = st.date_input("From", value=date(datetime.today().year, 4, 1), key="f_start")
    with fc4:
        f_end = st.date_input("To", value=date.today(), key="f_end")

    txns = get_transactions(
        start=str(f_start), end=str(f_end),
        voucher_type=None if f_type=="All" else f_type,
        party=f_party if f_party else None
    )

    if not txns:
        st.info("No entries found for selected filters.")
    else:
        df = pd.DataFrame(txns)
        st.markdown(f"**{len(df)} entries** | Total: ₹{df['total'].sum():,.2f}")

        # Display table
        display_cols = ["id","date","voucher_type","party","description","account_dr","account_cr","amount","gst_amount","total"]
        available = [c for c in display_cols if c in df.columns]
        st.dataframe(
            df[available].rename(columns={
                "id":"ID","date":"Date","voucher_type":"Type","party":"Party",
                "description":"Description","account_dr":"Dr","account_cr":"Cr",
                "amount":"Amount","gst_amount":"GST","total":"Total"
            }),
            use_container_width=True, hide_index=True, height=400
        )

        st.divider()
        st.markdown("#### Edit or Delete Entry")
        col_e1, col_e2 = st.columns(2)

        with col_e1:
            st.markdown("**✏️ Edit Entry**")
            edit_id = st.number_input("Entry ID to Edit", min_value=1, step=1, key="edit_id")
            edit_txn = next((t for t in txns if t["id"]==edit_id), None)
            if edit_txn:
                st.caption(f"Editing: {edit_txn['date']} | {edit_txn['voucher_type']} | {edit_txn['party']} | ₹{edit_txn['total']}")
                e_date   = st.date_input("Date", value=pd.to_datetime(edit_txn["date"]).date(), key="e_date")
                e_type   = st.selectbox("Type", VOUCHER_TYPES, index=VOUCHER_TYPES.index(edit_txn["voucher_type"]) if edit_txn["voucher_type"] in VOUCHER_TYPES else 0, key="e_type")
                e_party  = st.text_input("Party", value=edit_txn.get("party",""), key="e_party")
                e_dr     = st.selectbox("Dr Account", accounts, index=accounts.index(edit_txn["account_dr"]) if edit_txn["account_dr"] in accounts else 0, key="e_dr")
                e_cr     = st.selectbox("Cr Account", accounts, index=accounts.index(edit_txn["account_cr"]) if edit_txn["account_cr"] in accounts else 0, key="e_cr")
                e_amount = st.number_input("Amount", value=float(edit_txn["amount"]), key="e_amount")
                e_gst    = st.number_input("GST Amount", value=float(edit_txn.get("gst_amount",0)), key="e_gst")
                e_inv    = st.text_input("Invoice No", value=edit_txn.get("invoice_no",""), key="e_inv")
                e_desc   = st.text_area("Description", value=edit_txn.get("description",""), key="e_desc")

                if st.button("💾 Update Entry", type="primary", key="update_btn"):
                    update_transaction(edit_id, {
                        "date":str(e_date),"voucher_type":e_type,"party":e_party,
                        "account_dr":e_dr,"account_cr":e_cr,"amount":e_amount,
                        "gst_amount":e_gst,"gst_rate":edit_txn.get("gst_rate",0),
                        "igst":edit_txn.get("igst",0),"cgst":edit_txn.get("cgst",0),"sgst":edit_txn.get("sgst",0),
                        "invoice_no":e_inv,"hsn_sac":edit_txn.get("hsn_sac",""),
                        "total":e_amount+e_gst,"description":e_desc,"narration":e_desc
                    })
                    st.success("✅ Entry updated!")
                    st.rerun()

        with col_e2:
            st.markdown("**🗑️ Delete Entry**")
            del_id = st.number_input("Entry ID to Delete", min_value=1, step=1, key="del_id")
            del_txn = next((t for t in txns if t["id"]==del_id), None)
            if del_txn:
                st.warning(f"⚠️ This will delete: {del_txn['date']} | {del_txn['voucher_type']} | {del_txn.get('party','')} | ₹{del_txn['total']}")
            confirm = st.checkbox("I confirm I want to delete this entry", key="del_confirm")
            if st.button("🗑️ Delete Entry", type="secondary", key="del_btn"):
                if not confirm:
                    st.error("Please confirm deletion first")
                elif not del_txn:
                    st.error("Entry ID not found in current filter")
                else:
                    delete_transaction(del_id)
                    st.success(f"✅ Entry #{del_id} deleted")
                    st.rerun()
