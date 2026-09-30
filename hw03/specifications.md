# HW3 Specifications

## Specification A — Earnings Pipeline (hw03/hw03_earnings.py)

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

## Specification B — Executive Events Pipeline (hw03/hw03_executives.py)

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