My question: We have credit score, DTI, and annual income for every borrower, but they're currently just three separate columns rather than a combined risk indicator. Credit score reflects payment history and DTI reflects repayment capacity — two different dimensions of risk. What standard techniques do lenders use to combine attributes like these into a single risk score or segment, and how might doing that change what our current default rate (about 4.5% of the portfolio) is really telling us versus looking at each attribute in isolation? 
Claude response: Combining credit score, DTI, and income into a unified risk measure is standard practice in consumer lending — here's how it's typically done and why it matters for your default rate.

Techniques for combining the attributes

Statistical scorecards (the classic approach). This is how FICO-style scores are built internally at most lenders. Each variable is binned (e.g., DTI into ranges), and each bin gets a "weight of evidence" (WOE) value based on how it separates good vs. bad outcomes historically. A logistic regression is then fit across these transformed variables, and the coefficients determine how much each one contributes to the final score. The output is scaled to a points system (often calibrated so a fixed point increase halves the odds of default — "points to double the odds"). This handles non-linearity within each variable and lets you see the relative weight each dimension carries.

Follow up: How many borrowers do we need in each cell before its default rate is a reliable signal rather than noise?
