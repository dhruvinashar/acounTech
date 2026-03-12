"""
GST Reports — GSTR-1, GSTR-3B, ITC Summary
"""
import streamlit as st
import pandas as pd
import io
from datetime import datetime, date
from database import init_db, get_transactions

init_db()
st.markdown("## 🧾 GST Reports")
st.caption("GSTR-1 (Sales), GSTR-3B (Summary), ITC Reconciliation")

START = st.session_state.get("filter_start", f"{datetime.today().year}-04-01")
END   = st.session_state.get("filter_end",   str(date.today()))

# ── LOAD DATA ─────────────────────────────────────────────────────────────────
all_txns  = get_transactions(start=START, end=END)
sales_txns= [t for t in all_txns if t["voucher_type"]=="Sales"]
purch_txns= [t for t in all_txns if t["voucher_type"]=="Purchase"]

# Aggregate GST
def agg_gst(txns):
    total_taxable = sum(t["amount"] for t in txns)
    total_igst    = sum(t.get("igst",0) for t in txns)
    total_cgst    = sum(t.get("cgst",0) for t in txns)
    total_sgst    = sum(t.get("sgst",0) for t in txns)
    total_gst     = total_igst + total_cgst + total_sgst
    return round(total_taxable,2), round(total_igst,2), round(total_cgst,2), round(total_sgst,2), round(total_gst,2)

s_taxable, s_igst, s_cgst, s_sgst, s_gst = agg_gst(sales_txns)
p_taxable, p_igst, p_cgst, p_sgst, p_gst = agg_gst(purch_txns)
net_igst  = round(s_igst - p_igst, 2)
net_cgst  = round(s_cgst - p_cgst, 2)
net_sgst  = round(s_sgst - p_sgst, 2)
net_gst   = round(s_gst  - p_gst,  2)

tab_3b, tab_gstr1, tab_itc, tab_hsn = st.tabs(["📋 GSTR-3B", "📄 GSTR-1", "🔄 ITC Summary", "🔢 HSN Summary"])

# ─── GSTR-3B ──────────────────────────────────────────────────────────────────
with tab_3b:
    st.markdown("### GSTR-3B — Monthly Summary Return")
    st.caption(f"Period: {START} to {END}")

    st.markdown("#### 3.1 — Outward Supplies (Sales)")
    out_data = {
        "Nature of Supply": ["(a) Outward taxable supplies (other than zero rated, nil, exempted)",
                             "(b) Outward taxable supplies (Zero rated)", "(c) Other outward supplies (Nil, Exempted)"],
        "Total Taxable Value (₹)": [s_taxable, 0, 0],
        "IGST (₹)": [s_igst, 0, 0],
        "CGST (₹)": [s_cgst, 0, 0],
        "SGST/UTGST (₹)": [s_sgst, 0, 0],
        "Cess (₹)": [0, 0, 0],
    }
    st.dataframe(pd.DataFrame(out_data), use_container_width=True, hide_index=True)

    st.markdown("#### 4 — Eligible ITC (Purchases)")
    itc_data = {
        "ITC Available": ["(A) Import of goods", "(B) Import of services",
                          "(C) Inward supplies liable to reverse charge",
                          "(D) Inward supplies from ISD",
                          "(E) All other ITC — Inputs, Capital Goods, Input Services"],
        "IGST (₹)": [0, 0, 0, 0, p_igst],
        "CGST (₹)": [0, 0, 0, 0, p_cgst],
        "SGST/UTGST (₹)": [0, 0, 0, 0, p_sgst],
        "Cess (₹)": [0, 0, 0, 0, 0],
    }
    st.dataframe(pd.DataFrame(itc_data), use_container_width=True, hide_index=True)

    st.markdown("#### 5.1 — Tax Payable and Paid")
    pay_data = {
        "Description": ["IGST", "CGST", "SGST/UTGST", "Cess", "TOTAL"],
        "Tax Payable (₹)": [s_igst, s_cgst, s_sgst, 0, round(s_igst+s_cgst+s_sgst,2)],
        "ITC (₹)":         [p_igst, p_cgst, p_sgst, 0, round(p_igst+p_cgst+p_sgst,2)],
        "Net Tax Payable (₹)": [net_igst, net_cgst, net_sgst, 0, net_gst],
    }
    df_pay = pd.DataFrame(pay_data)
    st.dataframe(df_pay, use_container_width=True, hide_index=True)

    # Highlight net
    col1,col2,col3,col4 = st.columns(4)
    col1.metric("Net IGST Payable",     f"₹{net_igst:,.2f}", delta=None)
    col2.metric("Net CGST Payable",     f"₹{net_cgst:,.2f}")
    col3.metric("Net SGST Payable",     f"₹{net_sgst:,.2f}")
    col4.metric("Total GST Liability",  f"₹{net_gst:,.2f}",
                delta=f"{'Pay ₹'+str(abs(net_gst)) if net_gst>0 else 'Refund ₹'+str(abs(net_gst))}")

    if st.button("📥 Download GSTR-3B Excel", key="dl_3b"):
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            pd.DataFrame(out_data).to_excel(writer, sheet_name="3.1 Outward", index=False)
            pd.DataFrame(itc_data).to_excel(writer, sheet_name="4 ITC", index=False)
            pd.DataFrame(pay_data).to_excel(writer, sheet_name="5.1 Tax Payable", index=False)
        st.download_button("💾 GSTR-3B.xlsx", buf.getvalue(),
                           file_name=f"GSTR3B_{START[:7]}.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# ─── GSTR-1 ───────────────────────────────────────────────────────────────────
with tab_gstr1:
    st.markdown("### GSTR-1 — Outward Supplies Return")
    st.caption("Invoice-wise details of all sales (B2B & B2C)")

    if not sales_txns:
        st.info("No sales transactions found for selected period.")
    else:
        df_sales = pd.DataFrame(sales_txns)

        # B2B — parties with GSTIN
        # For now show all as invoice register
        st.markdown("#### Invoice Register — Outward Supplies")
        display = []
        for t in sales_txns:
            display.append({
                "Invoice Date":   t["date"],
                "Invoice No":     t.get("invoice_no",""),
                "Party Name":     t.get("party",""),
                "HSN/SAC":        t.get("hsn_sac",""),
                "Place of Supply":t.get("place_of_supply",""),
                "Taxable Value":  round(t["amount"],2),
                "IGST":           round(t.get("igst",0),2),
                "CGST":           round(t.get("cgst",0),2),
                "SGST":           round(t.get("sgst",0),2),
                "GST Rate %":     t.get("gst_rate",0),
                "Invoice Value":  round(t.get("total",0),2),
            })

        df_disp = pd.DataFrame(display)
        st.dataframe(df_disp, use_container_width=True, hide_index=True, height=400)

        # Totals row
        st.markdown(f"""
        **Summary:**  Invoices: **{len(display)}** | 
        Taxable: **₹{df_disp['Taxable Value'].sum():,.2f}** | 
        IGST: **₹{df_disp['IGST'].sum():,.2f}** | 
        CGST: **₹{df_disp['CGST'].sum():,.2f}** | 
        SGST: **₹{df_disp['SGST'].sum():,.2f}** | 
        Total: **₹{df_disp['Invoice Value'].sum():,.2f}**
        """)

        # Rate-wise breakup (Table 7)
        st.markdown("#### Rate-wise Summary (Table 7)")
        rate_grp = df_disp.groupby("GST Rate %").agg(
            Invoices=("Invoice No","count"),
            Taxable=("Taxable Value","sum"),
            IGST=("IGST","sum"),
            CGST=("CGST","sum"),
            SGST=("SGST","sum"),
            Total=("Invoice Value","sum")
        ).reset_index()
        st.dataframe(rate_grp, use_container_width=True, hide_index=True)

        if st.button("📥 Download GSTR-1 Excel", key="dl_gstr1"):
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine="openpyxl") as writer:
                df_disp.to_excel(writer, sheet_name="B2B Invoices", index=False)
                rate_grp.to_excel(writer, sheet_name="Rate-wise Summary", index=False)
            st.download_button("💾 GSTR-1.xlsx", buf.getvalue(),
                               file_name=f"GSTR1_{START[:7]}.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# ─── ITC RECONCILIATION ───────────────────────────────────────────────────────
with tab_itc:
    st.markdown("### Input Tax Credit (ITC) Summary")

    col1,col2 = st.columns(2)
    with col1:
        st.markdown("**Output Tax (Sales)**")
        st.metric("Total Taxable Sales", f"₹{s_taxable:,.2f}")
        st.metric("Output IGST", f"₹{s_igst:,.2f}")
        st.metric("Output CGST", f"₹{s_cgst:,.2f}")
        st.metric("Output SGST", f"₹{s_sgst:,.2f}")
        st.metric("Total Output GST", f"₹{s_gst:,.2f}")
    with col2:
        st.markdown("**Input Tax Credit (Purchases)**")
        st.metric("Total Taxable Purchases", f"₹{p_taxable:,.2f}")
        st.metric("Input IGST (ITC)", f"₹{p_igst:,.2f}")
        st.metric("Input CGST (ITC)", f"₹{p_cgst:,.2f}")
        st.metric("Input SGST (ITC)", f"₹{p_sgst:,.2f}")
        st.metric("Total Input ITC",  f"₹{p_gst:,.2f}")

    st.divider()
    c1,c2,c3 = st.columns(3)
    c1.metric("Net GST Payable", f"₹{net_gst:,.2f}",
              help="Output GST − Input ITC")
    c2.metric("Effective Tax Rate",
              f"{round(net_gst/s_taxable*100,2) if s_taxable else 0}%")
    c3.metric("ITC Utilization",
              f"{round(p_gst/s_gst*100,1) if s_gst else 0}%",
              help="How much of output tax is offset by ITC")

    # Purchase detail
    if purch_txns:
        st.markdown("#### Purchase Register (ITC)")
        df_p = pd.DataFrame([{
            "Date": t["date"], "Invoice": t.get("invoice_no",""),
            "Vendor": t.get("party",""), "Taxable": round(t["amount"],2),
            "IGST": round(t.get("igst",0),2), "CGST": round(t.get("cgst",0),2),
            "SGST": round(t.get("sgst",0),2), "Total": round(t.get("total",0),2)
        } for t in purch_txns])
        st.dataframe(df_p, use_container_width=True, hide_index=True)

# ─── HSN SUMMARY ──────────────────────────────────────────────────────────────
with tab_hsn:
    st.markdown("### HSN/SAC Wise Summary")
    st.caption("Required for GSTR-1 filing if turnover > ₹5 Cr")

    if not sales_txns:
        st.info("No sales data.")
    else:
        hsn_data = {}
        for t in sales_txns:
            hsn = t.get("hsn_sac","") or "Not Specified"
            if hsn not in hsn_data:
                hsn_data[hsn] = {"qty":0,"taxable":0,"igst":0,"cgst":0,"sgst":0}
            hsn_data[hsn]["taxable"] += t["amount"]
            hsn_data[hsn]["igst"]    += t.get("igst",0)
            hsn_data[hsn]["cgst"]    += t.get("cgst",0)
            hsn_data[hsn]["sgst"]    += t.get("sgst",0)

        rows = [{"HSN/SAC":k,"Taxable Value":round(v["taxable"],2),
                 "IGST":round(v["igst"],2),"CGST":round(v["cgst"],2),
                 "SGST":round(v["sgst"],2),
                 "Total Tax":round(v["igst"]+v["cgst"]+v["sgst"],2)}
                for k,v in hsn_data.items()]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
