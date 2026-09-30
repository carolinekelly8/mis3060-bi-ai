"""
HW3 - Earnings Pipeline (SEC 8-K, Item 2.02)
MIS3060 Business Intelligence with AI

Pulls the 4 most recent earnings press releases (8-K Item 2.02, Exhibit 99)
for five companies from SEC EDGAR, extracts revenue, diluted EPS, net income
and the reporting period, and saves them to hw03/earnings_history.csv.

Run from the repo root:
    python hw03/hw03_earnings.py
"""

import csv
import re
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
# SEC requires a descriptive User-Agent on EVERY request.
HEADERS = {"User-Agent": "MIS3060 Villanova ckelly80@villanova.edu"}
PAUSE_SECONDS = 0.2          # stay well under the SEC's 10 requests/second limit
FILINGS_PER_COMPANY = 4
NOT_FOUND = "NOT_FOUND"

COMPANIES = [
    {"company": "Apple Inc.",            "ticker": "AAPL", "cik": "0000320193"},
    {"company": "Microsoft Corporation", "ticker": "MSFT", "cik": "0000789019"},
    {"company": "NVIDIA Corporation",    "ticker": "NVDA", "cik": "0001045810"},
    {"company": "JPMorgan Chase & Co.",  "ticker": "JPM",  "cik": "0000019617"},
    {"company": "Walmart Inc.",          "ticker": "WMT",  "cik": "0000104169"},
]

OUTPUT_CSV = Path(__file__).resolve().parent / "earnings_history.csv"
CSV_COLUMNS = [
    "company", "ticker", "cik", "filing_date", "period",
    "revenue_reported", "eps_diluted", "net_income",
    # Extra columns (spec item 11): the unit each dollar figure was stated in
    "revenue_unit", "net_income_unit",
]


# ---------------------------------------------------------------------------
# HTTP helper - the ONLY place requests.get() is called, so the User-Agent
# header and the pause are applied to every single request.
# ---------------------------------------------------------------------------
def sec_get(url):
    response = requests.get(url, headers=HEADERS, timeout=30)
    time.sleep(PAUSE_SECONDS)
    response.raise_for_status()
    return response


def html_to_text(html):
    """Strip HTML tags and collapse all whitespace to single spaces."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    text = soup.get_text(separator=" ")
    text = text.replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


# ---------------------------------------------------------------------------
# Step 1-3: find the 4 most recent 8-K filings with Item 2.02
# ---------------------------------------------------------------------------
def get_earnings_filings(cik):
    data = sec_get(f"https://data.sec.gov/submissions/CIK{cik}.json").json()
    recent = data["filings"]["recent"]

    filings = []
    for i, form in enumerate(recent["form"]):
        items = recent["items"][i] or ""
        if form == "8-K" and "2.02" in items:
            filings.append({
                "filing_date": recent["filingDate"][i],
                "accession": recent["accessionNumber"][i],
                "primary_doc": recent["primaryDocument"][i],
            })
    # EDGAR lists newest first, but sort anyway to be safe
    filings.sort(key=lambda f: f["filing_date"], reverse=True)
    return filings[:FILINGS_PER_COMPANY]


# ---------------------------------------------------------------------------
# Step 4-5: locate the press-release exhibit in the filing folder
# ---------------------------------------------------------------------------
def find_press_release_url(cik, accession, primary_doc):
    """Find the earnings press release (Exhibit 99.x) inside a filing.

    Strategy 1: read the filing's index page, which lists every document with
                its official exhibit TYPE (e.g. "EX-99.1"). This works no matter
                what the company named the file (NVIDIA and Walmart use names
                like "q2fy27pr.htm" that don't contain "ex99").
    Strategy 2: fall back to matching "ex99" in the file name.
    Strategy 3: fall back to the largest .htm file that isn't the 8-K cover page.
    """
    cik_no_zeros = str(int(cik))
    accession_no_dashes = accession.replace("-", "")
    folder_url = f"https://www.sec.gov/Archives/edgar/data/{cik_no_zeros}/{accession_no_dashes}/"

    # --- Strategy 1: exhibit type from the filing index page ---------------
    try:
        index_html = sec_get(folder_url + f"{accession}-index.htm").text
        soup = BeautifulSoup(index_html, "html.parser")
        candidates = []
        for row in soup.select("table.tableFile tr"):
            cells = row.find_all("td")
            if len(cells) < 4:
                continue
            doc_type = cells[3].get_text(strip=True).upper()
            link = cells[2].find("a")
            if link and doc_type.startswith("EX-99"):
                name = link.get_text(strip=True)
                if name.lower().endswith((".htm", ".html")):
                    candidates.append((doc_type, name))
        if candidates:
            candidates.sort(key=lambda c: c[0] != "EX-99.1")   # prefer EX-99.1
            return folder_url + candidates[0][1]
    except Exception as err:
        print(f"  note: could not read filing index page ({err}); trying file names")

    # --- Strategy 2: file name contains ex99 -------------------------------
    listing = sec_get(folder_url + "index.json").json()
    items = listing["directory"]["item"]
    htm_items = [i for i in items if i["name"].lower().endswith((".htm", ".html"))]

    ex99 = re.compile(r"ex(hibit)?[-_]?99", re.I)
    ex99_names = sorted((i["name"] for i in htm_items if ex99.search(i["name"])),
                        key=lambda n: not re.search(r"99[-_.]?0?1", n))
    if ex99_names:
        return folder_url + ex99_names[0]

    # --- Strategy 3: largest non-cover-page .htm ---------------------------
    others = [i for i in htm_items
              if i["name"] != primary_doc and "index" not in i["name"].lower()]
    if others:
        biggest = max(others, key=lambda i: int(i.get("size") or 0))
        print(f"  note: using largest attachment {biggest['name']} as the press release")
        return folder_url + biggest["name"]

    print(f"  files in filing: {[i['name'] for i in items]}")
    return None  # caller prints a warning and moves on


# ---------------------------------------------------------------------------
# Step 7: extraction helpers
# ---------------------------------------------------------------------------
MONEY = r"\$\s?([\d,]+(?:\.\d+)?)\s*(billion|million)"

# Words that signal a SEGMENT revenue figure rather than the company total
SEGMENT_WORDS = re.compile(
    r"(data center|gaming|professional visualization|automotive|segment|cloud|"
    r"services|products|iphone|mac|ipad|wearables|intelligent|productivity|"
    r"personal computing|azure|sam's club|international|u\.s\.|ecommerce|"
    r"advertising|search|linkedin|consumer|commercial|markets|banking|"
    r"asset|wealth|investment)\s*$",
    re.I,
)


def _clean_number(value):
    return value.replace(",", "")


def extract_revenue(text):
    """Return (amount, unit). Tries prose first, then the financial table."""
    prose = re.compile(
        r"(?:net sales|net revenues?|total revenues?|revenues?)\b[^$]{0,60}?" + MONEY,
        re.I,
    )
    for match in prose.finditer(text):
        before = text[max(0, match.start() - 40):match.start()]
        if SEGMENT_WORDS.search(before):
            continue  # e.g. "Data Center revenue of $41 billion" - skip segment totals
        return _clean_number(match.group(1)), match.group(2).lower()

    # Fallback: income-statement table, usually "in millions"
    table = re.compile(
        r"(?:Total net sales|Total revenues?|Total net revenues?|Net revenues?|Revenue)"
        r"\s*\$?\s*(\d{1,3}(?:,\d{3})+(?:\.\d+)?)",
        re.I,
    )
    match = table.search(text)
    if match:
        return _clean_number(match.group(1)), "million"
    return NOT_FOUND, NOT_FOUND


def extract_eps(text):
    patterns = [
        r"diluted (?:earnings|net income) per (?:common )?share[^$]{0,60}?\$\s?(\d+\.\d{2})",
        r"earnings per (?:common )?share[^$]{0,40}?\$\s?(\d+\.\d{2})",
        r"(?:earnings|income) per diluted share[^$]{0,40}?\$\s?(\d+\.\d{2})",
        r"(?<!adjusted )(?:GAAP )?EPS (?:of|was|is)\s+\$\s?(\d+\.\d{2})",
        r"Diluted\s*\$\s*(\d+\.\d{2})",   # table fallback
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, text, re.I):
            before = text[max(0, match.start() - 15):match.start()].lower()
            if "adjusted" in before or "non-gaap" in before:
                continue  # we want the GAAP figure
            return match.group(1)
    return NOT_FOUND


def extract_net_income(text):
    """Return (amount, unit)."""
    prose = re.compile(r"net income\b[^$]{0,60}?" + MONEY, re.I)
    for match in prose.finditer(text):
        before = text[max(0, match.start() - 15):match.start()].lower()
        if "adjusted" in before or "non-gaap" in before:
            continue
        return _clean_number(match.group(1)), match.group(2).lower()

    table = re.compile(
        r"(?:Consolidated )?net income(?: attributable to [A-Za-z.,&' ]{3,40}?)?"
        r"\s*\$\s*(\d{1,3}(?:,\d{3})+(?:\.\d+)?)",
        re.I,
    )
    match = table.search(text)
    if match:
        return _clean_number(match.group(1)), "million"
    return NOT_FOUND, NOT_FOUND


QUARTER = r"(?:first|second|third|fourth)"
QUARTER_WORDS = {"1": "first", "2": "second", "3": "third", "4": "fourth"}


def extract_period(text):
    """Find the quarter the press release is REPORTING on.

    Press releases also mention the NEXT quarter (guidance/outlook) and the
    SAME quarter last year, so we look in the headline area (first 1,500
    characters) before searching the whole document.
    """
    patterns = [
        # "Q2 FY27" (Walmart style) -> "second quarter fiscal 2027"
        r"\bQ([1-4])\s*FY\s?'?(\d{2,4})\b",
        # "fourth quarter and fiscal 2026" (NVIDIA year-end style)
        QUARTER + r"[- ]quarter and fiscal(?: year)? \d{4}",
        # "fourth quarter fiscal 2025", "second quarter of fiscal year 2026"
        QUARTER + r"[- ]quarter(?: of)? fiscal(?: year)? \d{4}",
        # "fiscal 2025 third quarter" (Apple style)
        r"fiscal(?: year)? \d{4} " + QUARTER + r"[- ]quarter",
        # "second-quarter 2025" / "third quarter 2025" (JPMorgan style)
        QUARTER + r"[- ]quarter(?: of)? \d{4}",
        # "quarter ended June 30, 2025"
        r"quarter ended [A-Z][a-z]+ \d{1,2}, \d{4}",
        # last resort: just "third quarter"
        QUARTER + r"[- ]quarter",
    ]
    for window in (text[:1500], text):
        for pattern in patterns:
            match = re.search(pattern, window, re.I)
            if not match:
                continue
            if pattern.startswith(r"\bQ"):
                year = match.group(2)
                year = "20" + year if len(year) == 2 else year
                return f"{QUARTER_WORDS[match.group(1)]} quarter fiscal {year}"
            return match.group(0).replace("-", " ").lower()
    return NOT_FOUND


def fmt(amount, unit=""):
    if amount == NOT_FOUND:
        return NOT_FOUND
    return f"${amount} {unit}".strip() if unit and unit != NOT_FOUND else f"${amount}"


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------
def main():
    rows = []

    for co in COMPANIES:
        ticker, cik = co["ticker"], co["cik"]
        print(f"\n=== {co['company']} ({ticker}) ===")

        try:
            filings = get_earnings_filings(cik)
        except Exception as err:
            print(f"WARNING: could not load EDGAR submissions for {ticker}: {err}")
            continue

        if not filings:
            print(f"WARNING: no Item 2.02 8-K filings found for {ticker}")
            continue

        for filing in filings:
            try:
                exhibit_url = find_press_release_url(cik, filing["accession"], filing["primary_doc"])
                if exhibit_url is None:
                    print(f"WARNING: {ticker} {filing['filing_date']} - press release exhibit not found, skipping")
                    continue

                text = html_to_text(sec_get(exhibit_url).text)

                revenue, revenue_unit = extract_revenue(text)
                eps = extract_eps(text)
                net_income, net_income_unit = extract_net_income(text)
                period = extract_period(text)

                row = {
                    "company": co["company"],
                    "ticker": ticker,
                    "cik": cik,
                    "filing_date": filing["filing_date"],
                    "period": period,
                    "revenue_reported": revenue,
                    "eps_diluted": eps,
                    "net_income": net_income,
                    "revenue_unit": revenue_unit,
                    "net_income_unit": net_income_unit,
                }
                rows.append(row)

                print(f"{ticker} | {period} | Revenue: {fmt(revenue, revenue_unit)} | "
                      f"EPS: {fmt(eps)} | Net Income: {fmt(net_income, net_income_unit)}")

            except Exception as err:
                # One bad filing should never stop the whole pipeline
                print(f"WARNING: {ticker} {filing['filing_date']} - error processing filing: {err}")
                continue

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nSaved {len(rows)} rows to {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
