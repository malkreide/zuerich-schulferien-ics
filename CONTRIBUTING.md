# Contributing

Contributions are welcome — bug reports, data quality findings, and pull
requests alike.

## Development setup

```bash
pip install -r requirements-dev.txt
pytest -q                     # offline, no network needed
python generate_ics.py        # writes public/ferien.ics + public/index.html
```

## Before opening a pull request

- Run `pytest -q` — the suite runs on fixtures and needs no network
- Run `ruff check .` and `ruff format --check .`
- Run `python generate_ics.py` against the live API; the sanity gate must pass
- Do **not** add a `+1 day` correction to `end_date` — the source data is
  already exclusive (see comments in `generate_ics.py`). `pytest` fails loudly
  if you do.
- Only records prefixed `Schulen Stadt Zürich` are published; plain public
  holidays are filtered out on purpose (see the module docstring).
- Before cutting a release, run `python scripts/compare_official_ics.py`. It
  needs network access and checks the CKAN dataset against the city's own
  per-school-year `.ics` downloads — two separate exports of one source of
  truth. A non-zero exit means a school record exists in one and not the
  other, so one of the two is stale.

## Commit style

Short, imperative subject lines. Reference issues where applicable.
