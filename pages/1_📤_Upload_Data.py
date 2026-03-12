"""
Upload Data — smart importer for bank statements, sales, purchase files
"""
import streamlit as st
import pandas as pd
import io
from datetime import datetime
from database import init_db, bulk_insert, get_transactions

init_db()
st.markdown("## 📤 Upload Data")
st.caption("Upload your bank statement, sales or purchase Excel/CSV — column names auto-detected")

INDIAN_STATES = ["Andhra Pradesh","Arunachal Pradesh","Assam","Bihar","Chhattisgarh","Goa",
    "Gujarat","Haryana","Himachal Pradesh","Jharkhand","Karnataka","Kerala","Madhya Pradesh",
    "Maharashtra","Manipur","Meghalaya","Mizoram","Nagaland","Odisha","Punjab","Rajasthan",
    "Sikkim","Tamil Nadu","Telangana","Tripura","Uttar Pradesh","Uttarakhand","West Bengal",
    "Delhi","Jammu & Kashmir","Ladakh","Puducherry","Chandigarh","Other"]

# ── HELPERS ───────────────────────────────────────────────────────────────────
def detect_col(df, candidates):
    for c in candidates:
        for col in df.columns:
            if c.lower() in str(col).lower():
                return col
    return None

def to_num(val):
    try:
        if pd.isna(val): return 0.0
    except: pass
    try:
        return float(str(val).replace(",","").replace("₹","").replace("$","").strip())
    except:
        return 0.0

def parse_date(val):
    try: return str(pd.to_datetime(val).date())
    except: return str(datetime.today().date())

def smart_read(file_bytes, filename):
    """Auto-detect header row in bank statements."""
    ext = filename.rsplit(".",1)[-1].lower()
    raw = pd.read_excel(io.BytesIO(file_bytes), header=None) if ext in ["xlsx","xls"] \
          else pd.read_csv(io.BytesIO(file_bytes), header=None, encoding="latin-1")

    header_row = 0
    for i, row in raw.iterrows():
        vals = [str(v).strip().lower() for v in row if pd.notna(v)]
        has_date   = any("date" in v for v in vals)
        has_amount = any(any(k in v for k in ["amount","debit","credit","dr","cr","balance"]) for v in vals)
        if has_date and has_amount:
            header_row = i
            break

    if ext in ["xlsx","xls"]:
        df = pd.read_excel(io.BytesIO(file_bytes), header=header_row)
    else:
        df = pd.read_csv(io.BytesIO(file_bytes), header=header_row, encoding="latin-1")

    df.columns = [str(c).strip() for c in df.columns]
    return df.dropna(how="all"), header_row

def gst_split(amount, rate, txn_state, company_state):
    """Split GST into CGST+SGST (intra-state) or IGST (inter-state)."""
    gst_amt = round(amount * rate / 100, 2)
    if txn_state and company_state and txn_state.strip() != company_state.strip():
        return gst_amt, gst_amt, 0.0, 0.0   # igst, total_gst, cgst, sgst
    else:
        half = round(gst_amt / 2, 2)
        return 0.0, gst_amt, half, half      # igst, total_gst, cgst, sgst

# ── PROCESS FUNCTIONS ─────────────────────────────────────────────────────────

def process_bank(df, company_state=""):
    txns = []
    date_col   = detect_col(df, ["date"])
    desc_col   = detect_col(df, ["description","narration","particulars","details","remarks"])
    amount_col = detect_col(df, ["amount"])
    crdr_col   = detect_col(df, ["cr/dr","crdr","dr/cr","type","txn type"])
    debit_col  = detect_col(df, ["debit","withdrawal","dr"]) if not crdr_col else None
    credit_col = detect_col(df, ["credit","deposit","cr"]) if not crdr_col else None

    SKIP = {"sales","nan","none","","neft","imps","upi","rtgs","atm","pos"}

    def classify(desc):
        d = desc.lower()
        if any(k in d for k in ["salary","payroll","wages"]):      return "Salary"
        if any(k in d for k in ["rent","lease"]):                  return "Rent"
        if any(k in d for k in ["electric","internet","phone","utility","water"]): return "Utilities"
        if any(k in d for k in ["advertis","marketing"]):          return "Marketing"
        if any(k in d for k in ["purchase","vendor","supplier","raw","stock"]): return "Purchase"
        if any(k in d for k in ["professional","consultant","legal","audit"]): return "Professional Fees"
        if any(k in d for k in ["bank charge","service charge","commission"]): return "Bank Charges"
        if any(k in d for k in ["travel","transport","freight","courier"]):    return "Travel"
        return "Other Expense"

    for _, row in df.iterrows():
        date   = parse_date(row.get(date_col, datetime.today()))
        desc   = str(row.get(desc_col, "")).strip()
        amount = to_num(row.get(amount_col, 0))
        if not desc or desc.lower() in ["nan","none"] or amount == 0: continue

        if crdr_col:
            is_cr = str(row.get(crdr_col,"")).strip().lower() in ["cr","credit","c"]
        elif debit_col and credit_col:
            cr_v = to_num(row.get(credit_col,0)); dr_v = to_num(row.get(debit_col,0))
            is_cr = cr_v > 0; amount = cr_v if is_cr else dr_v
        else:
            is_cr = amount > 0; amount = abs(amount)

        party = desc if desc.lower() not in SKIP else ""

        if is_cr:
            txns.append({"date":date,"voucher_type":"Receipt","party":party,
                         "description":desc,"account_dr":"Bank","account_cr":"Sales Revenue",
                         "amount":amount,"total":amount,"source":"bank_upload"})
        else:
            acc = classify(desc)
            txns.append({"date":date,"voucher_type":"Payment","party":party,
                         "description":desc,"account_dr":acc,"account_cr":"Bank",
                         "amount":amount,"total":amount,"source":"bank_upload"})
    return txns

def process_sales(df, gst_rate_default=18, company_state="", place_of_supply=""):
    txns = []
    dc = detect_col(df,["date","invoice date","bill date"])
    cc = detect_col(df,["customer","client","buyer","party","name","party name"])
    ac = detect_col(df,["amount","taxable","net amount","basic"])
    gc = detect_col(df,["gst amount","gst","tax amount","tax"])
    rc = detect_col(df,["gst rate","tax rate","rate%","rate"])
    ic = detect_col(df,["invoice","invoice no","bill no","inv no","voucher"])
    hc = detect_col(df,["hsn","sac","hsn/sac","hsn code"])
    sc = detect_col(df,["state","place of supply","supply state"])

    for _, row in df.iterrows():
        date   = parse_date(row.get(dc, datetime.today()))
        cust   = str(row.get(cc,"Customer")).strip() if cc else "Customer"
        amount = to_num(row.get(ac,0))
        if amount == 0: continue
        inv    = str(row.get(ic,"")) if ic else ""
        hsn    = str(row.get(hc,"")) if hc else ""
        state  = str(row.get(sc, place_of_supply)) if sc else place_of_supply

        if gc:
            gst_amt = to_num(row.get(gc,0))
            rate    = round(gst_amt/amount*100) if amount else gst_rate_default
        elif rc:
            rate    = to_num(row.get(rc,gst_rate_default))
            gst_amt = round(amount*rate/100,2)
        else:
            rate    = gst_rate_default
            gst_amt = round(amount*rate/100,2)

        igst,total_gst,cgst,sgst = gst_split(amount, rate, state, company_state)
        total = amount + total_gst

        txns.append({
            "date":date,"voucher_type":"Sales","party":cust,
            "description":f"Sales to {cust}" + (f" [{inv}]" if inv else ""),
            "account_dr":"Accounts Receivable","account_cr":"Sales Revenue",
            "amount":amount,"gst_amount":total_gst,"gst_rate":rate,
            "igst":igst,"cgst":cgst,"sgst":sgst,
            "invoice_no":inv,"hsn_sac":hsn,"place_of_supply":state,
            "total":total,"source":"sales_upload"
        })

        # GST entries
        if cgst > 0:
            txns.append({"date":date,"voucher_type":"GST","party":cust,
                         "description":f"CGST @{rate/2}% on {inv or cust}",
                         "account_dr":"Accounts Receivable","account_cr":"Output CGST",
                         "amount":cgst,"total":cgst,"invoice_no":inv,"source":"sales_upload"})
            txns.append({"date":date,"voucher_type":"GST","party":cust,
                         "description":f"SGST @{rate/2}% on {inv or cust}",
                         "account_dr":"Accounts Receivable","account_cr":"Output SGST",
                         "amount":sgst,"total":sgst,"invoice_no":inv,"source":"sales_upload"})
        if igst > 0:
            txns.append({"date":date,"voucher_type":"GST","party":cust,
                         "description":f"IGST @{rate}% on {inv or cust}",
                         "account_dr":"Accounts Receivable","account_cr":"Output IGST",
                         "amount":igst,"total":igst,"invoice_no":inv,"source":"sales_upload"})
    return txns

def process_purchase(df, gst_rate_default=18, company_state=""):
    txns = []
    dc = detect_col(df,["date","invoice date","bill date","purchase date"])
    vc = detect_col(df,["vendor","supplier","seller","party","name"])
    ac = detect_col(df,["amount","taxable","net amount","basic"])
    gc = detect_col(df,["gst amount","gst","tax amount","tax"])
    rc = detect_col(df,["gst rate","tax rate","rate%","rate"])
    ic = detect_col(df,["invoice","invoice no","bill no","inv no"])
    hc = detect_col(df,["hsn","sac","hsn/sac"])
    sc = detect_col(df,["state","origin state","supplier state"])

    for _, row in df.iterrows():
        date   = parse_date(row.get(dc, datetime.today()))
        vend   = str(row.get(vc,"Vendor")).strip() if vc else "Vendor"
        amount = to_num(row.get(ac,0))
        if amount == 0: continue
        inv    = str(row.get(ic,"")) if ic else ""
        hsn    = str(row.get(hc,"")) if hc else ""
        state  = str(row.get(sc,"")) if sc else ""

        if gc:
            gst_amt = to_num(row.get(gc,0)); rate = round(gst_amt/amount*100) if amount else gst_rate_default
        elif rc:
            rate = to_num(row.get(rc,gst_rate_default)); gst_amt = round(amount*rate/100,2)
        else:
            rate = gst_rate_default; gst_amt = round(amount*rate/100,2)

        igst,total_gst,cgst,sgst = gst_split(amount,rate,state,company_state)
        total = amount + total_gst

        txns.append({
            "date":date,"voucher_type":"Purchase","party":vend,
            "description":f"Purchase from {vend}" + (f" [{inv}]" if inv else ""),
            "account_dr":"Purchase","account_cr":"Accounts Payable",
            "amount":amount,"gst_amount":total_gst,"gst_rate":rate,
            "igst":igst,"cgst":cgst,"sgst":sgst,
            "invoice_no":inv,"hsn_sac":hsn,
            "total":total,"source":"purchase_upload"
        })
        if cgst>0:
            txns.append({"date":date,"voucher_type":"GST","party":vend,
                         "description":f"Input CGST @{rate/2}% on {inv or vend}",
                         "account_dr":"Input CGST","account_cr":"Accounts Payable",
                         "amount":cgst,"total":cgst,"source":"purchase_upload"})
            txns.append({"date":date,"voucher_type":"GST","party":vend,
                         "description":f"Input SGST @{rate/2}% on {inv or vend}",
                         "account_dr":"Input SGST","account_cr":"Accounts Payable",
                         "amount":sgst,"total":sgst,"source":"purchase_upload"})
        if igst>0:
            txns.append({"date":date,"voucher_type":"GST","party":vend,
                         "description":f"Input IGST @{rate}% on {inv or vend}",
                         "account_dr":"Input IGST","account_cr":"Accounts Payable",
                         "amount":igst,"total":igst,"source":"purchase_upload"})
    return txns

# ── UI ────────────────────────────────────────────────────────────────────────
company_info = st.session_state.get("company", {})
company_state = company_info.get("state","Goa") if company_info else "Goa"

tab_bank, tab_sales, tab_purchase = st.tabs(["🏦 Bank Statement", "💰 Sales / Invoices", "🛒 Purchase / Bills"])

with tab_bank:
    st.markdown("**Upload your bank statement** — HDFC, ICICI, SBI, Axis all supported")
    col1, col2 = st.columns([2,1])
    with col1:
        bank_file = st.file_uploader("Bank Statement (Excel/CSV)", type=["xlsx","xls","csv"], key="bank_up")
    with col2:
        b_state = st.selectbox("Your State", INDIAN_STATES,
                                index=INDIAN_STATES.index("Goa") if "Goa" in INDIAN_STATES else 0,
                                key="bank_state")

    if bank_file:
        df, hrow = smart_read(bank_file.read(), bank_file.name)
        st.success(f"✓ File read — header at row {hrow} · {len(df)} rows · Columns: {list(df.columns)}")
        st.dataframe(df.head(5), use_container_width=True, hide_index=True)

        if st.button("💾 Import Bank Statement", type="primary", key="import_bank"):
            with st.spinner("Processing..."):
                bank_file.seek(0)
                df2, _ = smart_read(bank_file.read(), bank_file.name)
                txns = process_bank(df2, b_state)
                bulk_insert(txns)
            st.success(f"✅ Imported {len(txns)} transactions from {bank_file.name}")
            st.balloons()

with tab_sales:
    st.markdown("**Upload Sales / Invoice register**")
    col1, col2, col3 = st.columns([2,1,1])
    with col1:
        sales_file = st.file_uploader("Sales File (Excel/CSV)", type=["xlsx","xls","csv"], key="sales_up")
    with col2:
        s_gst_rate = st.number_input("Default GST Rate %", value=18, min_value=0, max_value=28, key="s_gst")
    with col3:
        s_pos = st.selectbox("Place of Supply", INDIAN_STATES,
                              index=INDIAN_STATES.index("Goa") if "Goa" in INDIAN_STATES else 0,
                              key="s_pos")

    if sales_file:
        df, hrow = smart_read(sales_file.read(), sales_file.name)
        st.success(f"✓ {len(df)} rows · Columns: {list(df.columns)}")
        st.dataframe(df.head(5), use_container_width=True, hide_index=True)

        if st.button("💾 Import Sales", type="primary", key="import_sales"):
            with st.spinner("Processing..."):
                sales_file.seek(0)
                df2, _ = smart_read(sales_file.read(), sales_file.name)
                txns = process_sales(df2, s_gst_rate, company_state, s_pos)
                bulk_insert(txns)
            st.success(f"✅ Imported {len([t for t in txns if t['voucher_type']=='Sales'])} sales invoices")
            st.balloons()

with tab_purchase:
    st.markdown("**Upload Purchase / Bill register**")
    col1, col2 = st.columns([2,1])
    with col1:
        purch_file = st.file_uploader("Purchase File (Excel/CSV)", type=["xlsx","xls","csv"], key="purch_up")
    with col2:
        p_gst_rate = st.number_input("Default GST Rate %", value=18, min_value=0, max_value=28, key="p_gst")

    if purch_file:
        df, hrow = smart_read(purch_file.read(), purch_file.name)
        st.success(f"✓ {len(df)} rows · Columns: {list(df.columns)}")
        st.dataframe(df.head(5), use_container_width=True, hide_index=True)

        if st.button("💾 Import Purchases", type="primary", key="import_purch"):
            with st.spinner("Processing..."):
                purch_file.seek(0)
                df2, _ = smart_read(purch_file.read(), purch_file.name)
                txns = process_purchase(df2, p_gst_rate, company_state)
                bulk_insert(txns)
            st.success(f"✅ Imported {len([t for t in txns if t['voucher_type']=='Purchase'])} purchase bills")
            st.balloons()

st.divider()
st.markdown("**📊 Uploaded Data Summary**")
all_txns = get_transactions()
if all_txns:
    df_all = pd.DataFrame(all_txns)
    by_type = df_all.groupby("voucher_type").agg(count=("id","count"), total=("total","sum")).reset_index()
    st.dataframe(by_type, use_container_width=True, hide_index=True)
else:
    st.info("No data uploaded yet.")
