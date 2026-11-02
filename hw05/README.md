# HW5 — Wildcat Capital Star Schema in Power BI

MIS3060 Business Intelligence with AI · Villanova University

## Structure

```
hw05/
├── README.md                 this file
├── star_design.md            Parts A, B, C, E and F
├── check_keys.py             PK / FK / date-join / grain checks (evidence for Parts A, B, C, E)
├── check_keys_output.txt     saved output of check_keys.py
└── powerbi/
    ├── hw05.pbix             Power BI model (Part D)
    └── model_view.png        Model view screenshot (Part D)
```

## How to run

From the `hw05/` folder, with the course virtual environment active (needs `pandas`). Run it in **Git Bash**: PowerShell 5.1's `>` writes the output file as UTF-16.

```
python check_keys.py "path/to/Wildcat Capital Clean"
python check_keys.py > check_keys_output.txt
```

With no argument, the script reads `C:\MIS3060\Wildcat Capital Clean\` (the folder next to this repo), so run it from `hw05/`. It accepts either `name.csv` or a re-downloaded `name (1).csv`, and prints which file it loaded for each table. Sections:
1. **Profile**: row/column counts checked against the assignment, plus dtypes, nulls and distinct counts
2. **Primary keys**: the expected PK of each table is checked for duplicates and blanks
3. **Foreign keys**: exact orphan and blank counts for all 13 FKs (date FKs against `dim_date[date]`), plus proof that no fact date matches `dim_date[date_id]`
4. **Grain**: the uniqueness tests behind each Part B sentence
5. **Supporting facts**: blank `security_id` by `txn_type`, fact vs. client advisor consistency, flag counts, sign of amounts, and the fee reconciliation used in Part F

The script ends with `All checks passed.` or a list of the checks that failed.

**Data source:** the official `Wildcat Capital Clean/` release (8 files). It's kept outside the repo and not committed. Every row and column count matches the assignment. The pandas version used is printed at the top of `check_keys_output.txt`.

## Power BI model (Part D)

- 8 CSVs loaded with Get Data → Text/CSV. Auto-detect relationships and Auto date/time are turned off.
- Types: IDs as Whole Number; date columns as Date; money (`amount`, `aum`, `aum_basis`, `initial_aum`, `price`) as Fixed decimal; rates and returns as Decimal; `zip_code`, `account_type` and `primary_account_type` as Text.
- 12 active relationships and 1 inactive one (`dim_client` → `dim_advisor`). All are many-to-one with single direction. See the table in `star_design.md`, Part E.
- `dim_date` is marked as the date table on `dim_date[date]`.
- Keys, date parts, flags and dimension attributes (`age`, `initial_aum`, `years_experience`, etc.) are set to **Don't summarize**, so Power BI doesn't sum them by default (matches Part C).
- Row counts in Power BI reconcile with the assignment: 25 / 8 / 2,500 / 1,827 / 500 / 122,197 / 129,547 / 298,572.

## Claude Code review findings

Claude Code reviewed `check_keys.py`, `check_keys_output.txt`, `star_design.md` and `model_view.png` before commit. It ran its own verification scripts against the data and confirmed that Parts A, B, C and E were correct. Its findings, and what I did about each:

| # | Severity | Finding | Action |
|---|---|---|---|
| 1 | Must-fix | Part F Q1 claimed the "Advisory Fee" transactions duplicate `fact_fees`. The data contradicts this: $263.7M vs $204.7M, 93,451 fee client-months with no debit, and no amounts that match. | Rewrote Q1: fee revenue comes only from `fact_fees`, and the mismatch is a data question to raise. Added the reconciliation to the script (§5). |
| 2 | Must-fix | The date check printed a rounded match %, so a handful of orphan dates could still show "100.0%", and "doesn't match `date_id`" was shown only by a missing line. | Date FKs now go through the same exact orphan count as the other FKs (§3), plus an explicit "0 of N rows match `date_id`" line. |
| 3 | Must-fix | README Claude Code section was still TODO. | This section. |
| 4 | Should-fix | Several numbers in `star_design.md` weren't computed by the script: blank `security_id` by type, the advisor match, flag counts, 281 non-ETFs. | All are now printed in §5 and cited by section number. |
| 5 | Should-fix | PKs were auto-detected, so a duplicated dimension PK would silently drop its FK checks. | PKs and FKs are now hard-coded lists. Every PK is checked for duplicates and blanks, and any failure appears in the final RESULT line. |
| 6 | Should-fix | The `txn_id` uniqueness check proves nothing, because it's a surrogate key. | Added a duplicate check on every column except `txn_id` (0 duplicates), and the client/day/type duplicate count (2,503). |
| 7 | Should-fix | Part F Q2's `LASTDATE` DAX would return blank, because snapshots are dated the 1st. | Changed it to `LASTNONBLANK` and explained why. |
| 8 | Should-fix | The saved output came from a different pandas version than the course venv, and the PowerShell redirect writes UTF-16. | Output regenerated from the course `.venv` in Git Bash. The pandas version is printed at the top, and the README says to use Git Bash. |
| 9 | Should-fix | The script didn't say which `name (1).csv` copy it loaded. | The profile section now prints the file name for each table. |
| 10 | Should-fix | Part C's `shares` wording ignored dividends, which also carry shares and price. | Reworded `shares` and `price` to cover Buy, Sell and Dividend. |
| 11 | Outside scope | Power BI would default to summing IDs, flags, `age`, `initial_aum` and similar. It also asked to confirm that `fee_date`/`txn_date` are Date type. | Set those columns to Don't summarize. The date columns are Date: they lack the calendar icon only because they're on the many side of a relationship to the marked date table, which doesn't generate an auto date hierarchy. |

Confirmed as fine: no machine-specific paths, all PKs/FKs (including both dimension-to-dimension FKs), all three grains, every Part C classification (the `bps_charged` formula checks within 0.7%), and Part E (a)–(d) against the screenshot.
