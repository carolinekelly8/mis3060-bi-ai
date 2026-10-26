# HW4 Decision Log — Wildcat Capital

Written from the Part A audit (`reports/dq_summary_raw.csv`, `reports/profile_raw.csv`) **before** the cleaning code. Each entry is the instruction given to Claude Desktop for `scripts/02_clean.py`. Issue numbers (#) are referenced in the script and in `data/audit/cleaning_log.csv`.

**Revisions after review:** #2 changed from fill to flag, and #11 now stores the reconciled full-precision value. Both are marked below.

**Cleaning order and why:** (1) fix formats first, so joins and comparisons work on consistent text; (2) remove duplicates before filling, so no fills are wasted on rows that get removed; (3) fill only where another table proves the value; (4) repair values that reconcile to other columns; (5) check referential integrity last, because earlier steps can rescue keys (e.g. `45.0` → `45`); (6) flag what can't be fixed.

---

## Issues fixed

### #1 — dim_client.state: full state names mixed with USPS codes
- **Table / column:** dim_client.state
- **Evidence:** 78 of 2,525 rows spell the state out (Pennsylvania 25, Florida 15, New York 14, New Jersey 13, California 5, Illinois 4, Texas 2), giving 27 distinct values for 20 actual states.
- **Dimension violated:** Consistency, Validity
- **Decision:** standardize to the 2-letter USPS code.
- **Justification:** a BI slicer or a GROUP BY on state would split "PA" and "Pennsylvania" into two regions and understate each state's AUM. The mapping is unambiguous.
- **Risk:** very low. Every full name maps to exactly one code.

### #3 — dim_client: 25 near-duplicate client records (IDs 2501–2525)
- **Table / column:** dim_client (all columns)
- **Evidence:** 25 clients share identical age, zip_code, initial_aum, client_since and advisor_id with an existing client. Their last name is truncated by one letter (e.g. 2501 "Taylo" = 674 "Taylor"; 2512 "Leen" = 1193 "Lee"). None of the 25 IDs appears in any fact table, which is why the audit shows "25 clients with no fees, snapshots or transactions".
- **Dimension violated:** Uniqueness
- **Decision:** quarantine to `data/audit/quarantine_dim_client_near_duplicates.csv`, with `client_id_original` linking each row to the record it duplicates.
- **Justification:** they would inflate the client count (2,525 vs 2,500) and the total initial AUM. The script asserts that no fact row references them, so removing them breaks no joins.
- **Risk:** if they were genuinely different people (very unlikely with five identical fields), we'd lose 25 clients with no activity. They're kept in quarantine, not deleted.

### #8 — fact_transactions.security_id stored as float text ("45.0")
- **Table / column:** fact_transactions.security_id
- **Evidence:** all 197,175 non-blank values look like `45.0`, while dim_security.security_id is `45`. An exact-text join therefore matches **0%** (the audit reports 197,175 orphans). After removing `.0`, 100% match.
- **Dimension violated:** Validity, Referential Integrity
- **Decision:** convert to integer text.
- **Justification:** a formatting artifact from the source export (an integer column with blanks gets cast to float). The value itself is correct.
- **Risk:** none. The script asserts every converted ID exists in dim_security.

### #9 — fact_transactions.client_id: 200 orphan rows
- **Table / column:** fact_transactions.client_id
- **Evidence:** 200 rows (200 distinct client_ids, range 2702–3192) reference clients that don't exist in dim_client. All other fact tables have a 100% client match.
- **Dimension violated:** Referential Integrity
- **Decision:** quarantine to `data/audit/quarantine_fact_transactions_orphan_client.csv`.
- **Justification:** these rows can't be attributed to a client's risk profile, tier or region, and they'd show up as "(Blank)" in every client-level Power BI visual. We can't invent the client.
- **Risk:** 200 of 298,772 rows (0.07%) of flows drop out of totals. If the clients arrive in a later dim_client extract, the rows can be restored from quarantine.

### #10 — fact_transactions.shares negative on 836 Buy rows
- **Table / column:** fact_transactions.shares
- **Evidence:** 836 rows, all txn_type = Buy, have negative shares. For every one, |shares| × price = amount to the cent. All other security rows reconcile exactly with positive shares.
- **Dimension violated:** Validity, Accuracy
- **Decision:** flip the sign to positive.
- **Justification:** amount and price prove the quantity; only the sign is wrong. A negative Buy would net against Sells and understate holdings.
- **Risk:** if some source system uses negative Buys to mean reversals, those trades would be overstated. Each change is in `value_changes.csv` and can be reversed.

### #11 — fact_portfolio_snapshot.return_ytd: 300 values stored as percent text
- **Table / column:** fact_portfolio_snapshot.return_ytd
- **Evidence:** 300 values look like `9.28%` while the rest are decimals (`0.0928`). These fail numeric parsing and would load as text or blank.
- **Dimension violated:** Validity, Consistency
- **Decision:** replace with benchmark_return_ytd + active_alpha_ytd at full precision (revised after the Claude Code review; it was ÷100 of the rounded text).
- **Justification:** verified, not assumed. Every % value agrees with benchmark + alpha within its 2-decimal rounding (max difference 0.00005), so the reconciled value is the same number at full precision. Simply dividing by 100 had left 233 of the 300 rows breaking alpha = return − benchmark at a 1e-5 tolerance; now all 300 satisfy it to 1e-6.
- **Risk:** none beyond the reconciliation itself, which the script asserts.

### #22 — dim_date.is_trading_day: NYSE market holidays marked as trading days
*Added after the Claude Code review of 01_profile.py, which noted that only weekends were checked.*
- **Table / column:** dim_date.is_trading_day
- **Evidence:** all 47 NYSE full-day closures in 2020–2024 (e.g. 2020-01-01, 2020-12-25, 2021-07-05, 2022-11-24) have is_trading_day = 1. dim_date only treats weekends as non-trading. 3,613 raw Buy/Sell rows fall on these holidays.
- **Dimension violated:** Accuracy, Validity
- **Decision:** set is_trading_day = 0 for the 47 holidays.
- **Justification:** verified against an external authority (the published NYSE holiday schedule, stored in `scripts/market_calendar.py`), not guessed. The script asserts that every holiday is a weekday before changing it. Any "trading days" measure in Power BI would otherwise be overstated by 47 days.
- **Risk:** low. If the firm also trades on venues open on some of these days, a few trades would be flagged unnecessarily. The flag keeps the rows; it doesn't remove them.

---

## Issues flagged (suspicious, but can't be corrected without inventing data)

### #2 — dim_client.risk_profile: blank for 76 clients (decision revised)
- **Table / column:** dim_client.risk_profile
- **Evidence:** 76 blanks (75 after the #3 de-dup). All 75 of these clients are on benchmark_id 3 (60/40 Blend) in every snapshot (3,942 rows). Among clients with a known profile, benchmark 3 is used only by Balanced, but only 31% of known clients (762 of 2,449) are Balanced.
- **Dimension violated:** Completeness
- **Original decision:** fill with "Balanced", because benchmark 3 maps only to Balanced.
- **Revised decision (after the Claude Code review of 02_clean.py):** leave blank and add `flag_risk_profile_missing = 1`.
- **Justification:** the inference is circular. If blank-profile clients were Balanced at the firm's normal 31% rate, the chance that all 75 land on benchmark 3 is about 1 in 10^38. The far likelier explanation is that the system assigns benchmark 3 as a **default when the profile is missing**, so the benchmark is a consequence of the blank, not evidence of the true profile. Filling would invent data. The script prints this test each time it runs.
- **Risk:** suitability and risk-mix reports show 75 clients (3.0%) as "unknown". This is the honest state: compliance needs to collect these questionnaires, and the flag lists exactly which clients.

### #12 — fact_portfolio_snapshot.return_ytd: implausible values and not flow-adjusted
- **Evidence:** return_ytd ranges from −99.4% to +9,467% (max 94.67). In 104,577 of 104,823 testable rows (99.8%), return_ytd = AUM ÷ prior-December AUM − 1, so deposits and withdrawals are counted as investment return. 2,639 rows are above +100% or below −50% (2,634 in the raw audit, plus 5 among the 300 converted % values).
- **Dimension:** Accuracy / Plausibility
- **Decision:** keep the values and add `flag_return_implausible = 1`.
- **Justification:** the true time-weighted return needs cash-flow data by date, which we don't have reliably. Replacing values would be fabrication.
- **Risk:** the committee could rank advisors on alpha that is really client deposits. The flag and README_clean warn against that.

### #13 — fact_portfolio_snapshot.aum exactly 1,000.00
- **Evidence:** 420 snapshots across 92 clients have aum = 1000.00 exactly, usually right after a large drop (e.g. client 29: 16,704.59 → 1,000.00 → 1,000.00).
- **Dimension:** Accuracy / Plausibility
- **Decision:** `flag_aum_floor = 1`.
- **Justification:** looks like a system minimum or placeholder, not a market value. The real balance is unknown.
- **Risk:** small, since the dollars involved are tiny. The flag stops these accounts being counted as "active small accounts".

### #15 — fact_transactions: Buy/Sell dated on non-trading days
- **Evidence:** 40,649 Buy/Sell rows in raw fall on weekends, and 3,613 more fall on NYSE holidays (#22): 44,262 in total. After quarantining orphans, 44,241 remain (40,630 weekend + 3,611 holiday).
- **Dimension:** Accuracy / Plausibility, Consistency with dim_date
- **Decision:** `flag_non_trading_day = 1`.
- **Justification:** probably a booking or entry date rather than the trade date. The true trade date isn't recoverable.
- **Risk:** day-level trade analysis would be wrong. Monthly and annual totals are unaffected.

### #16 — fact_transactions: inactive clients transacting after their final snapshot
- **Evidence:** 2,410 transactions belong to clients with is_active = False and are dated in months after that client's last portfolio snapshot.
- **Dimension:** Consistency (cross-table)
- **Decision:** `flag_after_last_snapshot = 1`.
- **Justification:** these could be legitimate closing trades or transfers out. Without account-closure dates we can't prove either way.
- **Risk:** if these are errors, flows for closed accounts are overstated. The flag allows exclusion.

---

## Issues left as is (legitimate structure or not fixable)

| # | Table / column | Evidence | Dimension | Decision | Justification | Risk |
|---|---|---|---|---|---|---|
| 4 | dim_advisor.certifications | 6 rows = text "None" | Completeness (apparent) | leave as is | "None" means the advisor holds no certification. It's a real answer, not a missing value. Must be imported as text so BI tools don't convert it to null. | A tool reading with default null parsing turns it blank. Noted in README_clean. |
| 5 | dim_security.sector | 219 blanks, all is_etf = True | Completeness (apparent) | leave as is | Funds and ETFs span sectors; 0 non-ETFs are blank. | None |
| 6 | dim_security.expense_ratio_bps | 281 blanks, all is_etf = False | Completeness (apparent) | leave as is | Individual stocks have no expense ratio; 0 funds are blank. | Don't fill with 0: it would drag down average fund costs. |
| 7 | dim_security.name | 3 pairs share a name (e.g. "Davis PLC Fund") | Uniqueness (apparent) | leave as is | Different ticker, asset class and benchmark, so they're different securities. Join on security_id, never name. | None |
| 14 | fact_portfolio_snapshot vs fact_fees | 7,350 snapshot months (5.7%) have no fee row | Completeness | leave as is | Can't invent fees. aum_basis matches snapshot AUM in 100% of the fee rows that do exist. | Fee revenue looks lower in those months. Documented limitation. |
| 17 | fact_transactions Advisory Fee vs fact_fees | only 17 of 28,746 client-months match | Consistency (cross-table) | leave as is | Different systems, different timing and grain (transaction debits vs monthly accrual). Use fact_fees for revenue. | Double counting if both are summed. Noted in README_clean. |
| 18 | fact_fees.bps_charged | 1 row at 100.38 bps (max of rest 99.88) | Plausibility | leave as is | Amount reconciles exactly (aum_basis × bps ÷ 10,000 ÷ 12). Within normal fee range. | None |
| 19 | fact_transactions security_id / shares / price | 101,597 blanks, all on Deposit / Withdrawal / Advisory Fee | Completeness (apparent) | leave as is | Cash transactions have no security. 0 Buy/Sell/Dividend rows are blank. | None |
| 20 | fact_fees.fee_type | fee_type changes month to month for the same client | Consistency | leave as is | Plausible billing practice; no rule says one type per client. | None |
| 21 | dim_benchmark | benchmark 6 (MSCI Emerging Markets) referenced by no table | Referential (unused parent) | leave as is | An unused dimension row is harmless. | None |

## Checked and clean (no action)
dim_date (year, quarter, month, month_name, week_of_year, day_of_week, month/quarter/year-end flags all agree with the date; no calendar gaps; weekends correctly non-trading; holidays are the exception, see #22); all primary keys unique; no exact duplicate rows; fee amount = aum_basis × bps ÷ 10,000 ÷ 12 for 100% of rows; active_alpha = return − benchmark return for 100% of rows; advisor_id in every fact table matches the client's advisor in dim_client; account_type matches the client's primary_account_type; client_tier is consistent with initial_aum bands (Retail < $500K, HNW $500K–$5M, UHNW > $5M); no transaction before client_since; zip codes keep leading zeros because the files are read as text.
