"""
HW4 Part A - Audit / profile the eight raw Wildcat Capital tables.

Outputs
  reports/profile_raw.csv     one row per table x column (generic profile)
  reports/dq_summary_raw.csv  one row per finding, tagged ERROR / WARN / INFO

Run from anywhere:  python scripts/01_profile.py
All files are read as text (dtype=str, keep_default_na=False) and converted on purpose.
"""
from pathlib import Path
import re

import numpy as np
import pandas as pd

from market_calendar import NYSE_HOLIDAYS  # NYSE full-day closures 2020-2024 (reference data)

HW = Path(__file__).resolve().parent.parent
RAW = HW / "data" / "raw"
REPORTS = HW / "reports"
REPORTS.mkdir(parents=True, exist_ok=True)

TABLES = ["dim_advisor", "dim_benchmark", "dim_client", "dim_date", "dim_security",
          "fact_fees", "fact_portfolio_snapshot", "fact_transactions"]

# Primary keys, foreign keys (10 ID-based + 3 date-based relationships)
PRIMARY_KEYS = {
    "dim_advisor": "advisor_id", "dim_benchmark": "benchmark_id", "dim_client": "client_id",
    "dim_date": "date_id", "dim_security": "security_id", "fact_fees": "fee_id",
    "fact_portfolio_snapshot": "snapshot_id", "fact_transactions": "txn_id",
}
RELATIONSHIPS = [  # (child table, child column, parent table, parent column)
    ("dim_client", "advisor_id", "dim_advisor", "advisor_id"),
    ("dim_security", "benchmark_id", "dim_benchmark", "benchmark_id"),
    ("fact_fees", "client_id", "dim_client", "client_id"),
    ("fact_fees", "advisor_id", "dim_advisor", "advisor_id"),
    ("fact_portfolio_snapshot", "client_id", "dim_client", "client_id"),
    ("fact_portfolio_snapshot", "advisor_id", "dim_advisor", "advisor_id"),
    ("fact_portfolio_snapshot", "benchmark_id", "dim_benchmark", "benchmark_id"),
    ("fact_transactions", "client_id", "dim_client", "client_id"),
    ("fact_transactions", "advisor_id", "dim_advisor", "advisor_id"),
    ("fact_transactions", "security_id", "dim_security", "security_id"),
    ("fact_fees", "fee_date", "dim_date", "date"),
    ("fact_portfolio_snapshot", "snapshot_date", "dim_date", "date"),
    ("fact_transactions", "txn_date", "dim_date", "date"),
]

NULL_TOKENS = {"", "NONE", "NULL", "NA", "N/A", "NAN", "-", "?"}
US_STATES = {"AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN","IA","KS","KY","LA",
             "ME","MD","MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ","NM","NY","NC","ND","OH","OK",
             "OR","PA","RI","SC","SD","TN","TX","UT","VT","VA","WA","WV","WI","WY","DC"}


def load(name: str) -> pd.DataFrame:
    return pd.read_csv(RAW / f"{name}.csv", dtype=str, keep_default_na=False)


def shape_of(v: str) -> str:
    """Value 'shape': digits->9, upper->A, lower->a (e.g. '2020-01-01' -> '9999-99-99')."""
    v = re.sub(r"\d", "9", v)
    v = re.sub(r"[A-Z]", "A", v)
    return re.sub(r"[a-z]", "a", v)


def infer_type(s: pd.Series) -> str:
    v = s[s.str.strip() != ""]
    if v.empty:
        return "empty"
    if pd.to_numeric(v, errors="coerce").notna().mean() >= 0.95:
        return "numeric"
    if pd.to_datetime(v, errors="coerce", format="%Y-%m-%d").notna().mean() >= 0.95:
        return "date"
    if v.isin(["True", "False", "0", "1"]).all():
        return "boolean"
    return "text"


# ------------------------------------------------------------------ generic profile
def profile_table(df: pd.DataFrame, name: str) -> pd.DataFrame:
    """Generic column profile - works on any table, no column names hard-coded."""
    rows = []
    n = len(df)
    for col in df.columns:
        s = df[col]
        stripped = s.str.strip()
        blank = (stripped == "").sum()
        null_token = stripped.str.upper().isin(NULL_TOKENS - {""}).sum()
        shapes = s.map(shape_of).value_counts()
        typ = infer_type(s)
        nonblank = s[stripped != ""]
        num = pd.to_numeric(nonblank, errors="coerce")
        if typ == "numeric":
            fail = num.isna().sum()
        elif typ == "date":
            fail = pd.to_datetime(nonblank, errors="coerce", format="%Y-%m-%d").isna().sum()
        else:
            fail = 0
        # mixed formats: dates/numbers with >1 shape family, or a low-cardinality text column
        # that mixes short ALL-CAPS codes with Title-case words (e.g. 'PA' vs 'Pennsylvania')
        mixed_n = 0
        symbol = nonblank.str.contains(r"[%$,]").sum() if typ == "numeric" else 0
        if typ == "date":
            mixed = len(shapes) > 1
            mixed_n = n - shapes.iloc[0]
        elif typ == "numeric":
            mixed = symbol > 0
            mixed_n = symbol
        elif typ == "text" and s.nunique() <= 60:
            code = nonblank.str.fullmatch(r"[A-Z]{2,3}")
            word = nonblank.str.fullmatch(r"[A-Z][a-z]+( [A-Z][a-z]+)*")
            mixed = code.mean() > 0.01 and word.mean() > 0.005 and code.mean() > 0.5
            mixed_n = int((~code).sum())
        else:
            mixed, mixed_n = False, 0
        rows.append({
            "table": name, "column": col, "rows": n,
            "inferred_type": typ,
            "blank_count": int(blank), "blank_pct": round(blank / n * 100, 2) if n else 0,
            "null_token_count": int(null_token),
            "distinct_count": int(s.nunique()),
            "is_unique": bool(s.nunique() == n),
            "top_shapes": "; ".join(f"{k or '<blank>'} ({v})" for k, v in shapes.head(4).items()),
            "shape_count": int(len(shapes)),
            "mixed_format": bool(mixed),
            "mixed_format_count": int(mixed_n) if mixed else 0,
            "symbol_in_numeric": int(symbol),
            "parse_fail_count": int(fail),
            "parse_fail_pct": round(fail / max(len(nonblank), 1) * 100, 2),
            "whitespace_issues": int((s != stripped).sum()),
            "numeric_min": num.min() if typ == "numeric" else None,
            "numeric_max": num.max() if typ == "numeric" else None,
            "top_values": "; ".join(f"{k or '<blank>'} ({v})" for k, v in s.value_counts().head(5).items()),
        })
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ findings
FINDINGS = []


def add(table, column, group, check, severity, count, total, example=""):
    if count == 0 and severity != "INFO":
        return
    FINDINGS.append({
        "table": table, "column": column, "check_group": group, "check": check,
        "severity": severity, "count": int(count),
        "pct_of_rows": round(count / total * 100, 3) if total else 0,
        "example": str(example)[:200],
    })


def num(s):
    return pd.to_numeric(s, errors="coerce")


def main():
    t = {name: load(name) for name in TABLES}

    # ---- generic profile for every table
    profile = pd.concat([profile_table(df, name) for name, df in t.items()], ignore_index=True)
    profile.to_csv(REPORTS / "profile_raw.csv", index=False)
    print(f"profile_raw.csv: {len(profile)} column profiles across {len(t)} tables")

    # ---- 1. COLUMN LEVEL (generic, driven by the profile) ----------------
    for _, p in profile.iterrows():
        tb, c, n = p.table, p.column, p.rows
        if p.blank_count:
            add(tb, c, "1 column", "blank values", "WARN", p.blank_count, n,
                "blank cells - decide if defect or legitimate")
        if p.null_token_count:
            add(tb, c, "1 column", "null-like text token (e.g. 'None')", "WARN", p.null_token_count, n,
                p.top_values)
        if p.parse_fail_count:
            bad = t[tb][c][pd.to_numeric(t[tb][c], errors="coerce").isna() & (t[tb][c] != "")]
            add(tb, c, "1 column", f"values failing {p.inferred_type} parse", "ERROR", p.parse_fail_count, n,
                bad.head(3).tolist())
        if p.symbol_in_numeric:
            add(tb, c, "1 column", "numeric column contains % / $ / , text", "ERROR", p.symbol_in_numeric, n)
        if p.whitespace_issues:
            add(tb, c, "1 column", "leading/trailing whitespace", "WARN", p.whitespace_issues, n)
        if p.mixed_format:
            add(tb, c, "1 column", "mixed formats (minority-format values)", "WARN", p.mixed_format_count, n, p.top_shapes)
    # key uniqueness
    for tb, pk in PRIMARY_KEYS.items():
        dups = t[tb][pk].duplicated(keep=False).sum()
        add(tb, pk, "1 column", "primary key not unique", "ERROR", dups, len(t[tb]))
        if dups == 0:
            add(tb, pk, "1 column", "primary key unique", "INFO", 0, len(t[tb]),
                f"{t[tb][pk].nunique()} distinct of {len(t[tb])}")
    # ID columns stored as floats ('45.0') - breaks text joins
    for tb, df in t.items():
        for c in [c for c in df.columns if c.endswith("_id")]:
            bad = df[c].str.fullmatch(r"\d+\.0").sum()
            add(tb, c, "1 column", "ID stored as float text (e.g. '45.0')", "ERROR", bad, len(df),
                df[c][df[c].str.fullmatch(r"\d+\.0")].head(3).tolist())

    # allowed values / ranges (business rules)
    cl = t["dim_client"]
    bad_state = ~cl.state.isin(US_STATES)
    add("dim_client", "state", "1 column", "state not a 2-letter USPS code", "ERROR", bad_state.sum(), len(cl),
        cl.state[bad_state].value_counts().to_dict())
    add("dim_client", "zip_code", "1 column", "zip not 5 digits", "ERROR",
        (~cl.zip_code.str.fullmatch(r"\d{5}")).sum(), len(cl))
    add("dim_client", "zip_code", "1 column", "zip with leading zero (must stay text)", "INFO",
        cl.zip_code.str.startswith("0").sum(), len(cl), "read as text so zeros are preserved")
    age = num(cl.age)
    add("dim_client", "age", "1 column", "age outside 18-100", "ERROR", ((age < 18) | (age > 100)).sum(), len(cl))
    add("dim_client", "risk_profile", "1 column", "risk_profile not in allowed list", "ERROR",
        (~cl.risk_profile.isin(["Conservative", "Moderately Conservative", "Balanced",
                                "Moderately Aggressive", "Aggressive", ""])).sum(), len(cl))
    add("dim_client", "initial_aum", "1 column", "initial_aum <= 0", "ERROR", (num(cl.initial_aum) <= 0).sum(), len(cl))

    sec = t["dim_security"]
    er = num(sec.expense_ratio_bps)
    add("dim_security", "expense_ratio_bps", "1 column", "expense ratio outside 0-300 bps", "ERROR",
        ((er < 0) | (er > 300)).sum(), len(sec))

    fee = t["fact_fees"]
    for c in ["aum_basis", "amount", "bps_charged"]:
        add("fact_fees", c, "1 column", f"{c} <= 0", "ERROR", (num(fee[c]) <= 0).sum(), len(fee))
    add("fact_fees", "bps_charged", "1 column", "bps_charged > 100 (above typical fee schedule)", "WARN",
        (num(fee.bps_charged) > 100).sum(), len(fee), fee.bps_charged[num(fee.bps_charged) > 100].tolist())
    add("fact_fees", "fee_date", "1 column", "fee_date not 1st of month", "WARN",
        (fee.fee_date.str[-2:] != "01").sum(), len(fee))

    sn = t["fact_portfolio_snapshot"]
    cash = num(sn.cash_pct)
    add("fact_portfolio_snapshot", "cash_pct", "1 column", "cash_pct outside 0-1", "ERROR",
        ((cash < 0) | (cash > 1)).sum(), len(sn))
    aum = num(sn.aum)
    add("fact_portfolio_snapshot", "aum", "1 column", "aum <= 0", "ERROR", (aum <= 0).sum(), len(sn))
    add("fact_portfolio_snapshot", "aum", "1 column", "aum exactly 1,000.00 (looks like a floor value)", "WARN",
        (aum == 1000).sum(), len(sn), f"{sn.client_id[aum == 1000].nunique()} clients")
    ret = num(sn.return_ytd)
    add("fact_portfolio_snapshot", "return_ytd", "1 column", "return_ytd > +100% or < -50% (implausible)", "WARN",
        ((ret > 1) | (ret < -0.5)).sum(), len(sn), f"min {ret.min()}, max {ret.max()}")

    tx = t["fact_transactions"]
    sh, px, amt = num(tx.shares), num(tx.price), num(tx.amount)
    neg = sh < 0
    neg_reconciles = (neg & ((sh.abs() * px - amt).abs() <= 0.01)).sum()   # computed, not assumed
    add("fact_transactions", "shares", "1 column", "negative shares", "ERROR", neg.sum(), len(tx),
        f"txn_types {tx.txn_type[neg].value_counts().to_dict()}; "
        f"{neg_reconciles} of {neg.sum()} reconcile as |shares| x price == amount (sign error only)")
    add("fact_transactions", "amount", "1 column", "amount <= 0", "ERROR", (amt <= 0).sum(), len(tx))
    add("fact_transactions", "price", "1 column", "price <= 0", "ERROR", (px <= 0).sum(), len(tx))
    add("fact_transactions", "txn_type", "1 column", "txn_type values", "INFO", 0, len(tx),
        tx.txn_type.value_counts().to_dict())

    # ---- 2. SINGLE-TABLE RULES -------------------------------------------
    for tb, df in t.items():
        pk = PRIMARY_KEYS[tb]
        full_dup = df.duplicated(df.columns.drop(pk).tolist(), keep=False).sum()
        add(tb, "(all)", "2 single-table", "exact duplicate rows (ignoring PK)", "ERROR", full_dup, len(df))
    # near-duplicate clients: same age, zip, initial_aum, client_since, advisor
    nd_cols = ["age", "zip_code", "initial_aum", "client_since", "advisor_id"]
    nd = cl.duplicated(nd_cols, keep=False)
    ex = cl[nd].sort_values(nd_cols)[["client_id", "first_name", "last_name"]].head(4).values.tolist()
    add("dim_client", "client_id", "2 single-table", "near-duplicate clients (same age/zip/AUM/since/advisor)",
        "ERROR", nd.sum(), len(cl), ex)
    # tier vs initial AUM bands
    ia = num(cl.initial_aum)
    tier_bad = ((cl.client_tier == "Retail") & (ia >= 500_000)) | \
               ((cl.client_tier == "HNW") & ((ia < 500_000) | (ia >= 5_000_000))) | \
               ((cl.client_tier == "UHNW") & (ia < 5_000_000))
    add("dim_client", "client_tier", "2 single-table", "tier inconsistent with initial_aum band", "WARN",
        tier_bad.sum(), len(cl))
    # security: ETF flag vs sector / expense ratio / name
    add("dim_security", "sector", "2 single-table", "sector blank only for ETFs (legitimate structure)", "INFO",
        ((sec.sector == "") & (sec.is_etf == "True")).sum(), len(sec))
    add("dim_security", "sector", "2 single-table", "sector blank for a non-ETF", "ERROR",
        ((sec.sector == "") & (sec.is_etf == "False")).sum(), len(sec))
    add("dim_security", "expense_ratio_bps", "2 single-table", "expense ratio blank for a fund", "ERROR",
        ((sec.expense_ratio_bps == "") & (sec.is_etf == "True")).sum(), len(sec))
    add("dim_security", "name", "2 single-table", "duplicate security names with different tickers", "INFO",
        sec.name.duplicated(keep=False).sum(), len(sec), sec.name[sec.name.duplicated()].tolist())
    # date dimension self-consistency
    dt = t["dim_date"]
    d = pd.to_datetime(dt.date, format="%Y-%m-%d")
    for c, exp in [("year", d.dt.year.astype(str)), ("month", d.dt.month.astype(str)),
                   ("quarter", d.dt.quarter.astype(str)), ("day_of_week", d.dt.day_name()),
                   ("month_name", d.dt.month_name()),
                   ("week_of_year", d.dt.isocalendar().week.astype(str)),
                   ("is_month_end", d.dt.is_month_end.astype(int).astype(str)),
                   ("is_quarter_end", d.dt.is_quarter_end.astype(int).astype(str)),
                   ("is_year_end", d.dt.is_year_end.astype(int).astype(str))]:
        add("dim_date", c, "2 single-table", f"{c} disagrees with date", "ERROR", (dt[c] != exp).sum(), len(dt))
    add("dim_date", "is_trading_day", "2 single-table", "weekend marked as trading day", "ERROR",
        ((d.dt.dayofweek >= 5) & (dt.is_trading_day == "1")).sum(), len(dt))
    hol = dt.date.isin(NYSE_HOLIDAYS) & (dt.is_trading_day == "1")
    add("dim_date", "is_trading_day", "2 single-table", "NYSE market holiday marked as trading day", "ERROR",
        hol.sum(), len(dt), dt.date[hol].head(4).tolist())
    add("dim_date", "date", "2 single-table", "calendar gaps (missing days between min and max date)", "ERROR",
        (d.max() - d.min()).days + 1 - d.nunique(), len(dt))
    # fees: amount = aum_basis * bps / 10000 / 12
    calc = num(fee.aum_basis) * num(fee.bps_charged) / 10000 / 12
    add("fact_fees", "amount", "2 single-table", "amount != aum_basis x bps / 10000 / 12 (>$0.01)", "ERROR",
        ((num(fee.amount) - calc).abs() > 0.01).sum(), len(fee))
    add("fact_fees", "fee_type", "2 single-table", "fee_type changes month to month for the same client", "INFO",
        (fee.groupby("client_id").fee_type.nunique() > 1).sum(), fee.client_id.nunique(), "clients affected")
    # snapshots: alpha = return - benchmark; year/month = date
    alpha = num(sn.return_ytd) - num(sn.benchmark_return_ytd) - num(sn.active_alpha_ytd)
    add("fact_portfolio_snapshot", "active_alpha_ytd", "2 single-table", "alpha != return - benchmark return",
        "ERROR", (alpha.abs() > 1e-5).sum(), len(sn))
    add("fact_portfolio_snapshot", "year", "2 single-table", "year/month disagree with snapshot_date", "ERROR",
        ((sn.snapshot_date.str[:4] != sn.year) |
         (sn.snapshot_date.str[5:7].astype(int).astype(str) != sn.month)).sum(), len(sn))
    add("fact_portfolio_snapshot", "client_id", "2 single-table", "duplicate client + snapshot_date", "ERROR",
        sn.duplicated(["client_id", "snapshot_date"], keep=False).sum(), len(sn))
    # transactions: security fields present only for security txn types; shares x price = amount
    is_sec = tx.txn_type.isin(["Buy", "Sell", "Dividend"])
    add("fact_transactions", "security_id", "2 single-table", "security txn missing security_id", "ERROR",
        (is_sec & (tx.security_id == "")).sum(), len(tx))
    add("fact_transactions", "security_id", "2 single-table", "cash txn (deposit/withdrawal/fee) blank security - legitimate",
        "INFO", (~is_sec & (tx.security_id == "")).sum(), len(tx))
    # amount check uses |shares| so the 836 negative-share rows (already reported above) are not double counted
    mism = is_sec & ((sh.abs() * px - amt).abs() > 0.01)
    add("fact_transactions", "amount", "2 single-table", "|shares| x price != amount", "ERROR", mism.sum(), len(tx))
    add("fact_transactions", "amount", "2 single-table", "|shares| x price reconciles to amount", "INFO",
        (is_sec & ~mism).sum(), int(is_sec.sum()), f"{(is_sec & ~mism).sum()} of {is_sec.sum()} security txns")

    # ---- 3. REFERENTIAL INTEGRITY ----------------------------------------
    for child, ccol, parent, pcol in RELATIONSHIPS:
        fk = t[child][ccol]
        fk_norm = fk.str.replace(r"\.0$", "", regex=True)
        nonnull = fk != ""
        orphan_raw = nonnull & ~fk.isin(t[parent][pcol])
        orphan_norm = nonnull & ~fk_norm.isin(t[parent][pcol])
        add(child, ccol, "3 referential", f"orphan FK -> {parent}.{pcol} (exact text match)", "ERROR",
            orphan_raw.sum(), len(fk), fk[orphan_raw].drop_duplicates().head(5).tolist())
        if orphan_norm.sum() != orphan_raw.sum():
            # report what removing '.0' resolves, even when nothing is left over
            resolved = orphan_raw.sum() - orphan_norm.sum()
            add(child, ccol, "3 referential", f"orphans that DO match {parent}.{pcol} once '.0' is removed "
                f"(format issue, fixable)", "INFO", resolved, len(fk),
                f"{resolved} of {orphan_raw.sum()} resolved; {orphan_norm.sum()} remain")
            add(child, ccol, "3 referential", f"orphan FK -> {parent}.{pcol} after removing '.0'", "ERROR",
                orphan_norm.sum(), len(fk), fk[orphan_norm].drop_duplicates().head(5).tolist())
    # parents never referenced by any child table
    used_clients = set(t["fact_fees"].client_id) | set(sn.client_id) | set(tx.client_id)
    add("dim_client", "client_id", "3 referential", "client with no fees, snapshots or transactions", "WARN",
        (~cl.client_id.isin(used_clients)).sum(), len(cl), cl.client_id[~cl.client_id.isin(used_clients)].head(5).tolist())
    used_bm = set(sn.benchmark_id) | set(sec.benchmark_id)
    add("dim_benchmark", "benchmark_id", "3 referential", "benchmark never referenced", "INFO",
        (~t["dim_benchmark"].benchmark_id.isin(used_bm)).sum(), 8,
        t["dim_benchmark"].name[~t["dim_benchmark"].benchmark_id.isin(used_bm)].tolist())

    # ---- 4. CROSS-TABLE BUSINESS RULES -----------------------------------
    cl_adv = dict(zip(cl.client_id, cl.advisor_id))
    for tb in ["fact_fees", "fact_portfolio_snapshot", "fact_transactions"]:
        df = t[tb]
        m = df.client_id.map(cl_adv)
        add(tb, "advisor_id", "4 cross-table", "advisor differs from client's advisor in dim_client", "ERROR",
            (m.notna() & (m != df.advisor_id)).sum(), len(df))
    acct = dict(zip(cl.client_id, cl.primary_account_type))
    add("fact_portfolio_snapshot", "account_type", "4 cross-table", "account_type != client primary_account_type",
        "WARN", (sn.client_id.map(acct).notna() & (sn.client_id.map(acct) != sn.account_type)).sum(), len(sn))
    # blank risk profile vs benchmark assignment
    risk = sn.client_id.map(dict(zip(cl.client_id, cl.risk_profile)))
    xt = pd.crosstab(risk, sn.benchmark_id)
    add("fact_portfolio_snapshot", "benchmark_id", "4 cross-table",
        "benchmark assigned by risk profile (1=Aggr/ModAggr, 3=Balanced, 8=Cons/ModCons); blank-risk clients all on 3",
        "INFO", 0, len(sn), xt.to_dict())
    # fees vs snapshots
    m = fee.merge(sn, left_on=["client_id", "fee_date"], right_on=["client_id", "snapshot_date"], how="left")
    add("fact_fees", "aum_basis", "4 cross-table", "aum_basis != snapshot aum for same client/month", "ERROR",
        ((num(m.aum) - num(m.aum_basis)).abs() > 0.01).sum(), len(fee))
    ms = sn.merge(fee[["client_id", "fee_date"]], left_on=["client_id", "snapshot_date"],
                  right_on=["client_id", "fee_date"], how="left")
    add("fact_portfolio_snapshot", "snapshot_date", "4 cross-table", "snapshot month with no fee charged", "WARN",
        ms.fee_date.isna().sum(), len(sn))
    # return_ytd vs AUM change (is return flow-adjusted?)
    s2 = sn.assign(a=num(sn.aum), r=num(sn.return_ytd), y=sn.year.astype(int), mo=sn.month.astype(int))
    base = s2[s2.mo == 12].assign(y=lambda d: d.y + 1)[["client_id", "y", "a"]].rename(columns={"a": "base"})
    s3 = s2.merge(base, on=["client_id", "y"], how="inner")
    match = ((s3.a / s3.base - 1 - s3.r).abs() < 1e-3).sum()
    add("fact_portfolio_snapshot", "return_ytd", "4 cross-table",
        "return_ytd equals AUM / prior Dec AUM - 1 (not flow-adjusted: deposits/withdrawals count as return)",
        "WARN", match, len(s3), f"{match} of {len(s3)} testable rows")
    # transactions vs client lifecycle
    since = dict(zip(cl.client_id, cl.client_since))
    add("fact_transactions", "txn_date", "4 cross-table", "transaction before client_since", "ERROR",
        (tx.txn_date < tx.client_id.map(since)).sum(), len(tx))
    last = sn.groupby("client_id").snapshot_date.max()
    inactive = set(cl.client_id[cl.is_active == "False"])
    late = tx.client_id.isin(inactive) & (tx.txn_date.str[:7] > tx.client_id.map(last).fillna("9999").str[:7])
    add("fact_transactions", "txn_date", "4 cross-table", "inactive client transacting after last snapshot month",
        "WARN", late.sum(), len(tx))
    trading = dict(zip(dt.date, dt.is_trading_day))
    bs = tx.txn_type.isin(["Buy", "Sell"])
    wk = bs & (tx.txn_date.map(trading) == "0")
    add("fact_transactions", "txn_date", "4 cross-table", "Buy/Sell on a non-trading day (dim_date: weekends)", "WARN",
        wk.sum(), len(tx))
    hol_tx = bs & tx.txn_date.isin(NYSE_HOLIDAYS)
    add("fact_transactions", "txn_date", "4 cross-table", "Buy/Sell on an NYSE market holiday (dim_date misses these)",
        "WARN", hol_tx.sum(), len(tx))
    # advisory fee transactions vs fact_fees
    af = tx[tx.txn_type == "Advisory Fee"].assign(a=num(tx.amount), ym=tx.txn_date.str[:7])
    fm = fee.assign(a=num(fee.amount), ym=fee.fee_date.str[:7]).groupby(["client_id", "ym"]).a.sum()
    am = af.groupby(["client_id", "ym"]).a.sum()
    allj = pd.concat([fm.rename("fee"), am.rename("txn")], axis=1)
    j = allj.dropna()
    add("fact_transactions", "amount", "4 cross-table",
        "Advisory Fee transactions do not reconcile to fact_fees for same client-month", "WARN",
        ((j.fee - j.txn).abs() > 1).sum(), len(j),
        f"{((j.fee - j.txn).abs() <= 1).sum()} of {len(j)} overlapping client-months match; coverage: "
        f"{allj.txn.isna().sum()} fee months have no Advisory Fee txn, {allj.fee.isna().sum()} txn months have no fee row")
    # security benchmark vs asset class
    add("dim_security", "benchmark_id", "4 cross-table", "security benchmark asset class mapping", "INFO", 0, len(sec),
        pd.crosstab(sec.asset_class, sec.benchmark_id).to_dict())

    dq = pd.DataFrame(FINDINGS)
    sev_order = {"ERROR": 0, "WARN": 1, "INFO": 2}
    dq = dq.sort_values(["severity", "table"], key=lambda c: c.map(sev_order) if c.name == "severity" else c)
    dq.to_csv(REPORTS / "dq_summary_raw.csv", index=False)
    print(f"dq_summary_raw.csv: {len(dq)} findings -> {dq.severity.value_counts().to_dict()}")
    print(dq[dq.severity != "INFO"][["severity", "table", "column", "check", "count"]].to_string(index=False))


if __name__ == "__main__":
    main()
