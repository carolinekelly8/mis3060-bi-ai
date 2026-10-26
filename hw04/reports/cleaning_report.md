# Wildcat Capital — Data Cleaning Report
**To:** Portfolio Committee  **Re:** Quality of the data warehouse extract (8 tables, 2020–2024)

## Executive summary

The extract is usable for reporting after cleaning, but **portfolio performance figures need care**. We audited 555,401 rows across eight tables and found 7 problems we could fix with proof from the data itself (or, for market holidays, from the published NYSE calendar), 5 we flagged but could not fix without inventing values, and 10 that look odd but are legitimate. **Only 225 rows (0.04%) were removed**: 25 duplicate client records and 200 transactions for clients who don't exist. Both sets are kept in quarantine files, not deleted. After cleaning, every one of the 13 table relationships joins at 100%, up from 0% for the security link and 99.93% for the transaction–client link.

The biggest issue for the committee is not a data-entry error but a definition problem: **`return_ytd` is AUM growth, not investment return.** In 104,577 of 104,823 testable rows (99.8%) it equals AUM ÷ prior-December AUM − 1, so a client deposit shows up as "performance". 2,639 snapshots show returns above +100% or below −50%. These are flagged, not changed, and advisor alpha rankings should not be built on this field until it is recomputed with cash flows.

## Cleaning summary

| Table | Issue | Action | Rows affected |
|---|---|---|---:|
| fact_transactions | security_id stored as `45.0`, so 0% matched dim_security | Converted to `45` | 197,175 |
| fact_transactions | Buy rows with negative shares (\|shares\| × price = amount) | Sign flipped | 836 |
| fact_transactions | client_id not in dim_client (IDs 2702–3192) | Quarantined | 200 |
| fact_portfolio_snapshot | return_ytd stored as `9.28%` text | Replaced with benchmark + alpha at full precision (agrees with the % text within rounding) | 300 |
| dim_client | State spelled out ("Pennsylvania" vs "PA") | Standardized to USPS code | 78 |
| dim_client | Near-duplicate clients (surname off by one letter, every other field identical) | Quarantined | 25 |
| dim_client | Blank risk_profile | Left blank + flagged (benchmark is a default, not proof) | 75 |
| dim_date | 47 NYSE holidays marked as trading days | Set is_trading_day = 0 (NYSE calendar) | 47 |
| fact_portfolio_snapshot | Return > +100% or < −50% | Flagged | 2,639 |
| fact_portfolio_snapshot | AUM exactly $1,000.00 (92 clients) | Flagged | 420 |
| fact_transactions | Buy/Sell on a weekend (40,630) or NYSE holiday (3,611) | Flagged | 44,241 |
| fact_transactions | Inactive client trading after final snapshot | Flagged | 2,410 |

**Data quality scorecard (raw → clean)**

| Table | Completeness | Key uniqueness | Type validity | Rule pass (defects) | Referential match | Rows flagged and kept |
|---|---|---|---|---|---|---|
| dim_client | 99.79% → 99.79% | 98.02% → 100% | 100% → 100% | 96.91% → 100% | 100% → 100% | 3.01% → 3.00% |
| dim_date | 100% → 100% | 100% → 100% | 100% → 100% | 97.43% → 100% | n/a | 0% |
| fact_portfolio_snapshot | 100% → 100% | 100% → 100% | 99.98% → 100% | 99.77% → 100% | 100% → 100% | 2.38% → 2.15% |
| fact_transactions | 100% → 100% | 100% → 100% | 90.55% → 100% | 99.72% → 100% | 81.95% → 100% | 14.82% → 14.82% |
| Other 4 tables | 100% | 100% | 100% | 100% | 100% | 0% |

Every defect rule passes at 100% after cleaning. "Rows flagged and kept" are known issues whose true value is unknown (missing risk profiles, implausible returns, $1,000 balances, weekend and holiday trades). They are kept with a flag column, not fixed. dim_client completeness stays at 99.79% because the 75 missing risk profiles were deliberately not filled.

## Key judgment calls

**1. Do not fill 75 blank risk profiles, even though the benchmark seems to imply "Balanced".**
*Justification:* all 75 blank-profile clients are on benchmark 3 (60/40 Blend), which known clients use only when Balanced. That looked like proof, and the first version of the cleaning filled them. Review showed the reasoning is circular. Only 31% of known clients are Balanced, so 75 of 75 landing on benchmark 3 by chance is about 1 in 10^38. Benchmark 3 is almost certainly the system's default for a missing profile. The profiles are left blank and flagged (`flag_risk_profile_missing = 1`). *Risk:* risk-mix reports show 3% "Unknown". That is accurate, and it gives compliance a list of clients whose questionnaires need collecting. Filling would have reported them as suitably assessed when they are not.

**2. Flip the sign on 836 negative Buy quantities rather than quarantine them.**
*Justification:* for every one of the 836 rows, |shares| × price equals the recorded amount to the cent, so the quantity is proven and only the sign is wrong. Quarantining would have dropped real trades. *Risk:* if a source system uses negative Buys to record reversals, holdings are overstated for those trades. Every change is logged in `value_changes.csv` and is reversible.

**3. Flag, but do not "correct", implausible returns.**
*Justification:* return_ytd is AUM-based, so withdrawals and deposits distort it (e.g. one client fell from $16,704.59 to $1,000.00 and shows −97.7% YTD). A true time-weighted return needs dated cash flows we can't reliably match. Replacing the values would be fabrication. *Risk:* anyone ranking advisors on active_alpha_ytd without the flag will reward advisors whose clients deposited money and penalize those whose clients withdrew.

**4. Quarantine 25 duplicate clients instead of merging them.**
*Justification:* each matches an existing client on every field except surname, which is off by one letter (e.g. "Taylo"/"Taylor", "Leen"/"Lee"). The script asserts this for every pair, and asserts that the record kept is the one with activity. No fee, snapshot or transaction references them. *Risk:* negligible, since there is no activity attached. Without this fix, the client count and total initial AUM would be overstated.

## Limitations

- **Performance:** return_ytd and active_alpha_ytd are not flow-adjusted (see above).
- **Missing fees:** 7,350 client-months (5.7% of snapshots) have no fee row, so fee revenue is understated for those months.
- **Two fee sources disagree:** Advisory Fee transactions match fact_fees in only 17 of 28,746 client-months. Use fact_fees for revenue, and never add the two together.
- **Trade dates:** 44,241 Buy/Sell rows fall on weekends or market holidays, so the true trade date is unknown. Analyze trades at monthly grain.
- **Excluded flows:** 200 orphan transactions are out of client-level totals until those clients appear in dim_client.
- **Unused benchmark:** MSCI Emerging Markets is defined but used by no security or client.

---
Reviewed for factual accuracy on 10/26/2026 by Caroline Kelly
