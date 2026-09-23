# HW2 Validation

## 2A — Known-Answer Benchmarks
   | Check | Expected | Your Script Produced | Match? | Notes |
|---|---|---|---|---|
| Dataset shape | (298772, 9) | (298772, 9) | Yes | Section 2; shape check also passed |
| Null count — `security_id` | 101,597 | 101,597 | Yes | `shares` and `price` also have 101,597 nulls |
| Null count — `amount` | 0 | 0 | Yes | |
| Unique `txn_type` values | 6 | 6 | Yes | Buy, Sell, Dividend, Deposit, Advisory Fee, Withdrawal |
| Count of `Buy` transactions | 83,556 | 83,556 | Yes | 27.97% of rows |
| `txn_date` data type | object | datetime64[us] | No | See note below |
| Earliest `txn_date` | 2020-01-01 | 2020-01-01 | Yes | |
| Latest `txn_date` | 2024-12-30 | 2024-12-30 | Yes | |
| Duplicate `txn_id` count | 0 | 0 | Yes | |
| Mean `amount` | $54,075.17 | $54,075.17 | Yes | |
| Median `amount` | $41,220.48 | $41,220.49 | Yes (rounding) | See note below |
| Skewness of `amount` | 1.15 | 1.15 | Yes | Right-skewed |
| Correlation `shares`–`amount` | 0.65 | 0.65 | Yes | Strongest correlation |
| Correlation `price`–`amount` | 0.64 | 0.64 | Yes | |
| Correlation `shares`–`price` | 0.00 | 0.00 | Yes | No relationship |
| Negative `shares` count (Buy only) | 836 | 836 | Yes | Min −499.63; Sell and Dividend have 0 negatives |
| Profile file created | Yes | Yes | Yes | hw02/hw02_profile.txt |
| Chart files created (3) | Yes | Yes | Yes | hist_amount.png, box_amount_by_type.png, scatter_shares_amount.png |
## 2B — Explain the Code and Output

Match? Yes, all the values matched. The only differences were formatting: section 5 printed unrounded numbers (.round(2) had no effect), and the date type showed as datetime64[us].
Flagged: 836 Buy rows with negative shares, 101,597 nulls, only 2,700 of the client IDs up to 3,192 actually used, right-skewed amounts, and very skewed Advisory Fees.
Nulls: Yes. Advisory Fee, Deposit and Withdrawal rows have no security, so security_id, shares and price are blank for those rows.
txn_date: Not at first. It parsed cleanly, but 28% of transactions fall on weekends and the data ends Dec 30. For time series, bad or missing dates silently drop rows, gaps look like zero activity, and weekend trades may distort trading-day trends.
Charts:
Histogram: Matched. I also noticed a big spike near $0 and a sharp drop at $100k.
Box plot: The order was reversed from the table, with Dividend at the bottom.
Scatter: Matched, but the legend lists all 6 types, green (Dividend) hides the other colors, and the negative-share Buys still have positive amounts, which looks like a sign error.
Follow-up: "Did you flag txn_date as a concern?" Claude said no at first, then checked and found no missing days, 28% weekend transactions, and data ending Dec 30.

## 2C — Business Check & Cross-Validation 
Deposit, Withdrawal and Advisory Fee have no security because they're cash movements, not trades of a specific stock or fund. Their counts do add up: 35,981 + 29,850 + 35,766 = 101,597.
Having more Buys than Sells suggests clients are mostly building their portfolios, helped by new deposits and reinvested dividends. For the firm, that likely means assets under management are growing, and so are the advisory fees charged on them.
Subtracting one date string from another raises an error, so days-between can't be calculated, and string sorting can put dates in the wrong order unless they're in YYYY-MM-DD format. The fix is to convert the column with pd.to_datetime() before doing any date math.
Yes, about 108 clients per advisor is plausible, since RIA advisors commonly manage roughly 50–150 client relationships. It would be a concern only well above that, for example 300 or more, where personal service becomes hard to deliver.
A negative share count on a Buy could be a sign error at data entry, or a reversal that cancels an earlier trade. The data points to a sign error, since all 836 rows have positive amounts and none matches an earlier Buy, but this needs further confirmation. 

### Cross Validation
(.venv) (MGT4170) C:\MIS3060\mis3060-bi-ai>python hw02/crossval_a.py
Rows where txn_type == 'Buy': 83556 

(.venv) (MGT4170) C:\MIS3060\mis3060-bi-ai>python hw02/crossval_b.py
Total rows:    298772
Excluded rows: 215216
Remaining:     83556