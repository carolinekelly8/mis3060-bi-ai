"""
HW3 - Executive Events Pipeline (SEC 8-K, Item 5.02)
MIS3060 Business Intelligence with AI

Finds every 8-K with Item 5.02 (Departure/Appointment of Directors or Officers)
filed in the past 12 months for five companies, extracts each departure or
appointment, and saves them to hw03/executive_events.csv.

Run from the repo root:
    python hw03/hw03_executives.py
"""

import csv
import re
import time
from datetime import date, timedelta
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
HEADERS = {"User-Agent": "MIS3060 Villanova ckelly80@villanova.edu"}
PAUSE_SECONDS = 0.2
NOT_FOUND = "NOT_FOUND"
CUTOFF_DATE = (date.today() - timedelta(days=365)).isoformat()

COMPANIES = [
    {"company": "Apple Inc.",            "ticker": "AAPL", "cik": "0000320193"},
    {"company": "Microsoft Corporation", "ticker": "MSFT", "cik": "0000789019"},
    {"company": "NVIDIA Corporation",    "ticker": "NVDA", "cik": "0001045810"},
    {"company": "JPMorgan Chase & Co.",  "ticker": "JPM",  "cik": "0000019617"},
    {"company": "Walmart Inc.",          "ticker": "WMT",  "cik": "0000104169"},
]

OUTPUT_CSV = Path(__file__).resolve().parent / "executive_events.csv"
CSV_COLUMNS = ["company", "ticker", "cik", "filing_date", "event_type",
               "person_name", "title", "effective_date"]


# ---------------------------------------------------------------------------
# HTTP helper - every request goes through here (User-Agent + pause)
# ---------------------------------------------------------------------------
def sec_get(url):
    response = requests.get(url, headers=HEADERS, timeout=30)
    time.sleep(PAUSE_SECONDS)
    response.raise_for_status()
    return response


def html_to_text(html):
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    text = soup.get_text(separator=" ").replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


# ---------------------------------------------------------------------------
# Find Item 5.02 8-Ks from the past 12 months
# ---------------------------------------------------------------------------
def get_502_filings(cik):
    data = sec_get(f"https://data.sec.gov/submissions/CIK{cik}.json").json()
    recent = data["filings"]["recent"]
    filings = []
    for i, form in enumerate(recent["form"]):
        items = recent["items"][i] or ""
        filing_date = recent["filingDate"][i]
        if form == "8-K" and "5.02" in items and filing_date >= CUTOFF_DATE:
            filings.append({
                "filing_date": filing_date,
                "accession": recent["accessionNumber"][i],
                "primary_doc": recent["primaryDocument"][i],
            })
    return filings


def filing_doc_url(cik, accession, primary_doc):
    return (f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/"
            f"{accession.replace('-', '')}/{primary_doc}")


def get_item_502_section(text):
    """Return just the Item 5.02 section (up to the next Item or signature block)."""
    best = ""
    for match in re.finditer(r"Item\s*5\.02", text, re.I):
        rest = text[match.end():]
        end = re.search(r"Item\s*\d\.\d{2}|SIGNATURES?\b", rest)
        section = rest[:end.start()] if end else rest[:5000]
        if len(section) > len(best):   # skip short mentions like a table of contents
            best = section
    best = best or text
    # Drop the standard Item 5.02 heading ("Departure of Directors or Certain Officers; ...")
    best = re.sub(r"^\s*[.:]?\s*Departure of Directors.*?Certain Officers\.?", "", best, count=1, flags=re.I)
    return best


# ---------------------------------------------------------------------------
# Extraction helpers
# ---------------------------------------------------------------------------
DEPARTURE = re.compile(
    r"\b(resign(?:ed|s|ing|ation)?|retir(?:e|ed|es|ing|ement)|"
    r"step(?:s|ped|ping)? down|depart(?:s|ed|ing|ure)?|"
    r"terminat(?:e|ed|ion)|will leave|not stand for re-?election)\b", re.I)
APPOINTMENT = re.compile(
    r"\b(appoint(?:s|ed|ing|ment)?|elect(?:s|ed)?|named|promot(?:e|ed|ion)|"
    r"hired|will join|will succeed|succeed(?:s|ed|ing)?)\b", re.I)

# SEC jargon that contains event words but is NOT an event
FALSE_TRIGGERS = re.compile(
    r"named executive officers?|retirement (?:plan|savings|benefits?|eligib\w*)|"
    r"termination of employment|upon (?:his|her|their) (?:retirement|termination)|"
    r"in the event of|elected to (?:defer|receive)", re.I)

MONTHS = ("January|February|March|April|May|June|July|August|September|"
          "October|November|December")
DATE = rf"(?:{MONTHS})\s+\d{{1,2}},\s+\d{{4}}"

# Capitalized words that look like names but are not people
NOT_NAME_WORDS = set("""
The On In As Of And For With By Board Directors Director Company Corporation Inc
Chief Executive Officer Financial Operating Technology Legal Marketing People
President Vice Senior General Counsel Secretary Treasurer Chair Chairman
Chairwoman Lead Independent Committee Compensation Audit Nominating Governance
Human Resources Annual Meeting Shareholders Stockholders Section Form Item
Securities Exchange Act Commission Agreement Plan Apple Microsoft NVIDIA Nvidia
JPMorgan Chase Walmart Bank America Group Global International Operations
Effective Following Mr Ms Mrs Dr Retirement Also There No Such Her His Their
Principal Accounting Controller Global Head Executive Worldwide Services
Departure Election Appointment Certain Officers Arrangements Compensatory Directors
CEO CFO COO CTO CAO EVP SVP Hardware Engineering Transition Date Target Award
Opportunity Achievement Fiscal Year Base Salary Covenant Not Consumer Community
Banking Commercial Investment Asset Wealth Management Stock Restricted Units
Performance Cash Bonus Incentive Long Short Term Equity Grant Letter Offer
Separation Release Non Competition Agreement Compete Solicitation Employment Severance
Change Control Retail Sam's Club Store Stores Product Products Software Cloud
Data Center Region Americas Europe Asia Pacific Division Business Segment
Enterprise Infrastructure Research Development Sales Supply Chain Strategy
Communications Policy Affairs Office Proxy Statement Current Report
Exhibit Press Release Registrant Holdings Corp LLC Trust United States Delaware
""".split()) | set(MONTHS.split("|"))

NAME = re.compile(
    r"\b(?:(?:Mr|Ms|Mrs|Dr)\.\s+)?"
    r"([A-Z][a-zA-Z'\-]+(?:\s+[A-Z]\.)?(?:\s+[A-Z][a-zA-Z'\-]+){1,2})\b")

TITLE = re.compile(
    r"\b(?:as(?: the| its| our| a| an)?|position of|role of|serve as|serving as|"
    r"named|appointed|elected|promoted to|become)\s+"
    r"((?:(?:Executive|Senior|Vice|Chief|President|General|Deputy|Co-|Lead|Independent|"
    r"Principal|Global|Worldwide|Corporate|CEO|CFO|COO|Chairman|Chair|Head|Treasurer|"
    r"Controller|Secretary)[\w\-]*\s*)"
    r"(?:(?:[A-Z][\w\-&]*|of|and|the|&)\s*){0,10})")


def is_not_name_word(word):
    """True for words like 'CEO', 'Agreements', 'Non-Competition'."""
    word = word.strip(".,")
    parts = [word] + word.split("-")
    return any(p in NOT_NAME_WORDS or p.rstrip("s") in NOT_NAME_WORDS for p in parts if p)


def clean_name(candidate):
    words = candidate.split()
    while words and is_not_name_word(words[0]):
        words.pop(0)                      # drop leading titles like "CEO"
    if len(words) < 2 or any(is_not_name_word(w) for w in words):
        return None
    if len(words) == 2 and len(words[1].rstrip(".")) == 1:
        return None                       # "John D." is not a full name
    return " ".join(words)


def find_names(sentence):
    names = []
    for match in NAME.finditer(sentence):
        name = clean_name(match.group(1))
        if name and not any(name in n or n in name for n in names):
            names.append(name)
    return names


TITLE_START = (r"(?:Executive|Senior|Vice|Chief|President|General|Deputy|Co-|Lead|"
               r"Principal|Global|Corporate|CEO|CFO|COO|Chairman|Chair|Head|Treasurer|"
               r"Controller|Secretary)")
TITLE_WORDS = r"(?:(?:[A-Z][\w\-&']*|of|and|the|&)\s*){0,10}"


def find_title(sentence, name=None, event_type=None):
    # Appointments: the NEW title usually follows "as"/"named"/"appointed"
    if event_type == "appointment":
        match = TITLE.search(sentence)
        if match:
            return re.sub(r"\s+(of|and|the|&)\s*$", "", match.group(1).strip()).strip(" ,.")
    # Departures: the CURRENT title usually follows the name ("Jane Doe, CFO, ...")
    if name and name != NOT_FOUND:
        after = re.search(re.escape(name) + r",?\s+(?:the\s+|our\s+|its\s+)?(?:Company's\s+|Firm's\s+)?"
                          r"(" + TITLE_START + r"[\w\-]*\s*" + TITLE_WORDS + ")", sentence)
        if after:
            return re.sub(r"\s+(of|and|the|&)\s*$", "", after.group(1).strip()).strip(" ,.")
    match = TITLE.search(sentence)
    if match:
        title = re.sub(r"\s+(of|and|the|&)\s*$", "", match.group(1).strip())
        return title.strip(" ,.")
    if re.search(r"\b(member of the Board|director)\b", sentence, re.I):
        return "Director"
    return NOT_FOUND


def find_effective_date(sentence, section):
    for source in (sentence, section):
        match = re.search(rf"effective(?: as of| on)?\s+({DATE})", source, re.I)
        if match:
            return match.group(1)
    match = re.search(rf"\b(?:on|as of)\s+({DATE})", sentence)
    if match:
        return match.group(1)
    return NOT_FOUND


def extract_events(section):
    """Return a list of event dicts - one per person / event found."""
    sentences = re.split(r"(?<=[.;])\s+(?=[A-Z(])", section)
    events, seen = [], set()

    for sentence in sentences:
        # Skip boilerplate that mentions these words but is not an event
        if re.search(r"no (?:arrangements|family relationships|transactions)", sentence, re.I):
            continue
        sentence_for_keywords = FALSE_TRIGGERS.sub(" ", sentence)
        has_dep = bool(DEPARTURE.search(sentence_for_keywords))
        has_app = bool(APPOINTMENT.search(sentence_for_keywords))
        if not (has_dep or has_app):
            continue

        event_type = "both" if (has_dep and has_app) else ("departure" if has_dep else "appointment")
        names = find_names(sentence) or [NOT_FOUND]

        for name in names:
            key = (name, event_type) if name != NOT_FOUND else (NOT_FOUND, event_type)
            if key in seen or (name != NOT_FOUND and any(
                    k[0] != NOT_FOUND and (name in k[0] or k[0] in name) for k in seen)):
                continue   # same person already recorded from an earlier sentence
            seen.add(key)
            events.append({
                "event_type": event_type,
                "person_name": name,
                "title": find_title(sentence, name, event_type),
                "effective_date": find_effective_date(sentence, section),
            })

    # If named events were found, drop the unnamed duplicates of the same type
    named_types = {e["event_type"] for e in events if e["person_name"] != NOT_FOUND}
    events = [e for e in events
              if e["person_name"] != NOT_FOUND or e["event_type"] not in named_types]
    return events


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------
def main():
    rows = []
    print(f"Looking for Item 5.02 filings on or after {CUTOFF_DATE}")

    for co in COMPANIES:
        ticker, cik = co["ticker"], co["cik"]
        print(f"\n=== {co['company']} ({ticker}) ===")

        try:
            filings = get_502_filings(cik)
        except Exception as err:
            print(f"WARNING: could not load EDGAR submissions for {ticker}: {err}")
            continue

        if not filings:
            print(f"{ticker}: No executive events in past 12 months")
            continue

        for filing in filings:
            try:
                url = filing_doc_url(cik, filing["accession"], filing["primary_doc"])
                text = html_to_text(sec_get(url).text)
                section = get_item_502_section(text)
                events = extract_events(section)

                if not events:
                    # Item 5.02 also covers compensation/plan changes - keep a
                    # NOT_FOUND row so the filing is not silently dropped
                    events = [{"event_type": NOT_FOUND, "person_name": NOT_FOUND,
                               "title": NOT_FOUND, "effective_date": NOT_FOUND}]

                for event in events:
                    row = {"company": co["company"], "ticker": ticker, "cik": cik,
                           "filing_date": filing["filing_date"], **event}
                    rows.append(row)
                    print(f"{ticker} | {filing['filing_date']} | {event['event_type']} | "
                          f"{event['person_name']} | {event['title']}")

            except Exception as err:
                print(f"WARNING: {ticker} {filing['filing_date']} - error processing filing: {err}")
                continue

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nSaved {len(rows)} events to {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
