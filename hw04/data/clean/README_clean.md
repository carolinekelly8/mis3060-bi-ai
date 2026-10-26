# Wildcat Capital — Clean Data Set

Produced by `scripts/02_clean.py` from `data/raw/`. Same 8 file names and the same columns in the same order. Flag columns (0/1) are appended at the end where noted. Removed rows are in `data/audit/quarantine_*.csv`, and every changed cell is in `data/audit/value_changes.csv`.

| Table | Raw rows | Clean rows | Quarantined |
|---|---:|---:|---:|
| dim_advisor | 25 | 25 | 0 |
| dim_benchmark | 8 | 8 | 0 |
| dim_client | 2,525 | 2,500 | 25 |
| dim_date | 1,827 | 1,827 | 0 |
| dim_security | 500 | 500 | 0 |
| fact_fees | 122,197 | 122,197 | 0 |
| fact_portfolio_snapshot | 129,547 | 129,547 | 0 |
| fact_transactions | 298,772 | 298,572 | 200 |

## Relationships (star schema)

| Fact / child | Column | → Dimension | Column | Cardinality |
|---|---|---|---|---|
| dim_client | advisor_id | dim_advisor | advisor_id | many-to-one |
| dim_security | benchmark_id | dim_benchmark | benchmark_id | many-to-one |
| fact_fees | client_id | dim_client | client_id | many-to-one |
| fact_fees | advisor_id | dim_advisor | advisor_id | many-to-one |
| fact_fees | fee_date | dim_date | date | many-to-one |
| fact_portfolio_snapshot | client_id | dim_client | client_id | many-to-one |
| fact_portfolio_snapshot | advisor_id | dim_advisor | advisor_id | many-to-one |
| fact_portfolio_snapshot | benchmark_id | dim_benchmark | benchmark_id | many-to-one |
| fact_portfolio_snapshot | snapshot_date | dim_date | date | many-to-one |
| fact_transactions | client_id | dim_client | client_id | many-to-one |
| fact_transactions | advisor_id | dim_advisor | advisor_id | many-to-one |
| fact_transactions | security_id | dim_security | security_id | many-to-one (blank for cash transactions) |
| fact_transactions | txn_date | dim_date | date | many-to-one |

`dim_date.is_trading_day` was corrected to 0 for the 47 NYSE market holidays in 2020–2024 (issue #22). In the raw file only weekends were non-trading.

Note the date join is on `dim_date.date` (YYYY-MM-DD), not `date_id`. The fact tables carry dates, not date IDs. Fact advisor_id always equals the client's advisor in dim_client, so in Power BI keep **one** active path to dim_advisor (via dim_client, or directly) to avoid ambiguous relationships.

## Column types for a BI tool

| Type | Columns |
|---|---|
| **Text (do not convert)** | dim_client.zip_code (leading zeros), dim_advisor.certifications ("None" is a real value, not null), all name/label columns, account_type / primary_account_type ("529" is a plan type, not a number) |
| Whole number | all `*_id` columns, age, years_experience, aum_target_mm, year, month, quarter, week_of_year, all `is_*` 0/1 columns in dim_date, all `flag_*` columns |
| Boolean (True/False) | dim_client.is_active, dim_security.is_etf |
| Date (YYYY-MM-DD) | dim_date.date, client_since, fee_date, snapshot_date, txn_date |
| Decimal / currency | initial_aum, aum_basis, amount, aum, price, shares |
| Decimal (rate, format as %) | return_ytd, benchmark_return_ytd, active_alpha_ytd, cash_pct. These are fractions (0.05 = 5%) |
| Decimal (basis points) | bps_charged, expense_ratio_bps |

## Flag columns added

| Table | Column | 1 means | Rows = 1 |
|---|---|---|---:|
| dim_client | flag_risk_profile_missing | risk_profile is blank (left blank on purpose: the benchmark-3 assignment looks like a system default, not evidence of the profile) | 75 |
| fact_portfolio_snapshot | flag_return_implausible | return_ytd > +100% or < −50% | 2,639 |
| fact_portfolio_snapshot | flag_aum_floor | aum is exactly 1,000.00 (looks like a system floor) | 420 |
| fact_transactions | flag_non_trading_day | Buy/Sell dated on a weekend or NYSE holiday (uses the corrected dim_date) | 44,241 |
| fact_transactions | flag_after_last_snapshot | inactive client, transaction in a month after their final snapshot | 2,410 |

## Known limitations (not fixed, with reasons)

1. **return_ytd is not a true investment return.** It equals AUM ÷ prior-December AUM − 1, so deposits and withdrawals count as performance, and active_alpha_ytd inherits the same distortion. Computing a time-weighted return needs dated cash flows matched to snapshots; we flagged the extremes rather than recompute.
2. **Fees are missing for 7,350 client-months (5.7% of snapshots).** We can't invent fee rows, so fee revenue for those months is understated.
3. **Advisory Fee transactions ≠ fact_fees.** Only 17 of 28,746 client-months agree. Use **fact_fees** for fee revenue, and don't add the two together.
4. **Trade dates on weekends and holidays** (flag_non_trading_day, 40,630 weekend + 3,611 holiday rows): the true trade date is unknown. Use monthly grain for trade analysis.
5. **200 orphan transactions** are excluded from client-level totals (in quarantine; restorable if the clients appear).
6. **AUM of 1,000.00** (flag_aum_floor) is probably a placeholder; the real balance is unknown.
7. **Missing risk profiles** (75 clients, flag_risk_profile_missing): left blank. Show them as "Unknown" in BI visuals rather than dropping them. Their benchmark 3 assignment is probably a default.
8. **Benchmark 6** (MSCI Emerging Markets) exists but is used by no security or snapshot.
