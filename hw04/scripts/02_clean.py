"""
HW4 Part C - Clean the eight Wildcat Capital tables.

Reads data/raw/*.csv (never modified) and writes:
  data/clean/<same 8 file names>    same columns + clearly named 0/1 flag columns
  data/audit/cleaning_log.csv       table, issue, action, rows_affected, note
  data/audit/value_changes.csv      table, key_column, key, column, old_value, new_value
  data/audit/quarantine_*.csv       one file per quarantined set (with reason + traceable keys)

Every step: prints rows affected + a before/after check, and asserts the after-state.
Run from anywhere:  python scripts/02_clean.py
Issue numbers (#) refer to decision_log.md.
"""
from pathlib import Path

import pandas as pd

from market_calendar import NYSE_HOLIDAYS  # NYSE full-day closures 2020-2024 (reference data)

HW = Path(__file__).resolve().parent.parent
RAW, CLEAN, AUDIT = HW / "data" / "raw", HW / "data" / "clean", HW / "data" / "audit"
CLEAN.mkdir(parents=True, exist_ok=True)
AUDIT.mkdir(parents=True, exist_ok=True)

TABLES = ["dim_advisor", "dim_benchmark", "dim_client", "dim_date", "dim_security",
          "fact_fees", "fact_portfolio_snapshot", "fact_transactions"]
PK = {"dim_advisor": "advisor_id", "dim_benchmark": "benchmark_id", "dim_client": "client_id",
      "dim_date": "date_id", "dim_security": "security_id", "fact_fees": "fee_id",
      "fact_portfolio_snapshot": "snapshot_id", "fact_transactions": "txn_id"}

US_STATES = set("AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM "
                "NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY DC".split())
STATE_CODES = {"Pennsylvania": "PA", "Florida": "FL", "New York": "NY", "New Jersey": "NJ",
               "California": "CA", "Illinois": "IL", "Texas": "TX"}

log_rows, change_rows, quarantine_counts = [], [], {}


def num(s):
    return pd.to_numeric(s, errors="coerce")


def log(table, issue, action, rows, note=""):
    log_rows.append({"table": table, "issue": issue, "action": action, "rows_affected": int(rows), "note": note})
    print(f"  [{table}] {issue}: {action} -> {rows:,} rows. {note}")


def record_changes(table, df, mask, column, old, new):
    """Append one value_changes row per changed cell."""
    key = PK[table]
    change_rows.append(pd.DataFrame({
        "table": table, "key_column": key, "key": df.loc[mask, key].values,
        "column": column, "old_value": old[mask].values, "new_value": new[mask].values}))


def quarantine(table, df, mask, name, reason):
    q = df[mask].copy()
    q.insert(0, "quarantine_reason", reason)
    q.to_csv(AUDIT / f"quarantine_{name}.csv", index=False)
    quarantine_counts[table] = quarantine_counts.get(table, 0) + len(q)
    return df[~mask].copy()


def main():
    for old_q in AUDIT.glob("quarantine_*.csv"):   # clear stale quarantine sets from earlier runs
        old_q.unlink()
    raw = {t: pd.read_csv(RAW / f"{t}.csv", dtype=str, keep_default_na=False) for t in TABLES}
    raw_counts = {t: len(df) for t, df in raw.items()}
    t = {k: v.copy() for k, v in raw.items()}

    # ===== STEP 1 - Formats first, so later joins and comparisons work on clean text ==========
    print("\nSTEP 1  standardise formats")

    # #8 fact_transactions.security_id stored as '45.0' -> '45'
    tx = t["fact_transactions"]
    old = tx.security_id.copy()
    mask = old.str.fullmatch(r"\d+\.0")
    before = mask.sum()
    tx["security_id"] = old.str.replace(r"\.0$", "", regex=True)
    record_changes("fact_transactions", tx, mask, "security_id", old, tx.security_id)
    assert not tx.security_id.str.contains(r"\.").any(), "security_id still has decimals"
    assert ((tx.security_id == "") | tx.security_id.isin(t["dim_security"].security_id)).all(), "orphan security_id"
    log("fact_transactions", "#8 security_id stored as float text", "convert to integer text", before,
        f"before: {before:,} '.0' values; after: 0; all non-blank ids now match dim_security")

    # #11 return_ytd stored as '9.28%' text in some rows -> decimal 0.0928, verified against alpha
    sn = t["fact_portfolio_snapshot"]
    old = sn.return_ytd.copy()
    mask = old.str.endswith("%")
    before = mask.sum()
    converted = (num(old[mask].str.rstrip("%")) / 100)
    implied = num(sn.loc[mask, "benchmark_return_ytd"]) + num(sn.loc[mask, "active_alpha_ytd"])
    diff = (converted - implied).abs()
    # the % text is rounded to 2 dp (max error 0.00005); it must agree with benchmark + alpha within that
    assert (diff <= 0.00005 + 1e-9).all(), "converted % does not reconcile to benchmark + alpha"
    # store the full-precision reconciled value (benchmark + alpha), not the rounded % text
    sn.loc[mask, "return_ytd"] = implied.round(6).map(lambda v: f"{v:.6f}".rstrip("0").rstrip("."))
    record_changes("fact_portfolio_snapshot", sn, mask, "return_ytd", old, sn.return_ytd)
    assert num(sn.return_ytd).notna().all(), "return_ytd still has unparseable values"
    alpha_gap = (num(sn.return_ytd) - num(sn.benchmark_return_ytd) - num(sn.active_alpha_ytd)).abs()
    assert (alpha_gap[mask] <= 1e-6).all(), "converted rows do not satisfy alpha = return - benchmark"
    log("fact_portfolio_snapshot", "#11 return_ytd stored as percent text",
        "replace with benchmark_return_ytd + active_alpha_ytd (full precision)", before,
        f"verified: all {before} % values agree with benchmark + alpha within rounding (max diff {diff.max():.1e}); "
        f"after: alpha = return - benchmark holds for all {before} rows to 1e-6")

    # #1 dim_client.state full names -> USPS codes
    cl = t["dim_client"]
    old = cl.state.copy()
    mask = old.isin(STATE_CODES)
    before = mask.sum()
    cl["state"] = old.replace(STATE_CODES)
    record_changes("dim_client", cl, mask, "state", old, cl.state)
    unmapped = sorted(set(cl.state) - US_STATES)
    assert not unmapped, f"state values not in the USPS list: {unmapped}"
    log("dim_client", "#1 state spelled out instead of USPS code", "standardise", before,
        f"before: {old.nunique()} distinct values; after: {cl.state.nunique()}")

    # #22 dim_date.is_trading_day = 1 on NYSE market holidays -> 0 (verified against the NYSE calendar)
    dt = t["dim_date"]
    old = dt.is_trading_day.copy()
    mask = dt.date.isin(NYSE_HOLIDAYS) & (old == "1")
    before = mask.sum()
    assert (pd.to_datetime(dt.date[mask]).dt.dayofweek < 5).all(), "holiday list contains a weekend date"
    dt.loc[mask, "is_trading_day"] = "0"
    record_changes("dim_date", dt, mask, "is_trading_day", old, dt.is_trading_day)
    assert (dt.is_trading_day[dt.date.isin(NYSE_HOLIDAYS)] == "0").all()
    log("dim_date", "#22 NYSE holidays marked as trading days", "set is_trading_day = 0", before,
        f"before: {(old == '1').sum():,} trading days; after: {(dt.is_trading_day == '1').sum():,} "
        f"(all {len(NYSE_HOLIDAYS)} NYSE full-day closures 2020-2024)")

    # ===== STEP 2 - Duplicates (before filling, so fills are not wasted on rows we remove) =====
    print("\nSTEP 2  de-duplicate dim_client")
    # #3 near-duplicate clients: truncated last name, identical age/zip/AUM/since/advisor
    match_cols = ["age", "zip_code", "initial_aum", "client_since", "advisor_id"]
    assert cl.client_id.str.fullmatch(r"\d+").all(), "non-numeric client_id - cannot order records"
    cl["_id"] = cl.client_id.astype(int)
    originals = cl.sort_values("_id").drop_duplicates(match_cols, keep="first")
    dup_mask = ~cl.index.isin(originals.index)
    other_cols = [c for c in cl.columns if c not in match_cols + ["client_id", "_id", "last_name"]]
    dups = cl[dup_mask].merge(originals[match_cols + other_cols + ["client_id", "last_name"]], on=match_cols,
                              suffixes=("", "_original"))
    fact_clients = (set(t["fact_fees"].client_id) | set(sn.client_id) | set(tx.client_id))
    # verify each pair directly (not via name prefixes):
    assert (dups.groupby("client_id_original").size() == 1).all(), "more than 2 records in a duplicate group"
    for c in other_cols:   # every other column identical, including first_name
        assert (dups[c] == dups[f"{c}_original"]).all(), f"duplicate pair differs on {c}"
    # last names differ by exactly one trailing letter (e.g. Taylo/Taylor, Leen/Lee)
    short = dups[["last_name", "last_name_original"]].apply(lambda r: min(r, key=len), axis=1)
    long_ = dups[["last_name", "last_name_original"]].apply(lambda r: max(r, key=len), axis=1)
    assert ((long_.str.len() - short.str.len() == 1) & (long_.str[:-1] == short)).all(), \
        "duplicate last_name does not differ from the kept one by exactly one trailing letter"
    assert not dups.client_id.isin(fact_clients).any(), "the record being quarantined has facts - cannot drop"
    assert dups.client_id_original.isin(fact_clients).all(), "the record being kept has no facts - wrong side kept"
    cl = cl.merge(dups[["client_id", "client_id_original"]], on="client_id", how="left")
    before = len(cl)
    cl = quarantine("dim_client", cl.drop(columns="_id"), cl.client_id_original.notna(),
                    "dim_client_near_duplicates",
                    "near-duplicate of client_id_original (last_name off by one letter, every other field identical); no facts reference it")
    cl = cl.drop(columns="client_id_original")
    assert not cl.duplicated(match_cols).any()
    log("dim_client", "#3 near-duplicate client records", "quarantine", before - len(cl),
        f"before: {before:,} rows; after: {len(cl):,}; none referenced by any fact table")

    # ===== STEP 3 - Missing risk profiles: test whether another table proves the value =======
    print("\nSTEP 3  blank risk_profile: test the benchmark inference, then flag")
    # #2 Every blank-profile client is on benchmark 3 (60/40). That LOOKS like proof of 'Balanced', but if
    #    blanks were Balanced at the firm's normal rate, 75 of 75 on benchmark 3 would be essentially impossible.
    #    So benchmark 3 is most likely the system DEFAULT for a missing profile: the inference is circular.
    #    Decision: do not fill; keep blank and flag (revised after Claude Code review).
    blank = cl.risk_profile == ""
    client_bms = sn.groupby("client_id").benchmark_id.unique()
    on_bm3 = blank & cl.client_id.map(lambda c: list(client_bms.get(c, [])) == ["3"])
    known = cl[~blank]
    balanced_share = (known.risk_profile == "Balanced").mean()
    p_chance = balanced_share ** on_bm3.sum()
    assert on_bm3.sum() == blank.sum(), "some blank-profile clients are not on benchmark 3 - re-check"
    cl["flag_risk_profile_missing"] = blank.astype(int)
    assert cl.flag_risk_profile_missing.sum() == (cl.risk_profile == "").sum()
    log("dim_client", "#2 blank risk_profile", "leave blank + flag_risk_profile_missing=1", blank.sum(),
        f"{on_bm3.sum()} of {blank.sum()} blank clients are on benchmark 3 vs {balanced_share:.0%} of known clients "
        f"Balanced (chance ~{p_chance:.0e}): benchmark 3 is a default, not proof, so no fill")

    # ===== STEP 4 - Values that can be repaired by reconciliation ===========================
    print("\nSTEP 4  repair negative shares on Buy transactions")
    # #10 negative shares on Buy: |shares| x price == amount proves the sign is the only error
    sh, px, amt = num(tx.shares), num(tx.price), num(tx.amount)
    mask = sh < 0
    before = mask.sum()
    assert (tx.txn_type[mask] == "Buy").all()
    assert ((sh[mask].abs() * px[mask] - amt[mask]).abs() <= 0.01).all(), "abs(shares) x price != amount"
    old = tx.shares.copy()
    tx.loc[mask, "shares"] = tx.loc[mask, "shares"].str.lstrip("-")
    record_changes("fact_transactions", tx, mask, "shares", old, tx.shares)
    sh = num(tx.shares)
    is_sec = tx.security_id != ""
    assert (sh[is_sec] > 0).all()
    assert ((sh * px - amt).abs()[is_sec] <= 0.01).all(), "shares x price still != amount"
    log("fact_transactions", "#10 negative shares on Buy", "flip sign (reconciled)", before,
        f"before: {before} rows with shares x price != amount; after: 0")

    # ===== STEP 5 - Referential integrity last (earlier steps can rescue keys) =============
    print("\nSTEP 5  quarantine orphan transactions")
    # #9 transactions for client_ids not in dim_client
    orphan = ~tx.client_id.isin(cl.client_id)
    before = len(tx)
    tx = quarantine("fact_transactions", tx, orphan, "fact_transactions_orphan_client",
                    "client_id not found in dim_client")
    assert tx.client_id.isin(cl.client_id).all()
    log("fact_transactions", "#9 orphan client_id", "quarantine", orphan.sum(),
        f"before: {before:,}; after: {before - orphan.sum():,}; {raw['fact_transactions'].client_id[orphan.values].nunique()} "
        f"distinct client_ids, range {raw['fact_transactions'].client_id[orphan.values].astype(int).min()}-"
        f"{raw['fact_transactions'].client_id[orphan.values].astype(int).max()}")
    for f in ["fact_fees", "fact_portfolio_snapshot"]:
        assert t[f].client_id.isin(cl.client_id).all(), f"{f} has orphan clients after de-dup"

    # ===== STEP 6 - Flags (suspicious but cannot be corrected without inventing data) ========
    print("\nSTEP 6  add flag columns")
    # #12 implausible return_ytd (return is AUM change, not flow-adjusted)
    r = num(sn.return_ytd)
    sn["flag_return_implausible"] = ((r > 1) | (r < -0.5)).astype(int)
    log("fact_portfolio_snapshot", "#12 return_ytd > +100% or < -50%", "flag_return_implausible=1",
        sn.flag_return_implausible.sum(), "values kept; return_ytd = AUM / prior Dec AUM - 1, so cash flows distort it")
    # #13 AUM floor of exactly 1,000.00
    sn["flag_aum_floor"] = (num(sn.aum) == 1000).astype(int)
    log("fact_portfolio_snapshot", "#13 aum exactly 1,000.00", "flag_aum_floor=1", sn.flag_aum_floor.sum(),
        f"{sn.client_id[sn.flag_aum_floor == 1].nunique()} clients; looks like a system floor, true value unknown")
    # #15 Buy/Sell on non-trading day
    trading = dict(zip(t["dim_date"].date, t["dim_date"].is_trading_day))
    tx["flag_non_trading_day"] = (tx.txn_type.isin(["Buy", "Sell"]) & (tx.txn_date.map(trading) == "0")).astype(int)
    n_hol = (tx.flag_non_trading_day.astype(bool) & tx.txn_date.isin(NYSE_HOLIDAYS)).sum()
    log("fact_transactions", "#15 Buy/Sell dated on a non-trading day", "flag_non_trading_day=1",
        tx.flag_non_trading_day.sum(), f"{tx.flag_non_trading_day.sum() - n_hol:,} weekends + {n_hol:,} NYSE holidays "
        "(uses corrected dim_date from #22); likely booking date, true trade date unknown")
    # #16 inactive client transacting after last snapshot
    last = sn.groupby("client_id").snapshot_date.max()
    inactive = set(cl.client_id[cl.is_active == "False"])
    tx["flag_after_last_snapshot"] = (tx.client_id.isin(inactive) &
                                      (tx.txn_date.str[:7] > tx.client_id.map(last).fillna("9999").str[:7])).astype(int)
    log("fact_transactions", "#16 inactive client transacting after final snapshot", "flag_after_last_snapshot=1",
        tx.flag_after_last_snapshot.sum(), "kept: could be closing trades/transfers out")
    # after-state checks for flags: 0/1 only, and each count independently recomputed from the values
    for col in ["flag_return_implausible", "flag_aum_floor"]:
        assert sn[col].isin([0, 1]).all()
    for col in ["flag_non_trading_day", "flag_after_last_snapshot"]:
        assert tx[col].isin([0, 1]).all()
    assert sn.flag_return_implausible.sum() == (~num(sn.return_ytd).between(-0.5, 1)).sum()
    assert sn.flag_aum_floor.sum() == (sn.aum.astype(float) == 1000).sum()
    wkday = pd.to_datetime(tx.txn_date, format="%Y-%m-%d").dt.dayofweek < 5
    assert tx.flag_non_trading_day.sum() == (tx.txn_type.isin(["Buy", "Sell"]) &
                                             (~wkday | tx.txn_date.isin(NYSE_HOLIDAYS))).sum()

    # ===== Issues deliberately left as is (logged with their evidence counts) ===============
    adv, sec, fee = t["dim_advisor"], t["dim_security"], t["fact_fees"]
    cash = ~tx.txn_type.isin(["Buy", "Sell", "Dividend"])
    fee_months = set(zip(fee.client_id, fee.fee_date))
    no_fee = sum((c, d) not in fee_months for c, d in zip(sn.client_id, sn.snapshot_date))
    used_bm = set(sn.benchmark_id) | set(sec.benchmark_id)
    for table, issue, n in [
        ("dim_advisor", "#4 certifications = 'None' means no certification (legitimate value)",
         (adv.certifications == "None").sum()),
        ("dim_security", "#5 sector blank for ETFs (legitimate structure)", (sec.sector == "").sum()),
        ("dim_security", "#6 expense_ratio blank for stocks (legitimate structure)", (sec.expense_ratio_bps == "").sum()),
        ("dim_security", "#7 duplicate security names with different tickers (legitimate)",
         sec.name.duplicated(keep=False).sum()),
        ("fact_portfolio_snapshot", "#14 snapshot months with no fee row", no_fee),
        ("fact_transactions", "#17 Advisory Fee transactions do not reconcile to fact_fees",
         (tx.txn_type == "Advisory Fee").sum()),
        ("fact_fees", "#18 bps_charged above 100; amount reconciles", (num(fee.bps_charged) > 100).sum()),
        ("fact_transactions", "#19 security_id/shares/price blank on cash transactions (legitimate)",
         (cash & (tx.security_id == "")).sum()),
        ("fact_fees", "#20 fee_type changes month to month for the same client",
         (fee.groupby("client_id").fee_type.nunique() > 1).sum()),
        ("dim_benchmark", "#21 benchmark referenced by no security or snapshot",
         (~t["dim_benchmark"].benchmark_id.isin(used_bm)).sum()),
    ]:
        log(table, issue, "leave as is", n, "rows_affected = evidence count; nothing changed. See decision_log.md")

    # ===== Write outputs + prove raw = clean + quarantined ==================================
    t["dim_client"], t["fact_transactions"], t["fact_portfolio_snapshot"] = cl, tx, sn
    print("\nRow reconciliation (raw = clean + quarantined)")
    for name in TABLES:
        df = t[name]
        assert list(df.columns[:len(raw[name].columns)]) == list(raw[name].columns), f"{name} column order changed"
        q = quarantine_counts.get(name, 0)
        assert raw_counts[name] == len(df) + q, f"{name}: {raw_counts[name]} != {len(df)} + {q}"
        print(f"  {name:25s} raw {raw_counts[name]:>8,} = clean {len(df):>8,} + quarantined {q:>4}")
        df.to_csv(CLEAN / f"{name}.csv", index=False)

    pd.DataFrame(log_rows).to_csv(AUDIT / "cleaning_log.csv", index=False)
    changes = pd.concat(change_rows, ignore_index=True)
    changes.to_csv(AUDIT / "value_changes.csv", index=False)
    print(f"\ncleaning_log.csv: {len(log_rows)} rows | value_changes.csv: {len(changes):,} cell changes | "
          f"quarantined: {quarantine_counts}")
    print("Raw files untouched; clean files written to data/clean/")


if __name__ == "__main__":
    main()
