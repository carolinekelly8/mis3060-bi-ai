# HW3 Validation

## 5A — Known-Answer Check: Earnings

Company and quarter checked: **Microsoft (MSFT), fourth quarter of fiscal year 2026 (quarter ended June 30, 2026)**, 8-K filed 2026-07-29.

| Check | Official Source | Your CSV | Match? |
|---|---|---|---|
| MSFT Q4 FY2026 Revenue | $90.0 billion ($90,007 million) — Microsoft FY26 Q4 earnings press release | 90.0 (billion) | Yes |
| MSFT Q4 FY2026 EPS Diluted | $4.81 — Microsoft FY26 Q4 earnings press release | 4.81 | Yes |

Official source: Microsoft Investor Relations, FY26 Q4 press release — https://www.microsoft.com/en-us/investor/earnings/fy-2026-q4/press-release-webcast

Both values matched, so no regex fix was needed for this check. Note that the CSV stores the rounded figure from the press release prose ("Revenue was $90.0 billion"), not the exact $90,007 million from the financial tables.

**Extraction issues found and fixed during the pipeline runs (before/after):**

| Problem | Before | After | Resolved? |
|---|---|---|---|
| NVDA and WMT press releases not found (8 filings skipped, only 12 rows) | Looked for the exhibit by file name: `ex(hibit)?[-_]?99[-_.]?0?1` | Read the filing index page and pick the document whose official type is `EX-99.1`, regardless of file name | Yes — 20/20 rows |
| Reporting period picked up the *next* quarter's outlook or the prior year's comparison (e.g., WMT filing of 2025-11-20 labeled "quarter ended October 31, 2024") | Searched the whole document for the first period phrase | Search the headline area (first 1,500 characters) first, then the whole document; added `Q2 FY27` and "fourth quarter and fiscal 2026" patterns | Yes — labels now match each filing date (Walmart labels no longer include the fiscal year) |

## 5B — Known-Answer Check: Executive Events

Event checked: **Apple, 8-K filed 2026-04-20 — John Ternus appointed Chief Executive Officer.**

| Check | News Source Confirms? | Notes |
|---|---|---|
| Person name and title | Yes | John Ternus, currently SVP of Hardware Engineering, to become CEO. CSV: "John Ternus / Chief Executive Officer" |
| Event type (departure/appointment) | Yes (partially) | Appointment is correct. Tim Cook is moving from CEO to Executive Chairman; the pipeline did not record a separate row for Cook's change in this filing because the sentence used "will become" rather than a departure keyword. |
| Effective date | Yes | September 1, 2026 — matches the CSV (`effective_date` = September 1, 2026) |

Source: Apple Newsroom, "Tim Cook to become Apple Executive Chairman; John Ternus to become Apple CEO" (April 20, 2026) — https://www.apple.com/newsroom/2026/04/tim-cook-to-become-apple-executive-chairman-john-ternus-to-become-apple-ceo/

## 5C — Cross-Validation: Earnings via Yahoo Finance

Script: `hw03/yf_check.py` (yfinance `quarterly_income_stmt`, most recent quarter for MSFT).

| Metric | From 8-K text extraction | From yfinance | Match? |
|---|---|---|---|
| Revenue | $90.0 billion | $90,007,000,000 ($90.0 billion) | Yes |
| Net Income | $35.8 billion | $35,766,000,000 ($35.8 billion) | Yes |

yfinance output (most recent quarter ended 2026-06-30):

```
MSFT most recent quarter ended: 2026-06-30
Total Revenue: $90,007,000,000  (= $90.0 billion)
Net Income:    $35,766,000,000  (= $35.8 billion)
```

Explanation: Both sources agree for the quarter ended June 30, 2026. yfinance reports exact dollar amounts, while the press release states figures rounded to one decimal in billions. After rounding, the values are identical, so there is no period mismatch, definition difference or extraction error.

## 5D — Pipeline Integrity Checks

| Check | Expected | Actual | Pass/Fail |
|---|---|---|---|
| `earnings_history.csv` row count | Up to 20 (5 companies × 4 quarters) | 20 | Pass |
| `executive_events.csv` row count | At least 0 (document actual) | 34 | Pass |
| `corporate_events_timeline.csv` created | Yes | Yes (34 rows) | Pass |
| Rows with all three fields `"NOT_FOUND"` | 0 (investigate if > 0) | 0 | Pass |

**Notes on the executive data:** In `executive_events.csv`, `person_name` is NOT_FOUND in 14 of 34 rows, `title` in 22, and `effective_date` in 14. Most unnamed rows come from Item 5.02 filings about compensation, board elections or plan amendments rather than a single person joining or leaving, or from filings where the wording is too complex for pattern matching. The pipeline records these as NOT_FOUND instead of skipping them, so every Item 5.02 filing is accounted for. On the first run the pipeline also mis-read phrases like "Hardware Engineering", "Base Salary" and "Covenant Not" as names; this was fixed by filtering non-name words and ignoring SEC jargon such as "named executive officers".
