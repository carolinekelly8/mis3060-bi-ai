# HW4 — Cleaning the Wildcat Capital Data

Audit, clean and validate the eight-table Wildcat Capital warehouse extract. Raw files are never modified. Every change is logged, and every removed row is quarantined.

## Structure

```
hw04/
├── README.md                  this file
├── decision_log.md            Part B - one entry per issue (written before cleaning code)
├── HW04_Data_Cleaning.md      assignment brief (used for Claude Code reviews)
├── scripts/
│   ├── 01_profile.py          Part A - generic profiler + 4 check groups
│   ├── 02_clean.py            Part C - incremental, asserted cleaning
│   ├── 03_validate.py         Part D - RI function, rules, reconciliations, IQR, scorecard
│   └── market_calendar.py     NYSE holiday list 2020-2024 (reference data used by all 3 scripts)
├── data/
│   ├── raw/                   8 original CSVs (read-only input)
│   ├── clean/                 8 cleaned CSVs + README_clean.md
│   └── audit/                 cleaning_log.csv, value_changes.csv, quarantine_*.csv
└── reports/
    ├── profile_raw.csv        column-level profile of every raw table
    ├── dq_summary_raw.csv     findings tagged ERROR / WARN / INFO
    ├── data_quality_scorecard.csv   raw vs clean, one row per table per stage
    ├── ri_results.csv         all 13 relationships, raw and clean
    ├── validation_details.csv every rule / reconciliation / outlier check
    └── cleaning_report.md     Part E - committee report
```

## How to run

From the repo root, in a terminal with the virtual environment active:

```
pip install pandas numpy
cd hw04
python scripts/01_profile.py     # ~30 s  -> reports/profile_raw.csv, dq_summary_raw.csv
python scripts/02_clean.py       # ~5 s   -> data/clean/, data/audit/
python scripts/03_validate.py    # ~15 s  -> reports/data_quality_scorecard.csv (+ details)
```

Scripts locate files relative to their own folder, so they also work when run from the repo root (`python hw04/scripts/01_profile.py`). `02_clean.py` stops with an `AssertionError` if any fix doesn't do what it claims, or if `raw rows ≠ clean rows + quarantined rows` for any table.

## Results at a glance

| Table | Raw rows | Clean rows | Quarantined |
|---|---:|---:|---:|
| dim_client | 2,525 | 2,500 | 25 (near-duplicates) |
| fact_transactions | 298,772 | 298,572 | 200 (orphan client_id) |
| other 6 tables | unchanged row counts | | 0 |

Referential match after cleaning is 100% on all 13 relationships, and every defect rule passes at 100%. See `reports/data_quality_scorecard.csv`.

## Process

Claude Desktop drafted each script; it was run and debugged in VS Code, and reviewed with Claude Code before each commit.

## Claude Code review findings

| Script | What Claude Code flagged | What I did |
|---|---|---|
| 01_profile.py | (1) The '.0'-normalized orphan check was suppressed when its count was 0, so the report showed 197,175 security_id orphans without saying they all match once '.0' is removed. | **Fixed:** added an INFO finding that reports how many orphans the '.0' fix resolves (197,175 of 197,175; 0 remain). |
| 01_profile.py | (2) The "\|shares\| x price == amount" note was a hard-coded string, not computed, and the 836 negative Buys were reported twice as separate ERRORs. | **Fixed:** the note is now computed (836 of 836 reconcile). The amount check uses \|shares\|, so the same rows aren't double counted. |
| 01_profile.py | (3) dim_date marks NYSE holidays (e.g. 2020-01-01, 2020-12-25) as trading days; only weekends were checked. | **Fixed:** added an NYSE holiday list (`market_calendar.py`). The profiler now finds 47 holidays marked as trading days and 3,613 Buy/Sell rows on holidays. 02_clean.py corrects dim_date (new issue #22 in decision_log.md), and the trade flag now covers holidays (44,241 rows). |
| 01_profile.py | (4) Smaller bugs: "PK unique" INFO was written even when there were duplicates; a leftover empty loop; the account_type check counted orphan clients as mismatches; the fee reconciliation hid its coverage; several dim_date fields were unchecked. | **Fixed** all five. Account type is now WARN (a "primary" account type can legitimately differ). The fee check now reports coverage (93,451 fee months have no Advisory Fee txn, 1,933 the reverse). Also added checks for month_name, week_of_year, quarter/year-end and calendar gaps. |
| 01_profile.py | (5) Rule checks are hard-coded per table, and thresholds (age 18–100, return > +100% / < −50%, bps > 100) are assumptions. | **Kept:** `profile_table()` is fully generic and runs on any table. The business-rule checks name columns by design, because rules are table-specific. Each threshold is justified in decision_log.md. |
| 02_clean.py | (1) **Risky assumption:** the risk_profile fill is circular. All 75 blank-profile clients are on benchmark 3 although only 31% of known clients are Balanced, so benchmark 3 is probably the default for a missing profile, not proof. | **Changed my decision:** no longer fill. The profiles stay blank with `flag_risk_profile_missing = 1`, and the script prints the test (75 of 75 vs 31%, chance about 1e-38). Updated decision log #2, README_clean and report judgment call 1. |
| 02_clean.py | (2) The % → decimal fix lost precision: 233 of 300 rows broke alpha = return − benchmark at 1e-5, hidden by 03's looser 1e-4 tolerance. | **Fixed:** store the reconciled benchmark + alpha value at full precision (asserted to agree with the % text within rounding). All 300 rows now satisfy alpha to 1e-6, and 03 uses the same 1e-5 tolerance as 01. |
| 02_clean.py | (3) The orphan log note printed the row count as "distinct ids" and hard-coded the 2702–3192 range. The near-duplicate name check could pass with roles reversed, and never compared first_name. | **Fixed:** distinct count and range are computed. Near-duplicates are now asserted pair by pair: every other column identical, surname off by exactly one letter (this caught that Leen/Lee and Pacen/Pace have an *extra* letter, not a missing one), the quarantined record has no facts, and the kept record has facts. |
| 02_clean.py | (4) Smaller: the state assert only checked the pattern; stale quarantine files were never cleared; "leave as is" rows logged 0 rows and #20/#21 were missing; the flag step had no after-state check. | **Fixed** all four: the state is asserted against the USPS list, old quarantine files are cleared at start, and leave-as-is rows log their evidence counts (incl. #20, #21). Each flag count is re-computed and asserted. |
| 03_validate.py | (1) Rules for issues that are flagged and kept counted as failures, so clean fact_transactions showed 85% rule pass, which looks like cleaning failed. | **Fixed:** rules are split into *hard rules* (defects; all 100% after cleaning, now asserted) and *known issues*, reported in a new column `pct_rows_known_issue_flagged`. |
| 03_validate.py | (2) `check_referential_integrity` returned 100% when every key was null and stripped whitespace. The scorecard mixed text ("n/a") into a numeric column. Advisor reconciliation counted orphans as mismatches. Fee reconciliation hid coverage. | **Fixed:** the RI function now returns NaN for all-null keys and compares exact text (a BI tool won't join " 45" to "45"). "n/a" is now blank, the advisor check skips orphan clients, fee coverage is reported, and the script asserts every clean relationship is 100%. |
| 03_validate.py | (3) Missing rules for many bounded columns. Thresholds differed from 01. IQR mixed all transaction types. | **Fixed:** added account type, is_active, client_since range, all dim_date fields, ticker uniqueness, fee_date = 1st, aum_basis > 0, year/month vs date, benchmark return range, price cap, blank security fields on cash rows, txn_date range and txn on/after client_since. Tier bands and alpha tolerance now match 01. IQR fences are per txn_type. Allowed lists cite their source. |
| 03_validate.py | (4) dim_client's "natural key" is the same column set used to find duplicates, so clean uniqueness is 100% by construction. | **Kept, with reason:** dim_client has no clean business key, because the last name *is* the corrupted field. The key is documented as the record-matching rule (every attribute except last_name and the surrogate ID). Other tables now use real business keys (dim_date.date, dim_security.ticker, dim_benchmark.ticker_proxy). |
