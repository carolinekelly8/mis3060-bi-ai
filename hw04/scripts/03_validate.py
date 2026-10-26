"""
HW4 Part D - Referential integrity and validation, run on RAW and CLEAN data.

Outputs
  reports/data_quality_scorecard.csv   one row per table per stage (raw / clean)
  reports/ri_results.csv               every relationship x stage (from check_referential_integrity)
  reports/validation_details.csv       every business rule, reconciliation and outlier check x stage

Run from anywhere:  python scripts/03_validate.py
"""
from pathlib import Path

import numpy as np
import pandas as pd

from market_calendar import NYSE_HOLIDAYS  # NYSE full-day closures 2020-2024 (reference data)

HW = Path(__file__).resolve().parent.parent
STAGES = {"raw": HW / "data" / "raw", "clean": HW / "data" / "clean"}
REPORTS = HW / "reports"
REPORTS.mkdir(parents=True, exist_ok=True)

TABLES = ["dim_advisor", "dim_benchmark", "dim_client", "dim_date", "dim_security",
          "fact_fees", "fact_portfolio_snapshot", "fact_transactions"]

# 10 ID-based relationships + 3 date relationships
RELATIONSHIPS = [
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

# primary key + natural (business) key per table, for the uniqueness score
KEYS = {
    "dim_advisor": ["advisor_id"], "dim_benchmark": ["ticker_proxy"], "dim_date": ["date"],
    "dim_security": ["ticker"],
    # dim_client has no clean business key (names are the defect). This is the record-matching rule used
    # to detect near-duplicates: every attribute except the (corrupted) last_name and the surrogate id.
    "dim_client": ["first_name", "age", "city", "state", "zip_code", "initial_aum", "client_since", "advisor_id"],
    "fact_fees": ["client_id", "fee_date"],
    "fact_portfolio_snapshot": ["client_id", "snapshot_date"],
    "fact_transactions": ["txn_id"],
}
PK = {"dim_advisor": "advisor_id", "dim_benchmark": "benchmark_id", "dim_client": "client_id",
      "dim_date": "date_id", "dim_security": "security_id", "fact_fees": "fee_id",
      "fact_portfolio_snapshot": "snapshot_id", "fact_transactions": "txn_id"}

INT, DEC, DATE, BOOL, TXT = "int", "dec", "date", "bool", "text"
TYPES = {
    "dim_advisor": {"advisor_id": INT, "years_experience": INT, "aum_target_mm": INT},
    "dim_benchmark": {"benchmark_id": INT},
    "dim_client": {"client_id": INT, "age": INT, "zip_code": TXT, "initial_aum": DEC,
                   "client_since": DATE, "advisor_id": INT, "is_active": BOOL},
    "dim_date": {"date_id": INT, "date": DATE, "year": INT, "quarter": INT, "month": INT,
                 "week_of_year": INT, "is_month_end": INT, "is_quarter_end": INT,
                 "is_year_end": INT, "is_trading_day": INT},
    "dim_security": {"security_id": INT, "benchmark_id": INT, "is_etf": BOOL, "expense_ratio_bps": DEC},
    "fact_fees": {"fee_id": INT, "client_id": INT, "advisor_id": INT, "fee_date": DATE,
                  "aum_basis": DEC, "bps_charged": DEC, "amount": DEC},
    "fact_portfolio_snapshot": {"snapshot_id": INT, "client_id": INT, "advisor_id": INT, "benchmark_id": INT,
                                "snapshot_date": DATE, "year": INT, "month": INT, "aum": DEC,
                                "return_ytd": DEC, "benchmark_return_ytd": DEC, "active_alpha_ytd": DEC,
                                "cash_pct": DEC},
    "fact_transactions": {"txn_id": INT, "client_id": INT, "advisor_id": INT, "security_id": INT,
                          "txn_date": DATE, "shares": DEC, "price": DEC, "amount": DEC},
}
US_STATES = set("AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM "
                "NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY DC".split())


def num(s):
    return pd.to_numeric(s, errors="coerce")


# =============================================================================================
def check_referential_integrity(fact_df, fact_key, dim_df, dim_key):
    """Reusable RI check (keep for Assignment 5).

    Returns a dict with:
      match_rate          share of non-null FK values found in the dimension (0-1)
      orphan_rows         rows whose non-null FK is not in the dimension
      distinct_orphan_keys
      null_key_rate       share of rows with a null/blank FK
    Compares exact text - no stripping or casting - so '45.0' or ' 45' vs '45' counts as an orphan,
    because that is exactly what fails when a BI tool joins the columns.
    match_rate is NaN (not 100%) when every key is null: nothing was matched.
    """
    fk = fact_df[fact_key].astype(str)
    is_null = fk.str.strip().isin(["", "nan", "None", "NaN"]) | fact_df[fact_key].isna()
    valid_keys = set(dim_df[dim_key].astype(str))
    nonnull = fk[~is_null]
    orphan_mask = ~nonnull.isin(valid_keys)
    n_nonnull = len(nonnull)
    return {
        "rows": len(fact_df),
        "match_rate": round((n_nonnull - orphan_mask.sum()) / n_nonnull, 6) if n_nonnull else np.nan,
        "orphan_rows": int(orphan_mask.sum()),
        "distinct_orphan_keys": int(nonnull[orphan_mask].nunique()),
        "null_key_rate": round(is_null.mean(), 6),
    }


# =============================================================================================
def expected_blank(table, df):
    """Boolean frame: True where a blank is legitimate structure (excluded from completeness)."""
    eb = pd.DataFrame(False, index=df.index, columns=df.columns)
    if table == "dim_security":
        eb["sector"] = df.is_etf == "True"
        eb["expense_ratio_bps"] = df.is_etf == "False"
    if table == "fact_transactions":
        cash = ~df.txn_type.isin(["Buy", "Sell", "Dividend"])
        for c in ["security_id", "shares", "price"]:
            eb[c] = cash
    return eb


def completeness(table, df):
    cols = [c for c in df.columns if not c.startswith("flag_")]
    blank = df[cols].apply(lambda s: s.astype(str).str.strip() == "")
    eb = expected_blank(table, df)[cols]
    required = ~eb
    return 1 - (blank & required).values.sum() / required.values.sum()


def type_validity(table, df):
    ok = total = 0
    for col, typ in TYPES[table].items():
        s = df[col].astype(str)
        s = s[s.str.strip() != ""]
        if typ == INT:
            good = s.str.fullmatch(r"-?\d+")
        elif typ == DEC:
            good = s.str.fullmatch(r"-?\d+(\.\d+)?([eE][-+]?\d+)?")
        elif typ == DATE:
            good = pd.to_datetime(s, format="%Y-%m-%d", errors="coerce").notna()
        elif typ == BOOL:
            good = s.isin(["True", "False"])
        else:
            good = pd.Series(True, index=s.index)
        ok += good.sum()
        total += len(s)
    return ok / total if total else 1.0


# Allowed-value lists: the categories defined in the source system, confirmed against the data with
# 01_profile.py (top_values in reports/profile_raw.csv). Any new category fails the rule.
ALLOWED = {
    "region": ["Northeast", "Mid-Atlantic", "Southeast", "Midwest", "West"],
    "risk_profile": ["Conservative", "Moderately Conservative", "Balanced", "Moderately Aggressive", "Aggressive"],
    "client_tier": ["Retail", "HNW", "UHNW"],
    "account_type": ["Taxable", "IRA", "Roth IRA", "Trust", "529"],
    "asset_class": ["Equity", "Fixed Income", "Alternative", "Cash Equivalent"],
    "fee_type": ["Advisory", "Management", "Custodial", "Performance"],
    "txn_type": ["Buy", "Sell", "Dividend", "Deposit", "Withdrawal", "Advisory Fee"],
}
# Thresholds shared with 01_profile.py
TIER_BANDS = {"Retail": (0, 5e5), "HNW": (5e5, 5e6), "UHNW": (5e6, np.inf)}   # [low, high)
ALPHA_TOL = 1e-5
HARD, FLAG = "hard rule", "known issue (flagged and kept)"


def business_rules(table, df, t):
    """Return {rule_name: (pass Series, kind)}.

    kind = HARD: a defect that cleaning must remove.
    kind = FLAG: a known issue the cleaning deliberately keeps with a flag column (the true value
    is unknown). Reported separately so 'flagged and kept' is not mistaken for 'cleaning failed'.
    """
    r = {}
    def add(name, ok, kind=HARD):
        r[name] = (ok, kind)
    if table == "dim_advisor":
        add("years_experience 0-50", num(df.years_experience).between(0, 50))
        add("aum_target_mm > 0", num(df.aum_target_mm) > 0)
        add("region in list", df.region.isin(ALLOWED["region"]))
    elif table == "dim_benchmark":
        add("name and ticker_proxy present", (df.name.str.strip() != "") & (df.ticker_proxy.str.strip() != ""))
        add("ticker_proxy unique", ~df.ticker_proxy.duplicated(keep=False))
    elif table == "dim_client":
        add("state is USPS code", df.state.isin(US_STATES))
        add("zip 5 digits", df.zip_code.str.fullmatch(r"\d{5}"))
        add("age 18-100", num(df.age).between(18, 100))
        add("risk_profile in list (or blank)", df.risk_profile.isin(ALLOWED["risk_profile"] + [""]))
        add("risk_profile present", df.risk_profile != "", FLAG)
        add("client_tier in list", df.client_tier.isin(ALLOWED["client_tier"]))
        add("primary_account_type in list", df.primary_account_type.isin(ALLOWED["account_type"]))
        add("is_active True/False", df.is_active.isin(["True", "False"]))
        cs = pd.to_datetime(df.client_since, format="%Y-%m-%d", errors="coerce")
        add("client_since 2000-01-01 to 2024-12-31", cs.between("2000-01-01", "2024-12-31"))
        ia = num(df.initial_aum)
        add("initial_aum > 0", ia > 0)
        band_ok = pd.Series(False, index=df.index)
        for tier, (lo, hi) in TIER_BANDS.items():
            band_ok |= (df.client_tier == tier) & (ia >= lo) & (ia < hi)
        add("tier matches AUM band", band_ok)
    elif table == "dim_date":
        d = pd.to_datetime(df.date, format="%Y-%m-%d", errors="coerce")
        add("date parses", d.notna())
        add("calendar fields agree with date",
            (df.year == d.dt.year.astype("Int64").astype(str)) & (df.month == d.dt.month.astype("Int64").astype(str)) &
            (df.quarter == d.dt.quarter.astype("Int64").astype(str)) & (df.month_name == d.dt.month_name()) &
            (df.day_of_week == d.dt.day_name()) &
            (df.week_of_year == d.dt.isocalendar().week.astype("Int64").astype(str)))
        add("month/quarter/year-end flags agree with date",
            (df.is_month_end == d.dt.is_month_end.astype(int).astype(str)) &
            (df.is_quarter_end == d.dt.is_quarter_end.astype(int).astype(str)) &
            (df.is_year_end == d.dt.is_year_end.astype(int).astype(str)))
        add("weekend not trading day", ~((d.dt.dayofweek >= 5) & (df.is_trading_day == "1")))
        add("NYSE holiday not trading day", ~(df.date.isin(NYSE_HOLIDAYS) & (df.is_trading_day == "1")))
    elif table == "dim_security":
        add("asset_class in list", df.asset_class.isin(ALLOWED["asset_class"]))
        add("is_etf True/False", df.is_etf.isin(["True", "False"]))
        add("ticker unique", ~df.ticker.duplicated(keep=False))
        er = num(df.expense_ratio_bps)
        add("expense_ratio 0-300 bps (funds)", (df.is_etf == "False") | er.between(0, 300))
        add("sector blank only for ETFs", (df.sector != "") | (df.is_etf == "True"))
    elif table == "fact_fees":
        add("amount > 0", num(df.amount) > 0)
        add("aum_basis > 0", num(df.aum_basis) > 0)
        add("bps_charged 0-150 (hard cap; 01 WARNs above 100 as 'investigate')", num(df.bps_charged).between(0, 150))
        add("fee_type in list", df.fee_type.isin(ALLOWED["fee_type"]))
        add("fee_date is 1st of month, 2020-2024", df.fee_date.str.fullmatch(r"202[0-4]-\d\d-01"))
        calc = num(df.aum_basis) * num(df.bps_charged) / 10000 / 12
        add("amount = aum_basis x bps / 10000 / 12", (num(df.amount) - calc).abs() <= 0.01)
    elif table == "fact_portfolio_snapshot":
        add("aum > 0", num(df.aum) > 0)
        add("cash_pct 0-1", num(df.cash_pct).between(0, 1))
        ret = num(df.return_ytd)
        add("return_ytd numeric", ret.notna())
        add("benchmark_return_ytd -100% to +100%", num(df.benchmark_return_ytd).between(-1, 1))
        add(f"alpha = return - benchmark (tol {ALPHA_TOL})",
            (ret - num(df.benchmark_return_ytd) - num(df.active_alpha_ytd)).abs() <= ALPHA_TOL)
        add("year/month agree with snapshot_date",
            (df.snapshot_date.str[:4] == df.year) & (df.snapshot_date.str[5:7].str.lstrip("0") == df.month))
        add("account_type in list", df.account_type.isin(ALLOWED["account_type"]))
        add("return_ytd -50% to +100%", ret.between(-0.5, 1), FLAG)
        add("aum not floor value 1000", num(df.aum) != 1000, FLAG)
    elif table == "fact_transactions":
        sec = df.txn_type.isin(["Buy", "Sell", "Dividend"])
        sh, px, amt = num(df.shares), num(df.price), num(df.amount)
        add("txn_type in list", df.txn_type.isin(ALLOWED["txn_type"]))
        add("amount > 0", amt > 0)
        add("shares > 0 (security txns)", ~sec | (sh > 0))
        add("price 0-10,000 (security txns)", ~sec | ((px > 0) & (px <= 10_000)))
        add("shares x price = amount", ~sec | ((sh * px - amt).abs() <= 0.01))
        add("cash txns have blank security_id/shares/price",
            sec | ((df.security_id == "") & (df.shares == "") & (df.price == "")))
        add("txn_date 2020-01-01 to 2024-12-31", df.txn_date.between("2020-01-01", "2024-12-31"))
        since = df.client_id.map(dict(zip(t["dim_client"].client_id, t["dim_client"].client_since)))
        add("txn_date on/after client_since", since.isna() | (df.txn_date >= since))
        # same rule for raw and clean: a trading day is a weekday that is not an NYSE holiday
        is_weekday = pd.to_datetime(df.txn_date, format="%Y-%m-%d", errors="coerce").dt.dayofweek < 5
        add("Buy/Sell on trading day (weekday, not NYSE holiday)",
            ~df.txn_type.isin(["Buy", "Sell"]) | (is_weekday & ~df.txn_date.isin(NYSE_HOLIDAYS)), FLAG)
    return {k: (v.fillna(False).astype(bool), kind) for k, (v, kind) in r.items()}


def iqr_outliers(s):
    x = num(s).dropna()
    q1, q3 = x.quantile([0.25, 0.75])
    lo, hi = q1 - 1.5 * (q3 - q1), q3 + 1.5 * (q3 - q1)
    return int(((x < lo) | (x > hi)).sum()), len(x), lo, hi


# =============================================================================================
def main():
    score_rows, ri_rows, detail_rows = [], [], []
    for stage, folder in STAGES.items():
        t = {n: pd.read_csv(folder / f"{n}.csv", dtype=str, keep_default_na=False) for n in TABLES}
        print(f"\n===== {stage.upper()} =====")

        # --- referential integrity on all 13 relationships
        ri_by_child = {}
        for child, ccol, parent, pcol in RELATIONSHIPS:
            res = check_referential_integrity(t[child], ccol, t[parent], pcol)
            ri_rows.append({"stage": stage, "relationship": f"{child}.{ccol} -> {parent}.{pcol}", **res})
            ri_by_child.setdefault(child, []).append(res)
            print(f"  RI {child}.{ccol} -> {parent}.{pcol}: match {res['match_rate']:.2%}, "
                  f"orphans {res['orphan_rows']:,}, null {res['null_key_rate']:.2%}")

        # --- business rules
        for name, df in t.items():
            rules = business_rules(name, df, t)
            for rule, (ok, kind) in rules.items():
                detail_rows.append({"stage": stage, "table": name, "check_type": f"business rule: {kind}",
                                    "check": rule, "rows_checked": len(df), "rows_failing": int((~ok).sum()),
                                    "pass_rate": round(ok.mean(), 6)})
            hard = [ok for ok, kind in rules.values() if kind == HARD]
            flag = [ok for ok, kind in rules.values() if kind == FLAG]
            all_pass = pd.concat(hard, axis=1).all(axis=1) if hard else pd.Series(True, index=df.index)
            any_flag = ~pd.concat(flag, axis=1).all(axis=1) if flag else pd.Series(False, index=df.index)

            # --- scorecard metrics
            keys = KEYS[name]
            pk_unique = 1 - df[PK[name]].duplicated(keep=False).mean()
            nk_unique = 1 - df.duplicated(keys, keep=False).mean()
            ri = ri_by_child.get(name)
            ri_match = (sum(r["rows"] * r["match_rate"] * (1 - r["null_key_rate"]) for r in ri) /
                        sum(r["rows"] * (1 - r["null_key_rate"]) for r in ri)) if ri else np.nan
            score_rows.append({
                "table": name, "stage": stage, "rows": len(df),
                "pct_completeness": round(completeness(name, df) * 100, 3),
                "pct_key_uniqueness": round(min(pk_unique, nk_unique) * 100, 3),
                "pct_type_validity": round(type_validity(name, df) * 100, 3),
                "pct_rule_pass": round(all_pass.mean() * 100, 3),
                "pct_referential_match": round(ri_match * 100, 3) if ri else np.nan,   # blank = no foreign keys
                "pct_rows_known_issue_flagged": round(any_flag.mean() * 100, 3),
            })

        # --- cross-table reconciliations
        fee, sn, tx, cl = t["fact_fees"], t["fact_portfolio_snapshot"], t["fact_transactions"], t["dim_client"]
        m = fee.merge(sn[["client_id", "snapshot_date", "aum"]], left_on=["client_id", "fee_date"],
                      right_on=["client_id", "snapshot_date"], how="left")
        ok = (num(m.aum) - num(m.aum_basis)).abs() <= 0.01
        detail_rows.append({"stage": stage, "table": "fact_fees vs fact_portfolio_snapshot",
                            "check_type": "cross-table reconciliation",
                            "check": "fee aum_basis = snapshot aum (same client, month)",
                            "rows_checked": len(m), "rows_failing": int((~ok).sum()), "pass_rate": round(ok.mean(), 6)})
        adv = dict(zip(cl.client_id, cl.advisor_id))
        for f in ["fact_fees", "fact_portfolio_snapshot", "fact_transactions"]:
            mapped = t[f].client_id.map(adv)
            known = mapped.notna()          # orphan clients are an RI problem, counted in ri_results.csv
            ok = mapped[known] == t[f].advisor_id[known]
            detail_rows.append({"stage": stage, "table": f"{f} vs dim_client", "check_type": "cross-table reconciliation",
                                "check": "fact advisor_id = client's advisor_id (rows with a known client)",
                                "rows_checked": int(known.sum()), "rows_failing": int((~ok).sum()),
                                "pass_rate": round(ok.mean(), 6)})
        af = tx[tx.txn_type == "Advisory Fee"]
        fm = fee.assign(a=num(fee.amount), ym=fee.fee_date.str[:7]).groupby(["client_id", "ym"]).a.sum()
        am = af.assign(a=num(af.amount), ym=af.txn_date.str[:7]).groupby(["client_id", "ym"]).a.sum()
        allj = pd.concat([fm.rename("fee"), am.rename("txn")], axis=1)
        j = allj.dropna()
        ok = (j.fee - j.txn).abs() <= 1
        for label, n in [("fee client-months with no Advisory Fee txn", allj.txn.isna().sum()),
                         ("Advisory Fee txn client-months with no fee row", allj.fee.isna().sum())]:
            detail_rows.append({"stage": stage, "table": "fact_transactions vs fact_fees",
                                "check_type": "reconciliation coverage", "check": label,
                                "rows_checked": len(allj), "rows_failing": int(n), "pass_rate": round(1 - n / len(allj), 6)})
        detail_rows.append({"stage": stage, "table": "fact_transactions vs fact_fees",
                            "check_type": "cross-table reconciliation",
                            "check": "Advisory Fee txn total = fact_fees total (client-month)",
                            "rows_checked": len(j), "rows_failing": int((~ok).sum()), "pass_rate": round(ok.mean(), 6)})
        sec = tx[tx.security_id != ""]
        ok = (num(sec.shares) * num(sec.price) - num(sec.amount)).abs() <= 0.01
        detail_rows.append({"stage": stage, "table": "fact_transactions", "check_type": "recompute",
                            "check": "recomputed shares x price = stored amount",
                            "rows_checked": len(sec), "rows_failing": int((~ok).sum()), "pass_rate": round(ok.mean(), 6)})

        # --- IQR outliers on unbounded numeric columns
        # Flagged != wrong: these are long-tailed money values (a few UHNW clients hold most AUM),
        # so an IQR "outlier" is usually a large but real account, not an error.
        targets = [("fact_portfolio_snapshot", "aum", None), ("fact_fees", "amount", None),
                   ("dim_client", "initial_aum", None)]
        # transaction amounts come from different distributions per type -> separate fences per txn_type
        targets += [("fact_transactions", "amount", tt) for tt in sorted(tx.txn_type.unique())]
        for name, col, tt in targets:
            data = t[name][col] if tt is None else t[name].loc[t[name].txn_type == tt, col]
            n_out, n, lo, hi = iqr_outliers(data)
            label = col if tt is None else f"{col} [{tt}]"
            detail_rows.append({"stage": stage, "table": name, "check_type": "IQR outlier",
                                "check": f"{label} outside [{lo:,.2f}, {hi:,.2f}]",
                                "rows_checked": n, "rows_failing": n_out, "pass_rate": round(1 - n_out / n, 6)})

    score = pd.DataFrame(score_rows).sort_values(["table", "stage"], key=lambda c: c.map({"raw": 0, "clean": 1}) if c.name == "stage" else c)
    score.to_csv(REPORTS / "data_quality_scorecard.csv", index=False)
    pd.DataFrame(ri_rows).to_csv(REPORTS / "ri_results.csv", index=False)
    pd.DataFrame(detail_rows).to_csv(REPORTS / "validation_details.csv", index=False)

    print("\n===== SCORECARD =====")
    print(score.to_string(index=False))
    print("\npct_rule_pass = hard rules only; pct_rows_known_issue_flagged = rows kept on purpose with a flag "
          "(true value unknown). Blank pct_referential_match = table has no foreign keys.")
    print("\nIQR note: 'flagged' does not mean 'wrong' - AUM and trade amounts are naturally long-tailed, "
          "so most IQR outliers are large but legitimate UHNW accounts.")
    # Sanity checks on the clean stage
    for name in TABLES:
        r = score[(score.table == name) & (score.stage == "raw")].iloc[0]
        c = score[(score.table == name) & (score.stage == "clean")].iloc[0]
        for col in ["pct_key_uniqueness", "pct_type_validity", "pct_rule_pass"]:
            assert c[col] >= r[col] - 1e-9, f"{name} {col} got worse after cleaning"
        assert c.pct_rule_pass == 100, f"{name}: a hard rule still fails after cleaning"
    # completeness is not asserted 'not worse': the 75 deliberately-blank risk profiles sit on 25 fewer rows
    clean_ri = pd.DataFrame(ri_rows).query("stage == 'clean'")
    assert (clean_ri.match_rate == 1).all(), "a clean relationship has orphans"


if __name__ == "__main__":
    main()
