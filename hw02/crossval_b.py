import csv

EXCLUDED = {"Sell", "Deposit", "Withdrawal", "Dividend", "Advisory Fee"}

total = 0
excluded = 0
with open("data/raw/fact_transactions.csv", newline="", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        total += 1
        if row["txn_type"] in EXCLUDED:
            excluded += 1

print(f"Total rows:    {total}")
print(f"Excluded rows: {excluded}")
print(f"Remaining:     {total - excluded}")