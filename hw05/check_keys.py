"""
HW5 - key, integrity and grain checks for the Wildcat Capital star schema.

Usage (from the hw05/ folder):
    python check_keys.py "path/to/Wildcat Capital Clean"
    python check_keys.py            (defaults to C:/MIS3060/Wildcat Capital Clean)

Every number cited in star_design.md is printed by one of the sections below:
  1. Profile            row/column counts vs. the assignment, dtypes, nulls
  2. Primary keys       the expected PK of every table is unique and non-blank
  3. Foreign keys       exact orphan and blank counts for every FK, incl. dates
  4. Grain              uniqueness tests behind each Part B sentence
  5. Supporting facts   blank security_id by txn_type, advisor consistency,
                        flag counts, sign of amounts, fee reconciliation
"""
import sys
from pathlib import Path

import pandas as pd

FILES = [
    "dim_advisor", "dim_benchmark", "dim_client", "dim_date", "dim_security",
    "fact_fees", "fact_portfolio_snapshot", "fact_transactions",
]

EXPECTED_SHAPE = {  # (rows, cols) from the assignment sheet
    "dim_advisor": (25, 7), "dim_benchmark": (8, 4), "dim_client": (2500, 14),
    "dim_date": (1827, 12), "dim_security": (500, 8), "fact_fees": (122197, 8),
    "fact_portfolio_snapshot": (129547, 14), "fact_transactions": (298572, 10),
}

PRIMARY_KEYS = {
    "dim_advisor": "advisor_id", "dim_benchmark": "benchmark_id",
    "dim_client": "client_id", "dim_date": "date_id",
    "dim_security": "security_id", "fact_fees": "fee_id",
    "fact_portfolio_snapshot": "snapshot_id", "fact_transactions": "txn_id",
}

# (child table, child column, parent table, parent column)
FOREIGN_KEYS = [
    ("dim_client", "advisor_id", "dim_advisor", "advisor_id"),
    ("dim_security", "benchmark_id", "dim_benchmark", "benchmark_id"),
    ("fact_fees", "client_id", "dim_client", "client_id"),
    ("fact_fees", "advisor_id", "dim_advisor", "advisor_id"),
    ("fact_fees", "fee_date", "dim_date", "date"),
    ("fact_portfolio_snapshot", "client_id", "dim_client", "client_id"),
    ("fact_portfolio_snapshot", "advisor_id", "dim_advisor", "advisor_id"),
    ("fact_portfolio_snapshot", "benchmark_id", "dim_benchmark", "benchmark_id"),
    ("fact_portfolio_snapshot", "snapshot_date", "dim_date", "date"),
    ("fact_transactions", "client_id", "dim_client", "client_id"),
    ("fact_transactions", "advisor_id", "dim_advisor", "advisor_id"),
    ("fact_transactions", "security_id", "dim_security", "security_id"),
    ("fact_transactions", "txn_date", "dim_date", "date"),
]

FACT_DATES = {"fact_fees": "fee_date", "fact_portfolio_snapshot": "snapshot_date",
              "fact_transactions": "txn_date"}


def header(text):
    print("\n" + "=" * 78 + f"\n{text}\n" + "=" * 78)


def load(folder):
    t = {}
    for name in FILES:
        # accept "name.csv" or a re-downloaded copy such as "name (1).csv"
        path = folder / f"{name}.csv"
        if not path.exists():
            matches = sorted(folder.glob(f"{name} (*).csv"))
            if not matches:
                sys.exit(f"Missing {name}.csv in {folder}")
            path = matches[0]
        t[name] = pd.read_csv(path)
        t[name].attrs["path"] = path.name
    return t


def orphans(child, parent):
    """Exact count of non-blank child values missing from parent (compared as text)."""
    c = child.dropna()
    if pd.api.types.is_float_dtype(c) and (c % 1 == 0).all():
        c = c.astype("int64")  # security_id is float only because it has blanks
    return int((~c.astype(str).isin(set(parent.astype(str)))).sum())


def main(folder):
    folder = Path(folder)
    t = load(folder)
    problems = []

    # 1. Profile -------------------------------------------------------------
    header("1. PROFILE")
    print(f"pandas {pd.__version__}; data folder: {folder}")
    for name, df in t.items():
        ok = df.shape == EXPECTED_SHAPE[name]
        if not ok:
            problems.append(f"{name} shape {df.shape} != {EXPECTED_SHAPE[name]}")
        print(f"\n{name}  <- {df.attrs['path']}: {df.shape[0]:,} rows x "
              f"{df.shape[1]} cols  [{'OK' if ok else 'MISMATCH'}]")
        print(pd.DataFrame({"dtype": df.dtypes.astype(str),
                            "nulls": df.isna().sum(),
                            "distinct": df.nunique()}).to_string())

    # 2. Primary keys --------------------------------------------------------
    header("2. PRIMARY KEYS (expected PK must be unique and non-blank)")
    for name, pk in PRIMARY_KEYS.items():
        s = t[name][pk]
        dups, blanks = int(s.duplicated().sum()), int(s.isna().sum())
        status = "OK" if dups == 0 and blanks == 0 else "FAIL"
        if status == "FAIL":
            problems.append(f"PK {name}.{pk}")
        print(f"{name:26s} {pk:14s} duplicates={dups:,}  blanks={blanks:,}  [{status}]")
    d = t["dim_date"]["date"]
    print(f"{'dim_date (natural key)':26s} {'date':14s} duplicates={int(d.duplicated().sum()):,}"
          f"  blanks={int(d.isna().sum()):,}")

    # 3. Foreign keys --------------------------------------------------------
    header("3. FOREIGN KEYS (exact orphan count = non-blank values missing from parent)")
    for child, ccol, parent, pcol in FOREIGN_KEYS:
        s = t[child][ccol]
        n_orph = orphans(s, t[parent][pcol])
        if n_orph:
            problems.append(f"FK {child}.{ccol}")
        print(f"{child}.{ccol} -> {parent}[{pcol}]: {n_orph:,} orphans, "
              f"{int(s.isna().sum()):,} blanks  [{'OK' if n_orph == 0 else 'FAIL'}]")
    print("\nFact dates vs dim_date[date_id] (shows date_id is NOT the join column):")
    for fact, col in FACT_DATES.items():
        n = len(t[fact])
        miss = orphans(t[fact][col], t["dim_date"]["date_id"])
        print(f"  {fact}.{col}: {n - miss:,} of {n:,} rows match dim_date[date_id]")

    # 4. Grain ---------------------------------------------------------------
    header("4. GRAIN")
    f, s, x = t["fact_fees"], t["fact_portfolio_snapshot"], t["fact_transactions"]
    print(f"fact_fees duplicates on (client_id, fee_date): "
          f"{int(f.duplicated(['client_id', 'fee_date']).sum()):,}")
    print(f"fact_fees max fee_type values per client-month: "
          f"{f.groupby(['client_id', 'fee_date']).fee_type.nunique().max()}")
    print(f"fact_portfolio_snapshot duplicates on (client_id, snapshot_date): "
          f"{int(s.duplicated(['client_id', 'snapshot_date']).sum()):,}")
    for name, col in [("fact_fees", "fee_date"), ("fact_portfolio_snapshot", "snapshot_date")]:
        days = pd.to_datetime(t[name][col]).dt.day
        print(f"{name}.{col}: {int((days == 1).sum()):,} of {len(days):,} rows dated the 1st")
    no_id = [c for c in x.columns if c != "txn_id"]
    print(f"fact_transactions duplicates on every column except txn_id: "
          f"{int(x.duplicated(no_id).sum()):,}")
    print(f"fact_transactions rows sharing (client_id, txn_date, txn_type) with another row: "
          f"{int(x.duplicated(['client_id', 'txn_date', 'txn_type']).sum()):,}")

    # 5. Supporting facts ----------------------------------------------------
    header("5. SUPPORTING FACTS")
    print("Blank security_id by txn_type:")
    print(x[x.security_id.isna()].txn_type.value_counts().to_string())
    print("\nRows with blank shares / price by txn_type:")
    print(x.groupby("txn_type")[["shares", "price"]]
          .apply(lambda g: g.isna().sum()).to_string())

    print("\nFact advisor_id equals the client's advisor_id in dim_client:")
    client_adv = t["dim_client"].set_index("client_id").advisor_id
    for name in FACT_DATES:
        df = t[name]
        same = (df.advisor_id == df.client_id.map(client_adv)).sum()
        print(f"  {name}: {same:,} of {len(df):,} rows")

    print("\nFlag counts:")
    for name, col in [("fact_portfolio_snapshot", "is_return_suspect"),
                      ("fact_transactions", "is_post_departure_txn")]:
        print(f"  {name}.{col}: {t[name][col].value_counts().sort_index().to_dict()}")

    sec = t["dim_security"]
    print(f"\ndim_security is_etf: {sec.is_etf.value_counts().to_dict()}; "
          f"blank expense_ratio_bps: {int(sec.expense_ratio_bps.isna().sum())} "
          f"(all non-ETF: {bool((~sec.is_etf[sec.expense_ratio_bps.isna()]).all())})")

    print(f"\nNegative amounts: fact_transactions={int((x.amount < 0).sum())}, "
          f"fact_fees={int((f.amount < 0).sum())}")

    print("\nFee reconciliation (fact_fees vs Advisory Fee transactions):")
    fee_txn = x[x.txn_type == "Advisory Fee"].copy()
    fee_txn["month"] = pd.to_datetime(fee_txn.txn_date).dt.to_period("M")
    ff = f.assign(month=pd.to_datetime(f.fee_date).dt.to_period("M"))
    print(f"  fact_fees total amount:            ${f.amount.sum():,.2f}")
    print(f"  Advisory Fee transactions total:   ${fee_txn.amount.sum():,.2f}")
    txn_m = fee_txn.groupby(["client_id", "month"]).amount.sum()
    fee_m = ff.groupby(["client_id", "month"]).amount.sum()
    both = fee_m.to_frame("fee").join(txn_m.rename("txn"), how="inner")
    print(f"  fee client-months with no Advisory Fee transaction: "
          f"{len(fee_m) - len(both):,} of {len(fee_m):,}")
    print(f"  client-months in both where amounts match to the cent: "
          f"{int(((both.fee - both.txn).abs() < 0.005).sum()):,} of {len(both):,}")

    header("RESULT")
    print("All checks passed." if not problems else "PROBLEMS: " + "; ".join(problems))


if __name__ == "__main__":
    if len(sys.argv) > 2:
        sys.exit('Usage: python check_keys.py "path/to/Wildcat Capital Clean"')
    default = Path(__file__).resolve().parents[2] / "Wildcat Capital Clean"
    main(sys.argv[1] if len(sys.argv) == 2 else default)
