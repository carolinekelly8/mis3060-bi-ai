# HW3 AI Usage Log

All work was done in Claude Cowork. The three prompts below were sent in one Cowork conversation (the scripts were written to hw03/ and run in the VS Code terminal).

## Prompt 1 — Specification A (Earnings Pipeline)

Prompt sent: *"Read my specifications.md and write hw03_earnings.py and hw03_executives.py from Spec A and Spec B, then write hw03_timeline.py from the Part 4 prompt."* The full Specification A text from specifications.md is below.


Write a Python script using `requests` and `beautifulsoup4` that does the following:

1. Set the HTTP header `User-Agent: "MIS3060 Villanova ckelly80@villanova.edu"` on every single request, not just the first one. Pause 0.2 seconds between requests so the SEC doesn't block us.
2. Loop through these five companies: Apple (AAPL, CIK 0000320193), Microsoft (MSFT, 0000789019), NVIDIA (NVDA, 0001045810), JPMorgan Chase (JPM, 0000019617), Walmart (WMT, 0000104169).
3. For each company, download `https://data.sec.gov/submissions/CIK{cik}.json`. In `filings.recent`, keep only filings where `form` is "8-K" and the `items` field contains "2.02".
4. Keep the 4 most recent of those filings for each company.
5. For each filing, build the filing index URL (`https://www.sec.gov/Archives/edgar/data/{cik without leading zeros}/{accession number without dashes}/`), find the earnings press release exhibit (usually a `.htm` file with "ex99" in the name), download it, and strip the HTML down to plain text.
6. If the press release exhibit can't be found, print a warning and move on to the next filing. The script must never crash.
7. From the plain text, extract: quarterly revenue, diluted EPS, net income, and the reporting period (e.g., "fourth quarter fiscal 2024"). Companies word revenue differently — Apple says "net sales," JPMorgan says "net revenue" — so the patterns should handle that.
8. If a field can't be found, store the text "NOT_FOUND" — never leave it blank or store None.
9. Print each row as it's processed like this: `[Ticker] | [Period] | Revenue: $X | EPS: $X | Net Income: $X`
10. Save all rows to `hw03/earnings_history.csv` with columns: company, ticker, cik, filing_date, period, revenue_reported, eps_diluted, net_income. Print a message confirming the file was saved.
11. Record whether revenue was stated in millions or billions.


## Prompt 2 — Specification B (Executive Events Pipeline)


Write a Python script using `requests` and `beautifulsoup4` that does the following:

1. Set the HTTP header `User-Agent: "MIS3060 Villanova ckelly80@villanova.edu"` on every request, with the same 0.2-second pause between requests.
2. Loop through the same five companies and CIKs as Specification A.
3. For each company, download the EDGAR submissions JSON and keep only 8-K filings where `items` contains "5.02" and `filingDate` is within the last 12 months from today.
4. For each matching filing, download the main 8-K document and strip the HTML to plain text.
5. From the text, extract: event type ("departure", "appointment", or "both"), the person's full name, their title, and the effective date. Departure words include resign, retire, step down, depart. Appointment words include appoint, elect, named, promote.
6. If one filing reports more than one event (e.g., a departure and an appointment), create a separate row for each event.
7. If a field can't be found, store "NOT_FOUND".
8. Print each event as it's processed: `[Ticker] | [Date] | [Event Type] | [Name] | [Title]`
9. If a company has no Item 5.02 filings in the last 12 months, print `[Ticker]: No executive events in past 12 months` and continue. This is valid data, not an error.
10. Save all events to `hw03/executive_events.csv` with columns: company, ticker, cik, filing_date, event_type, person_name, title, effective_date. Print a message confirming the file was saved.
11. Wrap each filing in try/except so one bad filing doesn't stop the whole script.
## Prompt 3 — Timeline (Part 4 prompt, sent as written in the assignment)

> Write a Python script that reads `hw03/earnings_history.csv` and `hw03/executive_events.csv`. Do the following:
>
> 1. For each executive event in the events table, calculate the number of days between the executive event's `filing_date` and the nearest earnings filing date for the same company in the earnings table. Call this `days_to_nearest_earnings`.
> 2. Add a column `event_timing` that categorizes each executive event as: `'before earnings'` if the event came before the nearest earnings filing, `'after earnings'` if it came after, or `'same week'` if within 7 days of an earnings filing.
> 3. Save the combined table to `hw03/corporate_events_timeline.csv` with all columns from both source tables plus `days_to_nearest_earnings` and `event_timing`.
> 4. Print a summary: for each company, list any executive events and whether they occurred before or after the nearest earnings announcement.
> 5. Print a final count: how many events occurred before vs. after an earnings announcement across all five companies.

## Iterations (follow-up fixes)

| Run | Result | What was fixed |
|---|---|---|
| 1 | 12 earnings rows; NVDA and WMT all 4 filings "press release exhibit not found"; 40 executive events including non-names like "Hardware Engineering", "Transition Date", "Base Salary Jen-Hsun", "Covenant Not" | Earnings: find the exhibit using the filing index's official document type (EX-99.1) instead of the file name. Executives: filter non-name words, strip titles like "CEO" from names, ignore SEC jargon like "named executive officers", merge duplicates ("Suzanne Nora Johnson" / "Nora Johnson"), and pick the new title for appointments. |
| 2 | 20 earnings rows; 35 events; NVDA/WMT period labels sometimes pointed at the next quarter's outlook or the prior year; "Non-Competition Agreements" read as a name | Period: search the headline area first and add Walmart ("Q2 FY27") and NVIDIA ("fourth quarter and fiscal 2026") patterns. Names: check each part of hyphenated words. |
| 3 | 20 earnings rows, 34 events, 0 rows with all three earnings fields NOT_FOUND | Final version |

Companies that required iteration: **NVIDIA** and **Walmart** (earnings exhibit and period labels) and all five for executive name extraction. Apple, Microsoft and JPMorgan earnings extracted correctly on the first run.

## Something the script did that I did not specify

The executive pipeline keeps a row with `NOT_FOUND` for every Item 5.02 filing where it cannot identify a departure or appointment (for example, filings about compensation plans or board votes), instead of dropping the filing. I did not ask for this. It was correct in the sense that no filing is silently lost and it follows my NOT_FOUND rule, but it also means those rows are counted as "events" in the timeline, which inflates the before/after counts. A future adjustment would be to label them `other` and exclude them from the timing summary.
