"""
HW3 Part 5C - Cross-validate earnings with Yahoo Finance (yfinance)

Gets the most recent quarterly revenue and net income for MSFT so they can be
compared with the values extracted from the 8-K press release.

Run from the repo root:
    python hw03/yf_check.py
"""

import yfinance as yf

TICKER = "MSFT"

stock = yf.Ticker(TICKER)
income = stock.quarterly_income_stmt          # columns = quarter-end dates, newest first

latest_quarter = income.columns[0]
revenue = income.loc["Total Revenue", latest_quarter]
net_income = income.loc["Net Income", latest_quarter]

print(f"{TICKER} most recent quarter ended: {latest_quarter.date()}")
print(f"Total Revenue: ${revenue:,.0f}  (= ${revenue / 1e9:.1f} billion)")
print(f"Net Income:    ${net_income:,.0f}  (= ${net_income / 1e9:.1f} billion)")
