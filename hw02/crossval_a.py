import csv

count = 0
with open("data/raw/fact_transactions.csv", newline="", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        if row["txn_type"] == "Buy":
            count += 1

print(f"Rows where txn_type == 'Buy': {count}")