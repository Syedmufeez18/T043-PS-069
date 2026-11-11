# PS-069 · Scholarship Eligibility and Disbursement Engine (Team T043)

Command-file driven Python 3.10+ back-end engine for scholarship screening, scheme precedence resolution, district reservation ranking, multi-run instalment disbursement with runtime gates, waitlist movement, and annual renewals.

## Project Structure

```text
T043-PS-069/
├── engine/
│   ├── __init__.py
│   ├── models.py       # Dataclasses for schemes, applicants, ledger & renewals
│   ├── loader.py       # CSV/command-file parsers & date/money helpers
│   ├── rules.py        # Business rules BR-01 through BR-12
│   └── engine.py       # Command processor & CSV report generator
├── tests/
│   └── test_engine.py  # Unit tests for BR-01..BR-12, EC-01..EC-08 & sample data
├── T043-PS-069-sample-data/
├── output/             # Generated CSV reports
├── main.py             # CLI entry point
├── DESIGN.md           # Business rule registry & viva design notes
└── README.md
```

## How to Run

Run against the included sample data pack (`T043-PS-069-sample-data`) and export CSV reports to `output/`:

```powershell
python main.py
```

Custom input/output directories:

```powershell
python main.py --data-dir path\to\data --output-dir path\to\output
```

## Generated Output CSVs

- `output/eligibility_matrix.csv`
- `output/sanction.csv`
- `output/disbursement_ledger.csv`
- `output/renewal_decisions.csv`
- `output/utilisation.csv`

## How to Run Tests

```powershell
python -m unittest discover -s tests -v
```
