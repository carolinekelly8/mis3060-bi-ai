"""
HW3 - Corporate Events Timeline
MIS3060 Business Intelligence with AI

Joins hw03/earnings_history.csv and hw03/executive_events.csv. For each
executive event, finds the nearest earnings filing for the same company,
measures the gap in days, and labels the event 'before earnings',
'after earnings', or 'same week'. Saves hw03/corporate_events_timeline.csv.

Run from the repo root:
    python hw03/hw03_timeline.py
"""

from pathlib import Path

import pandas as pd

HW_DIR = Path(__file__).resolve().parent
EARNINGS_CSV = HW_DIR / "earnings_history.csv"
EVENTS_CSV = HW_DIR / "executive_events.csv"
OUTPUT_CSV = HW_DIR / "corporate_events_timeline.csv"


def categorize(signed_days):
    """signed_days = event date minus nearest earnings date."""
    if pd.isna(signed_days):
        return "no earnings data"
    if abs(signed_days) <= 7:
        return "same week"
    return "before earnings" if signed_days < 0 else "after earnings"


def main():
    earnings = pd.read_csv(EARNINGS_CSV, dtype=str)
    events = pd.read_csv(EVENTS_CSV, dtype=str)

    earnings["filing_date"] = pd.to_datetime(earnings["filing_date"])
    events["filing_date"] = pd.to_datetime(events["filing_date"])

    # Rename earnings columns so they don't collide with the event columns
    earnings_renamed = earnings.rename(columns={
        c: f"earnings_{c}" for c in earnings.columns if c not in ("ticker",)
    })

    if events.empty:
        print("executive_events.csv has no rows - no executive events to place on the timeline.")
        combined = events.copy()
        for c in earnings_renamed.columns:
            if c != "ticker":
                combined[c] = pd.Series(dtype=str)
        combined["days_to_nearest_earnings"] = pd.Series(dtype=float)
        combined["event_timing"] = pd.Series(dtype=str)
        combined.to_csv(OUTPUT_CSV, index=False)
        print(f"Saved empty timeline to {OUTPUT_CSV}")
        return

    # Step 1-2: nearest earnings filing for the same company
    combined_rows = []
    for _, event in events.iterrows():
        same_co = earnings_renamed[earnings_renamed["ticker"] == event["ticker"]]
        row = event.to_dict()

        if same_co.empty:
            row.update({c: None for c in earnings_renamed.columns if c != "ticker"})
            row["days_to_nearest_earnings"] = None
            row["event_timing"] = categorize(None)
        else:
            gaps = (event["filing_date"] - same_co["earnings_filing_date"]).dt.days
            nearest_idx = gaps.abs().idxmin()
            signed = int(gaps[nearest_idx])
            row.update({c: same_co.loc[nearest_idx, c]
                        for c in earnings_renamed.columns if c != "ticker"})
            row["days_to_nearest_earnings"] = abs(signed)
            row["event_timing"] = categorize(signed)

        combined_rows.append(row)

    combined = pd.DataFrame(combined_rows)
    combined["days_to_nearest_earnings"] = combined["days_to_nearest_earnings"].astype("Int64")
    combined["filing_date"] = pd.to_datetime(combined["filing_date"]).dt.date
    combined["earnings_filing_date"] = pd.to_datetime(combined["earnings_filing_date"]).dt.date
    combined = combined.sort_values(["ticker", "filing_date"])

    # Step 3: save
    combined.to_csv(OUTPUT_CSV, index=False)
    print(f"Saved {len(combined)} rows to {OUTPUT_CSV}\n")

    # Step 4: per-company summary
    print("=== Executive events by company ===")
    for ticker in sorted(set(earnings["ticker"]) | set(events["ticker"])):
        co_events = combined[combined["ticker"] == ticker]
        print(f"\n{ticker}:")
        if co_events.empty:
            print("  No executive events in past 12 months")
            continue
        for _, r in co_events.iterrows():
            print(f"  {r['filing_date']} | {r['event_type']} | {r['person_name']} | "
                  f"{r['title']} -> {r['event_timing']} "
                  f"({r['days_to_nearest_earnings']} days from earnings filed "
                  f"{r['earnings_filing_date']})")

    # Step 5: overall counts
    counts = combined["event_timing"].value_counts()
    print("\n=== Overall timing (all five companies) ===")
    for label in ["before earnings", "after earnings", "same week", "no earnings data"]:
        if label in counts or label != "no earnings data":
            print(f"  {label}: {int(counts.get(label, 0))}")


if __name__ == "__main__":
    main()
