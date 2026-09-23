# HW2 Specification — EDA Script for fact_transactions.csv

## Goal
Write **one single Python script**, saved as `hw02/hw02_eda.py`, that performs a complete exploratory data analysis of Wildcat Capital's transaction data. Every step below must happen in the same file, in a single run. Do not split this into separate scripts. The script will be run from the root of my repository with `python hw02/hw02_eda.py`.

## About the data
The file `data/raw/fact_transactions.csv` holds five years (2020–2024) of client transactions for a wealth management firm. Each row is one transaction: a Buy, Sell, Deposit, Withdrawal, Dividend, or Advisory Fee. The columns include a transaction ID, client ID, advisor ID, security ID, transaction date, transaction type, number of shares, price per share, and dollar amount.

## What the script must do, in this order

1. **Load the data.** Read `data/raw/fact_transactions.csv` into a pandas DataFrame.
2. **Shape.** Print how many rows and columns the dataset has.
3. **Columns and types.** Print every column name along with its data type.
4. **Missing values.** Print how many values are missing in each column.
5. **Descriptive statistics.** For every numeric column, print the count, mean, standard deviation, minimum, 25th percentile, median, 75th percentile, and maximum.
6. **Transaction type breakdown.** For `txn_type`, print how many times each type appears and what percentage of all rows it represents, listed from most common to least common.
7. **Unique entities.** Print how many different clients, advisors, and securities appear in the file.
8. **Date range.** Print the earliest and latest date in `txn_date`.
9. **Duplicates.** Check whether any `txn_id` appears more than once, and print the number of duplicates.
10. **Amount center and shape.** Print the mean, median, and skewness of the `amount` column.
11. **Amount by transaction type.** Group the data by `txn_type`. For each type, print the number of transactions and the mean and median `amount`, rounded to 2 decimal places. Sort the table from highest mean amount to lowest.
12. **Correlations.** Calculate the correlation matrix for `shares`, `price`, and `amount`, rounded to 2 decimal places, and print it. Then list the three strongest correlations between two different variables. Ignore each variable's correlation with itself, and don't count the same pair twice.
13. **Negative shares check.** For each `txn_type`, print the minimum and maximum value of `shares` and how many rows have a negative `shares` value.
14. **Shape warning.** If the dataset does not have exactly 298,772 rows and 9 columns, print a clear warning that the file may be incomplete or incorrect.
15. **Charts.** Create the `hw02/charts/` folder if it doesn't exist, and save three charts there as PNG files:
    - `hist_amount.png`: a histogram of `amount`, with one vertical line at the mean and another at the median. Label each line clearly with its value, and include a title and axis labels.
    - `box_amount_by_type.png`: a horizontal box plot showing the spread of `amount` for each `txn_type`.
    - `scatter_shares_amount.png`: a scatter plot with `shares` on the x-axis and `amount` on the y-axis. Give each `txn_type` its own color and include a legend.
    
    The charts should save to files without popping up windows.
16. **Profile file.** Save everything printed in steps 2 through 13 to a plain-text file at `hw02/hw02_profile.txt`, so the results can be reviewed without re-running the script.
17. **Header comment.** At the very top of the script, include a comment block giving the script name, the dataset it analyzes, the author (Caroline Kelly), and the date it was generated.

## Other expectations
- Use clear section headings in the printed output, numbered to match the steps above, so each result is easy to find.
- Use file paths that work when the script is run from the repository root.
- The script should finish in under two minutes and print a message confirming where the charts and profile were saved.
