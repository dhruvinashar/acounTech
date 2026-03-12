"""
AccounTech Database Layer
SQLite — persists all data permanently on Streamlit Cloud
"""
import sqlite3
import os
import pandas as pd
from datetime import datetime

DB_PATH = os.environ.get("DB_PATH", "accounTech.db")

def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    c = conn.cursor()

    c.executescript("""
    CREATE TABLE IF NOT EXISTS companies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        gstin TEXT,
        pan TEXT,
        address TEXT,
        state TEXT,
        email TEXT,
        phone TEXT,
        fy_start TEXT DEFAULT '04',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id INTEGER DEFAULT 1,
        date TEXT NOT NULL,
        voucher_no TEXT,
        voucher_type TEXT NOT NULL,
        party TEXT,
        description TEXT,
        account_dr TEXT NOT NULL,
        account_cr TEXT NOT NULL,
        amount REAL NOT NULL DEFAULT 0,
        gst_amount REAL DEFAULT 0,
        gst_rate REAL DEFAULT 0,
        igst REAL DEFAULT 0,
        cgst REAL DEFAULT 0,
        sgst REAL DEFAULT 0,
        hsn_sac TEXT,
        invoice_no TEXT,
        place_of_supply TEXT,
        reverse_charge INTEGER DEFAULT 0,
        total REAL NOT NULL DEFAULT 0,
        narration TEXT,
        tags TEXT,
        source TEXT DEFAULT 'manual',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS parties (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id INTEGER DEFAULT 1,
        name TEXT NOT NULL,
        type TEXT DEFAULT 'both',
        gstin TEXT,
        pan TEXT,
        phone TEXT,
        email TEXT,
        address TEXT,
        state TEXT,
        opening_balance REAL DEFAULT 0,
        opening_type TEXT DEFAULT 'Dr',
        notes TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id INTEGER DEFAULT 1,
        name TEXT NOT NULL UNIQUE,
        group_name TEXT NOT NULL,
        type TEXT NOT NULL,
        opening_balance REAL DEFAULT 0,
        opening_type TEXT DEFAULT 'Dr',
        notes TEXT
    );

    CREATE INDEX IF NOT EXISTS idx_txn_date ON transactions(date);
    CREATE INDEX IF NOT EXISTS idx_txn_party ON transactions(party);
    CREATE INDEX IF NOT EXISTS idx_txn_type ON transactions(voucher_type);
    CREATE INDEX IF NOT EXISTS idx_txn_company ON transactions(company_id);
    """)

    # Seed default accounts if empty
    count = c.execute("SELECT COUNT(*) FROM accounts").fetchone()[0]
    if count == 0:
        default_accounts = [
            # (name, group, type)
            ("Cash",                  "Cash & Bank",       "Asset"),
            ("Bank",                  "Cash & Bank",       "Asset"),
            ("Accounts Receivable",   "Sundry Debtors",    "Asset"),
            ("GST Receivable",        "Tax Assets",        "Asset"),
            ("Input CGST",            "Tax Assets",        "Asset"),
            ("Input SGST",            "Tax Assets",        "Asset"),
            ("Input IGST",            "Tax Assets",        "Asset"),
            ("Fixed Assets",          "Fixed Assets",      "Asset"),
            ("Accounts Payable",      "Sundry Creditors",  "Liability"),
            ("GST Payable",           "Tax Liabilities",   "Liability"),
            ("Output CGST",           "Tax Liabilities",   "Liability"),
            ("Output SGST",           "Tax Liabilities",   "Liability"),
            ("Output IGST",           "Tax Liabilities",   "Liability"),
            ("TDS Payable",           "Tax Liabilities",   "Liability"),
            ("Loans",                 "Loans & Borrowings","Liability"),
            ("Capital",               "Capital",           "Equity"),
            ("Retained Earnings",     "Reserves",          "Equity"),
            ("Sales Revenue",         "Direct Income",     "Income"),
            ("Other Income",          "Indirect Income",   "Income"),
            ("Interest Income",       "Indirect Income",   "Income"),
            ("Purchase",              "Direct Expense",    "Expense"),
            ("Salary",                "Indirect Expense",  "Expense"),
            ("Rent",                  "Indirect Expense",  "Expense"),
            ("Utilities",             "Indirect Expense",  "Expense"),
            ("Marketing",             "Indirect Expense",  "Expense"),
            ("Travel",                "Indirect Expense",  "Expense"),
            ("Professional Fees",     "Indirect Expense",  "Expense"),
            ("Bank Charges",          "Indirect Expense",  "Expense"),
            ("Depreciation",          "Indirect Expense",  "Expense"),
            ("Other Expense",         "Indirect Expense",  "Expense"),
        ]
        c.executemany(
            "INSERT OR IGNORE INTO accounts (name, group_name, type) VALUES (?,?,?)",
            default_accounts
        )

    # Seed default company if empty
    comp = c.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
    if comp == 0:
        c.execute("""INSERT INTO companies (name, gstin, state)
                     VALUES ('My Business', '', 'Goa')""")

    conn.commit()
    conn.close()

# ── COMPANY ───────────────────────────────────────────────────────────────────

def get_company(company_id=1):
    conn = get_conn()
    row = conn.execute("SELECT * FROM companies WHERE id=?", (company_id,)).fetchone()
    conn.close()
    return dict(row) if row else {}

def save_company(data, company_id=1):
    conn = get_conn()
    conn.execute("""UPDATE companies SET name=?,gstin=?,pan=?,address=?,state=?,email=?,phone=?,fy_start=?
                    WHERE id=?""",
                 (data["name"],data.get("gstin",""),data.get("pan",""),data.get("address",""),
                  data.get("state",""),data.get("email",""),data.get("phone",""),
                  data.get("fy_start","04"), company_id))
    conn.commit(); conn.close()

# ── TRANSACTIONS ──────────────────────────────────────────────────────────────

def add_transaction(txn: dict, company_id=1):
    conn = get_conn()
    conn.execute("""INSERT INTO transactions
        (company_id,date,voucher_no,voucher_type,party,description,account_dr,account_cr,
         amount,gst_amount,gst_rate,igst,cgst,sgst,hsn_sac,invoice_no,place_of_supply,
         reverse_charge,total,narration,tags,source)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (company_id, txn["date"], txn.get("voucher_no",""), txn["voucher_type"],
         txn.get("party",""), txn.get("description",""), txn["account_dr"], txn["account_cr"],
         txn["amount"], txn.get("gst_amount",0), txn.get("gst_rate",0),
         txn.get("igst",0), txn.get("cgst",0), txn.get("sgst",0),
         txn.get("hsn_sac",""), txn.get("invoice_no",""), txn.get("place_of_supply",""),
         txn.get("reverse_charge",0), txn.get("total", txn["amount"]),
         txn.get("narration",""), txn.get("tags",""), txn.get("source","manual")))
    conn.commit(); conn.close()

def bulk_insert(txns: list, company_id=1):
    conn = get_conn()
    conn.executemany("""INSERT INTO transactions
        (company_id,date,voucher_no,voucher_type,party,description,account_dr,account_cr,
         amount,gst_amount,gst_rate,igst,cgst,sgst,hsn_sac,invoice_no,place_of_supply,
         reverse_charge,total,narration,tags,source)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        [(company_id, t["date"], t.get("voucher_no",""), t["voucher_type"],
          t.get("party",""), t.get("description",""), t["account_dr"], t["account_cr"],
          t["amount"], t.get("gst_amount",0), t.get("gst_rate",0),
          t.get("igst",0), t.get("cgst",0), t.get("sgst",0),
          t.get("hsn_sac",""), t.get("invoice_no",""), t.get("place_of_supply",""),
          t.get("reverse_charge",0), t.get("total", t["amount"]),
          t.get("narration",""), t.get("tags",""), t.get("source","upload"))
         for t in txns])
    conn.commit(); conn.close()

def get_transactions(company_id=1, start=None, end=None, voucher_type=None,
                     party=None, account=None):
    conn = get_conn()
    q = "SELECT * FROM transactions WHERE company_id=?"
    params = [company_id]
    if start:         q += " AND date>=?";          params.append(start)
    if end:           q += " AND date<=?";           params.append(end)
    if voucher_type:  q += " AND voucher_type=?";   params.append(voucher_type)
    if party:         q += " AND party LIKE ?";     params.append(f"%{party}%")
    if account:       q += " AND (account_dr=? OR account_cr=?)"; params += [account,account]
    q += " ORDER BY date, id"
    rows = conn.execute(q, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def update_transaction(txn_id, data):
    conn = get_conn()
    conn.execute("""UPDATE transactions SET
        date=?,voucher_type=?,party=?,description=?,account_dr=?,account_cr=?,
        amount=?,gst_amount=?,gst_rate=?,igst=?,cgst=?,sgst=?,
        invoice_no=?,hsn_sac=?,total=?,narration=?,updated_at=CURRENT_TIMESTAMP
        WHERE id=?""",
        (data["date"],data["voucher_type"],data.get("party",""),data.get("description",""),
         data["account_dr"],data["account_cr"],data["amount"],data.get("gst_amount",0),
         data.get("gst_rate",0),data.get("igst",0),data.get("cgst",0),data.get("sgst",0),
         data.get("invoice_no",""),data.get("hsn_sac",""),
         data.get("total",data["amount"]),data.get("narration",""),txn_id))
    conn.commit(); conn.close()

def delete_transaction(txn_id):
    conn = get_conn()
    conn.execute("DELETE FROM transactions WHERE id=?", (txn_id,))
    conn.commit(); conn.close()

# ── PARTIES ───────────────────────────────────────────────────────────────────

def get_parties(company_id=1):
    conn = get_conn()
    rows = conn.execute("SELECT * FROM parties WHERE company_id=? ORDER BY name",
                        (company_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def upsert_party(data, company_id=1):
    conn = get_conn()
    existing = conn.execute("SELECT id FROM parties WHERE company_id=? AND name=?",
                            (company_id, data["name"])).fetchone()
    if existing:
        conn.execute("""UPDATE parties SET gstin=?,pan=?,phone=?,email=?,address=?,state=?,
                        type=?,notes=? WHERE id=?""",
                     (data.get("gstin",""),data.get("pan",""),data.get("phone",""),
                      data.get("email",""),data.get("address",""),data.get("state",""),
                      data.get("type","both"),data.get("notes",""),existing[0]))
    else:
        conn.execute("""INSERT INTO parties (company_id,name,gstin,pan,phone,email,address,state,type)
                        VALUES (?,?,?,?,?,?,?,?,?)""",
                     (company_id,data["name"],data.get("gstin",""),data.get("pan",""),
                      data.get("phone",""),data.get("email",""),data.get("address",""),
                      data.get("state",""),data.get("type","both")))
    conn.commit(); conn.close()

# ── ACCOUNTS ──────────────────────────────────────────────────────────────────

def get_accounts():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM accounts ORDER BY type, name").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_account_names():
    return [a["name"] for a in get_accounts()]

# ── REPORTS ───────────────────────────────────────────────────────────────────

def get_ledger_summary(company_id=1, start=None, end=None):
    txns = get_transactions(company_id, start, end)
    from collections import defaultdict
    summary = defaultdict(lambda: {"dr":0.0,"cr":0.0})
    accounts = {a["name"]: a for a in get_accounts()}
    for t in txns:
        summary[t["account_dr"]]["dr"] += t["amount"]
        summary[t["account_cr"]]["cr"] += t["amount"]
    result = {}
    for acc, vals in summary.items():
        info = accounts.get(acc, {"type":"Other","group_name":"Other"})
        atype = info["type"] if isinstance(info,dict) else "Other"
        bal = (vals["dr"]-vals["cr"]) if atype in ("Asset","Expense") else (vals["cr"]-vals["dr"])
        result[acc] = {"type":atype,"group":info.get("group_name","Other") if isinstance(info,dict) else "Other",
                       "dr":round(vals["dr"],2),"cr":round(vals["cr"],2),"bal":round(bal,2)}
    return result

def get_party_ledger(party_name, company_id=1, start=None, end=None):
    txns = get_transactions(company_id, start, end, party=party_name)
    running = 0.0
    rows = []
    for t in txns:
        # Money in = debit to receivable/bank, Money out = credit
        dr = t["amount"] if t["account_dr"] in ("Accounts Receivable","Bank","Cash") else 0
        cr = t["amount"] if t["account_cr"] in ("Accounts Receivable","Bank","Cash") else 0
        # Fallback: use total
        if dr == 0 and cr == 0:
            if t["voucher_type"] in ("Sales","Receipt"):   dr = t["total"]
            else:                                           cr = t["total"]
        running += dr - cr
        rows.append({**t, "party_dr": round(dr,2), "party_cr": round(cr,2),
                     "running_bal": round(running,2)})
    return rows, round(running, 2)
