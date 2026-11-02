# HW5 — Wildcat Capital Star Schema Design

Every count and key, integrity or grain claim below is printed by `check_keys.py`; its full output is saved in `check_keys_output.txt`. Section numbers (§) refer to that output.

---

## Part A — Keys

| Table | Type | Primary key | Foreign keys (column → table[column]) |
|---|---|---|---|
| dim_advisor | Dimension | `advisor_id` | — |
| dim_benchmark | Dimension | `benchmark_id` | — |
| dim_client | Dimension | `client_id` | `advisor_id` → dim_advisor[advisor_id] |
| dim_date | Dimension | `date_id` | — |
| dim_security | Dimension | `security_id` | `benchmark_id` → dim_benchmark[benchmark_id] |
| fact_fees | Fact | `fee_id` | `client_id` → dim_client[client_id]<br>`advisor_id` → dim_advisor[advisor_id]<br>`fee_date` → dim_date[date] |
| fact_portfolio_snapshot | Fact | `snapshot_id` | `client_id` → dim_client[client_id]<br>`advisor_id` → dim_advisor[advisor_id]<br>`benchmark_id` → dim_benchmark[benchmark_id]<br>`snapshot_date` → dim_date[date] |
| fact_transactions | Fact | `txn_id` | `client_id` → dim_client[client_id]<br>`advisor_id` → dim_advisor[advisor_id]<br>`security_id` → dim_security[security_id]<br>`txn_date` → dim_date[date] |

**Proof (from `check_keys.py`):**
- §2: Each table's expected primary key has 0 duplicates and 0 blanks. `dim_date[date]` is also unique and non-blank. `date_id` is the surrogate primary key, and `date` is the natural key that the facts join to.
- §3: All 13 foreign keys, including the three date keys, have an exact count of **0 orphans**: every non-blank value exists in the column it points to.
- §3: 0 rows in any fact table match `dim_date[date_id]`, so the date join has to be on `date`.

**Keys that can legitimately be blank:** `fact_transactions.security_id` is blank on 101,528 rows. These are exactly the Deposit (35,956), Withdrawal (29,830) and Advisory Fee (35,742) rows. Cash movements and fee debits don't involve a security, so there is nothing for the key to point to (see Part E(a)). No other foreign key has blanks.

---

## Part B — Grain

- **fact_fees:** One row represents one fee charged to one client for one month, dated the first of that month.
- **fact_portfolio_snapshot:** One row represents one client's portfolio position (AUM, YTD returns and cash share) as of one month, dated the first of that month.
- **fact_transactions:** One row represents a single transaction event for one client on one day: a buy, sell, dividend, deposit, withdrawal or advisory-fee debit.

**Proof (§4):**
- `fact_fees` has 0 duplicates on `client_id` + `fee_date`, and at most one `fee_type` per client-month.
- `fact_portfolio_snapshot` has 0 duplicates on `client_id` + `snapshot_date`.
- All 122,197 fee rows and all 129,547 snapshot rows are dated the 1st of the month.
- `txn_id` is a surrogate key, so being unique proves nothing about the grain. The real test: no two transaction rows are identical on every column except `txn_id` (0 duplicates), so each row is a distinct event. 2,503 rows share client, day and type with another row, which confirms that a client can have several transactions of the same type on the same day. The grain is the event, not client-day.

---

## Part C — Measures

### Fact measures

| Table | Column | Classification | What that means for summing / averaging |
|---|---|---|---|
| fact_fees | `amount` | **Additive** | Fee dollars can be summed across clients, advisors, fee types and months, and the total is real fee revenue. |
| fact_fees | `aum_basis` | **Semi-additive** | AUM the fee was charged on is a balance. It can be summed across clients within one month, but summing it across months counts the same assets again each month, so over time use the period-end value or an average. |
| fact_fees | `bps_charged` | **Non-additive** | It's an annual rate in basis points, so it can never be summed. An overall rate must be recomputed as Σamount ÷ Σaum_basis × 12 × 10,000 (an AUM-weighted average), not a simple average. |
| fact_portfolio_snapshot | `aum` | **Semi-additive** | Sum across clients for a single month to get firm AUM. Over time, take the last snapshot in the period (or the average) instead of summing. |
| fact_portfolio_snapshot | `return_ytd` | **Non-additive** | Returns are percentages that compound year-to-date. They can't be summed across clients or months, and the cross-client figure should be AUM-weighted. |
| fact_portfolio_snapshot | `benchmark_return_ytd` | **Non-additive** | Same as `return_ytd`: a YTD percentage. Take the value for the right month, never a sum. |
| fact_portfolio_snapshot | `active_alpha_ytd` | **Non-additive** | It's a difference of two YTD percentages, so it can't be summed. Recompute it from weighted returns at the aggregate level. |
| fact_portfolio_snapshot | `cash_pct` | **Non-additive** | It's a share of the client's AUM. The firm-wide figure is Σ(cash_pct × aum) ÷ Σaum, never a sum or simple average. |
| fact_transactions | `amount` | **Additive** (within a `txn_type`) | Dollar amounts sum across clients, securities and days. But every amount is stored as a positive number and direction comes from `txn_type`, so a total that mixes types (e.g. deposits + withdrawals, or buys + sells) is meaningless. Filter or split by `txn_type` first. |
| fact_transactions | `shares` | **Additive** (within one security and one `txn_type`) | Share counts sum only for the same security and the same transaction type: Buy, Sell or Dividend (all three carry shares, with amount = shares × price). Shares of different securities, or buys + sells + dividends mixed together, don't add up to anything meaningful. Blank for deposits, withdrawals and fee debits. |
| fact_transactions | `price` | **Non-additive** | A per-share price (on Buy, Sell and Dividend rows) can't be summed. An average price must be weighted by shares (Σamount ÷ Σshares). |

### Numeric columns that are not measures
- **Keys:** `fee_id`, `snapshot_id`, `txn_id`, and every `client_id`, `advisor_id`, `benchmark_id` and `security_id` on the fact tables.
- **Date parts:** `fact_portfolio_snapshot.year` and `.month` (these repeat `snapshot_date`; use `dim_date` instead).
- **Flags (0/1):** `fact_portfolio_snapshot.is_return_suspect` (3,875 rows = 1) and `fact_transactions.is_post_departure_txn` (2,410 rows = 1). These can be *counted* to see how many rows are flagged, or used as filters, but they aren't business measures.
- **Codes that look numeric:** `fact_portfolio_snapshot.account_type` (e.g. "529" is a plan type) — treat as text.

### Numeric attributes in dimension tables (never sum)
- **dim_advisor:** `years_experience`, `aum_target_mm` (a target, not actual AUM).
- **dim_client:** `age`, `initial_aum` (frozen at onboarding; current AUM comes from the snapshot fact), `zip_code` (an identifier that loads as a number and loses its leading zeros, e.g. 03897 → 3897; set it to Text).
- **dim_security:** `expense_ratio_bps` (a rate; blank for the 281 non-ETFs).
- **dim_date:** `date_id`, `year`, `quarter`, `month`, `week_of_year`, and all the `is_*` flags.
- **dim_benchmark:** only `benchmark_id` (a key).

---

## Part E — Relationships and design questions

### Relationships in the Power BI model

All relationships are many-to-one (dimension on the "1" side) with **single** cross-filter direction (the dimension filters the fact). `dim_date` is marked as the date table on `dim_date[date]`.

| From (many) | To (one) | Status |
|---|---|---|
| fact_fees[fee_date] | dim_date[date] | Active |
| fact_fees[client_id] | dim_client[client_id] | Active |
| fact_fees[advisor_id] | dim_advisor[advisor_id] | Active |
| fact_portfolio_snapshot[snapshot_date] | dim_date[date] | Active |
| fact_portfolio_snapshot[client_id] | dim_client[client_id] | Active |
| fact_portfolio_snapshot[advisor_id] | dim_advisor[advisor_id] | Active |
| fact_portfolio_snapshot[benchmark_id] | dim_benchmark[benchmark_id] | Active |
| fact_transactions[txn_date] | dim_date[date] | Active |
| fact_transactions[client_id] | dim_client[client_id] | Active |
| fact_transactions[advisor_id] | dim_advisor[advisor_id] | Active |
| fact_transactions[security_id] | dim_security[security_id] | Active |
| dim_security[benchmark_id] | dim_benchmark[benchmark_id] | Active |
| dim_client[advisor_id] | dim_advisor[advisor_id] | **Inactive** (see (b)) |

**Conformed dimensions:** `dim_date`, `dim_client` and `dim_advisor` connect to all three fact tables. They mean the same thing in each, so one slicer on any of them filters fees, snapshots and transactions together. `dim_benchmark` is shared by the snapshot fact and, through `dim_security`, the transaction fact.

### (a) Some transaction rows have no `security_id`. Why, and is that a defect?
101,528 transactions have a blank `security_id`, and every one is a Deposit, Withdrawal or Advisory Fee. These rows are cash moving into or out of the account, or a fee being debited, so no security is bought, sold or paid out. Their `shares` and `price` are blank for the same reason. That isn't a defect: the key is blank because it doesn't apply, not because it's missing. The script shows 0 orphans among the non-blank values. In Power BI the blank rows fall under a "(Blank)" security, which is the correct place for them. Filling them with a fake "Cash" security would invent a value. A better schema could add a "Cash / No security" row to `dim_security`, but the assignment says not to add rows.

### (b) `advisor_id` appears in `dim_client` and on all three fact tables. Which relationship(s) are active, and why?
I kept **`dim_advisor` → each fact table** active and made **`dim_client[advisor_id]` → `dim_advisor`** inactive. With all four active there would be two filter paths from `dim_advisor` to every fact table (directly, and through `dim_client`), which is ambiguous, so Power BI only allows one. The direct path is the cleaner star: every fact sits one hop from every dimension, and the advisor on a fact row is the advisor recorded at the time of the event. That's the right one to keep if a client ever changes advisor. In this data the fact `advisor_id` equals the client's `advisor_id` on every row of all three facts (§5: 122,197/122,197, 129,547/129,547, 298,572/298,572), so both paths give the same numbers today. The trade-off is that a question about `dim_client` itself, like "how many clients does each advisor have", needs `USERELATIONSHIP` in DAX (HW6), or must be answered by counting distinct clients in a fact table.

### (c) The date dimension has its own `date_id`, but the facts store calendar dates. Which column did you join on, and why?
I joined on **`dim_date[date]`**. A relationship can only match values that are equal, and the facts store calendar dates (`fee_date`, `snapshot_date`, `txn_date` as YYYY-MM-DD) that have 0 orphans against `dim_date[date]`, while 0 rows match `date_id` (§3). Joining on `date_id` would mean adding a date-ID column to every fact, which the assignment rules out. `date` is unique and has no blanks, so it works as the "one" side. It's also the column Power BI needs in order to **mark the table as a date table**, which time-intelligence DAX in HW6 relies on. Both sides are set to the Date type, not Date/Time or text.

### (d) Star or snowflake: does anything connect one dimension to another? Did you keep it?
Yes, two dimension-to-dimension links exist, so the source design is partly a snowflake:
1. **`dim_client` → `dim_advisor`**: kept but **inactive**, for the reason in (b). Every fact links to `dim_advisor` directly, so the model stays a star for reporting.
2. **`dim_security` → `dim_benchmark`**: kept **active**. `fact_transactions` has no `benchmark_id`, so this is the only way to analyse trades by the benchmark of the security traded. It doesn't create an ambiguous path: `dim_benchmark` reaches the snapshot fact directly and the transaction fact only through `dim_security`. One caution: a benchmark slicer then means two different things, the *client's* benchmark for snapshots and the *security's* benchmark for transactions. Report visuals should say which one they use.

So the model is a star with one snowflake branch (security → benchmark) and one inactive one (client → advisor).

---

## Part F — Reflection

**1. Fees: "What was total fee revenue by advisor region for each quarter of 2024?"**
This works in **a single visual with no DAX**. `fact_fees[amount]` is fully additive, `dim_advisor[region]` and `dim_date[year]`/`[quarter]` all filter `fact_fees` directly, and a matrix with the default Sum is correct. One caveat: fee revenue should come only from `fact_fees`. `fact_transactions` also has "Advisory Fee" debits, but they don't reconcile with `fact_fees` (§5). They total $263.7M against $204.7M in `fact_fees`, 93,451 of 122,197 fee client-months have no matching debit, and where both exist the amounts never match to the cent. That's a data question to raise with the business (are debits billed in arrears, in batches, or on a different basis?), not something the model can resolve. **Schema fix:** a shared `fee_id` on the debit transaction would let the two be reconciled.

**2. Snapshot: "What was total assets under management by advisor at the end of each quarter?"**
This **can't be done in a single visual without a DAX workaround**. `aum` is semi-additive, so putting it in a matrix by quarter sums three monthly snapshots and roughly triples AUM. Filtering to `dim_date[is_quarter_end] = 1` doesn't help either, because snapshots are dated the *first* of the month, which never falls on a quarter-end day. HW6 will need a measure that takes the last date in the period that actually has a snapshot, e.g. `CALCULATE(SUM(fact_portfolio_snapshot[aum]), LASTNONBLANK(dim_date[date], CALCULATE(SUM(fact_portfolio_snapshot[aum]))))`. `LASTDATE` wouldn't work, because it picks the quarter's last calendar day (e.g. 3/31), and there's no snapshot on that day, so it would return blank. **Schema fix:** date each snapshot at month-end (or add an `is_snapshot_period_end` flag) so a plain filter picks the right month. The same problem affects firm-level `return_ytd`, which needs an AUM-weighted measure, never Sum or Average.

**3. Transactions: "What was net new money (deposits minus withdrawals) by client tier each month?"**
This **can't be done in a single visual without DAX**. Every `amount` is stored as a positive number, so Sum of amount adds withdrawals to deposits instead of subtracting them. You need a measure that negates withdrawals (e.g. `SUMX` with an IF on `txn_type`). **Schema fix:** store a signed `net_cash_flow` amount (positive in, negative out), or add a `direction` column (+1/−1) to the fact, so a plain Sum gives the right answer. A related question, "how many clients does each advisor manage?", also needs DAX because of the inactive client → advisor relationship in (b).
