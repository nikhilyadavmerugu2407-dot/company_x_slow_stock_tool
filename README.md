# Company X — Slow Stock Action Tool

A Streamlit application for the Management Trainee – Technology & Data Management case study.

## What it does

1. Accepts either:
   - one Excel workbook containing all four required datasets, or
   - the four separate Excel files.
2. Validates and cleans the data.
3. Handles pack-size SWITCH relationships.
4. Excludes inactive items and flags inactive stock.
5. Calculates aged stock, aged value, average monthly sales and months to clear.
6. Classifies items into Red List, No Action and Push in the required order.
7. Creates ranked customer targets for Push items.
8. Exports the analysis to Excel.

## Files

- `app.py` — Streamlit user interface.
- `analysis_engine.py` — data loading, cleaning, business rules and Excel export.
- `requirements.txt` — Python dependencies.
- `TEST_RESULTS.md` — validation results from the supplied case data.
- `.gitignore` — prevents accidental upload of raw Excel files.

## Run locally

1. Install Python 3.10+.
2. Open a terminal in this folder.
3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Start the app:

```bash
streamlit run app.py
```

5. Open the browser URL shown by Streamlit.

## Deploy

Push this folder to GitHub and deploy `app.py` using Streamlit Community Cloud.

Do not commit the case-study Excel data to the public repository.

## Important case-study design choices

- SWITCH relationships are merged under the replacement/new SKU.
- Inactive items are excluded from the main analysis.
- Aged quantity = 91–180 days + 180+ days.
- Average monthly sales = six-month quantity / 6.
- Months to clear = total stock / average monthly sales.
- Classification order: Red List → No Action → Push.
- Push customers must have six-month purchase value > ₹1,00,000.
- Customer bucket priority: 1 → 2 → 3.
- Within a bucket, customers are sorted by six-month purchase value descending.

## AI disclosure

This project was developed with AI assistance. AI was used for application scaffolding, data-processing code, debugging support and review of edge cases. The business rules and final outputs were checked against the supplied case data before submission.
