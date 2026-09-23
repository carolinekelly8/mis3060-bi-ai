"""
=============================================================================
Script:     hw02_eda.py
Purpose:    Exploratory Data Analysis (EDA) of transaction data - HW2
Dataset:    data/raw/fact_transactions.csv
Author:     Caroline Kelly (MIS3060 Business Intelligence with AI)
Generated:  2026-09-23, with Claude (Cowork), from the HW2 specification
Outputs:    hw02/hw02_profile.txt
            hw02/charts/hist_amount.png
            hw02/charts/box_amount_by_type.png
            hw02/charts/scatter_shares_amount.png
Run from:   anywhere, e.g.  python hw02/hw02_eda.py
=============================================================================
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # save charts to files without opening a window
import matplotlib.pyplot as plt
import pandas as pd

# ---------------------------------------------------------------------------
# Paths (relative to the repository root, so the script works from any folder)
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = REPO_ROOT / "data" / "raw" / "fact_transactions.csv"
HW_DIR = REPO_ROOT / "hw02"
CHART_DIR = HW_DIR / "charts"
PROFILE_PATH = HW_DIR / "hw02_profile.txt"
EXPECTED_SHAPE = (298772, 9)

CHART_DIR.mkdir(parents=True, exist_ok=True)

pd.set_option("display.width", 120)
pd.set_option("display.max_columns", 50)

# Everything passed to report() is printed AND saved to the profile text file.
profile_lines = []


def report(text=""):
    print(text)
    profile_lines.append(str(text))


def section(title):
    report()
    report("=" * 70)
    report(title)
    report("=" * 70)


def find_column(df, keyword):
    """Return the first ID column containing the keyword (e.g. 'client_id')."""
    matches = [c for c in df.columns if keyword in c.lower() and "id" in c.lower()]
    if not matches:
        matches = [c for c in df.columns if keyword in c.lower()]
    return matches[0] if matches else None


# ---------------------------------------------------------------------------
# 1. Load the data
# ---------------------------------------------------------------------------
if not DATA_PATH.exists():
    raise FileNotFoundError(
        f"Could not find {DATA_PATH}. Download fact_transactions.csv from "
        "Brightspace and save it to data/raw/ in your repository."
    )

df = pd.read_csv(DATA_PATH)
df["txn_date"] = pd.to_datetime(df["txn_date"], errors="coerce")

report("HW2 EDA PROFILE - fact_transactions.csv")
report(f"Source file: {DATA_PATH.relative_to(REPO_ROOT)}")

# ---------------------------------------------------------------------------
# 2. Shape
# ---------------------------------------------------------------------------
section("2. SHAPE")
report(f"Rows: {df.shape[0]:,}   Columns: {df.shape[1]}")

# ---------------------------------------------------------------------------
# 3. Column names and data types
# ---------------------------------------------------------------------------
section("3. COLUMN NAMES AND DATA TYPES")
report(df.dtypes.to_string())

# ---------------------------------------------------------------------------
# 4. Missing values per column
# ---------------------------------------------------------------------------
section("4. MISSING VALUES PER COLUMN")
report(df.isna().sum().to_string())
report(f"Total missing values: {int(df.isna().sum().sum()):,}")

# ---------------------------------------------------------------------------
# 5. Descriptive statistics for numeric columns
# ---------------------------------------------------------------------------
section("5. DESCRIPTIVE STATISTICS (NUMERIC COLUMNS)")
desc = df.describe().T.rename(columns={"50%": "median"})
report(desc[["count", "mean", "std", "min", "25%", "median", "75%", "max"]]
       .round(2).to_string())

# ---------------------------------------------------------------------------
# 6. txn_type value counts and percentages
# ---------------------------------------------------------------------------
section("6. TXN_TYPE VALUE COUNTS")
type_counts = df["txn_type"].value_counts()  # sorted most -> least frequent
type_table = pd.DataFrame({
    "count": type_counts,
    "percent": (type_counts / len(df) * 100).round(2),
})
report(type_table.to_string())

# ---------------------------------------------------------------------------
# 7. Unique clients, advisors, securities
# ---------------------------------------------------------------------------
section("7. UNIQUE ENTITIES REFERENCED")
for label, keyword in [("Clients", "client"), ("Advisors", "advisor"),
                       ("Securities", "security")]:
    col = find_column(df, keyword)
    if col:
        report(f"{label:<11} ({col}): {df[col].nunique():,}")
    else:
        report(f"{label:<11}: no matching column found")

# ---------------------------------------------------------------------------
# 8. Date range
# ---------------------------------------------------------------------------
section("8. DATE RANGE (txn_date)")
report(f"Earliest: {df['txn_date'].min().date()}")
report(f"Latest:   {df['txn_date'].max().date()}")
bad_dates = int(df["txn_date"].isna().sum())
if bad_dates:
    report(f"Note: {bad_dates:,} txn_date values are missing or unreadable")

# ---------------------------------------------------------------------------
# 9. Duplicate txn_id check
# ---------------------------------------------------------------------------
section("9. DUPLICATE CHECK (txn_id)")
dup_count = int(df["txn_id"].duplicated().sum())
report(f"Duplicate txn_id rows (beyond first occurrence): {dup_count:,}")

# ---------------------------------------------------------------------------
# 10. Mean, median, skewness of amount
# ---------------------------------------------------------------------------
section("10. AMOUNT - CENTER AND SHAPE")
amount_mean = df["amount"].mean()
amount_median = df["amount"].median()
amount_skew = df["amount"].skew()
report(f"Mean:     {amount_mean:,.2f}")
report(f"Median:   {amount_median:,.2f}")
report(f"Skewness: {amount_skew:.2f}")

# ---------------------------------------------------------------------------
# 11. Amount by txn_type
# ---------------------------------------------------------------------------
section("11. AMOUNT BY TXN_TYPE (sorted by mean, descending)")
by_type = (df.groupby("txn_type")["amount"]
             .agg(count="count", mean="mean", median="median")
             .round(2)
             .sort_values("mean", ascending=False))
report(by_type.to_string())

# ---------------------------------------------------------------------------
# 12. Correlation matrix and three strongest correlations
# ---------------------------------------------------------------------------
section("12. CORRELATION MATRIX (shares, price, amount)")
corr = df[["shares", "price", "amount"]].corr().round(2)
report(corr.to_string())
report()
report("Three strongest correlations (by absolute value):")
pairs = []
cols = list(corr.columns)
for i in range(len(cols)):
    for j in range(i + 1, len(cols)):  # upper triangle: no self or repeat pairs
        pairs.append((cols[i], cols[j], corr.iloc[i, j]))
pairs.sort(key=lambda p: abs(p[2]), reverse=True)
for rank, (a, b, r) in enumerate(pairs[:3], start=1):
    report(f"  {rank}. {a} & {b}: {r:.2f}")

# ---------------------------------------------------------------------------
# 13. Shares min / max / negative count by txn_type
# ---------------------------------------------------------------------------
section("13. SHARES BY TXN_TYPE (min, max, negative count)")
shares_table = df.groupby("txn_type")["shares"].agg(
    min="min",
    max="max",
    negative_count=lambda s: int((s < 0).sum()),
)
report(shares_table.to_string())

# ---------------------------------------------------------------------------
# 14. Shape check
# ---------------------------------------------------------------------------
if df.shape != EXPECTED_SHAPE:
    print()
    print(f"WARNING: shape is {df.shape}, expected {EXPECTED_SHAPE}. "
          "Check that you downloaded the correct, complete file.")
else:
    print()
    print(f"Shape check passed: {df.shape}")

# ---------------------------------------------------------------------------
# 15. Charts
# ---------------------------------------------------------------------------
# Histogram of amount with mean and median lines
fig, ax = plt.subplots(figsize=(10, 6))
ax.hist(df["amount"].dropna(), bins=60, color="#4C72B0", edgecolor="white")
ax.axvline(amount_mean, color="#C44E52", linestyle="--", linewidth=2,
           label=f"Mean = {amount_mean:,.2f}")
ax.axvline(amount_median, color="#55A868", linestyle="-", linewidth=2,
           label=f"Median = {amount_median:,.2f}")
ax.set_title("Distribution of Transaction Amount")
ax.set_xlabel("Amount")
ax.set_ylabel("Number of transactions")
ax.legend()
fig.tight_layout()
fig.savefig(CHART_DIR / "hist_amount.png", dpi=150)
plt.close(fig)

# Horizontal box plot of amount by txn_type
order = by_type.index.tolist()
fig, ax = plt.subplots(figsize=(10, 6))
ax.boxplot([df.loc[df["txn_type"] == t, "amount"].dropna() for t in order],
           vert=False, flierprops={"markersize": 2, "alpha": 0.3})
ax.set_yticks(range(1, len(order) + 1))
ax.set_yticklabels(order)
ax.set_title("Transaction Amount by Transaction Type")
ax.set_xlabel("Amount")
ax.set_ylabel("Transaction type")
fig.tight_layout()
fig.savefig(CHART_DIR / "box_amount_by_type.png", dpi=150)
plt.close(fig)

# Scatter of shares vs amount, colored by txn_type
fig, ax = plt.subplots(figsize=(10, 6))
for t in type_counts.index:
    subset = df[df["txn_type"] == t]
    ax.scatter(subset["shares"], subset["amount"], s=4, alpha=0.4, label=t)
ax.set_title("Shares vs. Amount by Transaction Type")
ax.set_xlabel("Shares")
ax.set_ylabel("Amount")
ax.legend(title="txn_type", markerscale=4)
fig.tight_layout()
fig.savefig(CHART_DIR / "scatter_shares_amount.png", dpi=150)
plt.close(fig)

print()
print(f"Charts saved to {CHART_DIR.relative_to(REPO_ROOT)}/")

# ---------------------------------------------------------------------------
# 16. Save plain-text profile (items 2-13)
# ---------------------------------------------------------------------------
PROFILE_PATH.write_text("\n".join(profile_lines) + "\n", encoding="utf-8")
print(f"Profile saved to {PROFILE_PATH.relative_to(REPO_ROOT)}")