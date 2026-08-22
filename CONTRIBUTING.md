# Contributing

Contributions are welcome — bug reports, data quality findings, and pull
requests alike.

## Development setup

```bash
pip install -r requirements.txt
python generate_ics.py        # writes public/ferien.ics
```

## Before opening a pull request

- Run `ruff check .` and `ruff format --check .`
- Run `python generate_ics.py` against the live API; the sanity gate must pass
- Do **not** add a `+1 day` correction to `end_date` — the source data is
  already exclusive (see comments in `generate_ics.py`)

## Commit style

Short, imperative subject lines. Reference issues where applicable.
