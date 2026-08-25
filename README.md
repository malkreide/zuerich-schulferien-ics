# Zürich Schulferien ICS Feed

![Version](https://img.shields.io/badge/version-2.0.0-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Python](https://img.shields.io/badge/python-3.10+-blue)

> Subscribable iCal feed for Zurich public school holidays, generated from Open Data Zurich (CKAN)

🇩🇪 [Deutsche Version](README.de.md)

> **Note:** This is an independent open-source project, not an official service
> of the City of Zurich. Data source: [Open Data Zürich](https://data.stadt-zuerich.ch/dataset/ssd_schulferien)
> (dataset `ssd_schulferien`, CC-0-like open government data).

## Overview

The City of Zurich publishes school holidays as per-school-year static ICS
files, which users must re-download and re-import every year. This project
turns the underlying open data into a **permanently subscribable** iCalendar
feed under a stable URL: calendar apps poll it automatically, and changes to
holiday dates propagate to all subscribers without any manual action.

A GitHub Actions workflow fetches the CKAN datastore nightly, generates an
RFC 5545-compliant `.ics` file, and deploys it to GitHub Pages.

## Subscribe

A human-readable landing page with step-by-step subscription instructions is
published at
[malkreide.github.io/zuerich-schulferien-ics](https://malkreide.github.io/zuerich-schulferien-ics/)
— point non-technical users there rather than at this README.

Stable feed URL:

```
https://malkreide.github.io/zuerich-schulferien-ics/ferien.ics
```

The same data is published in three cuts — subscribe to one of them:

| Feed | Contents |
|---|---|
| `ferien.ics` | Holidays and individual school-free days. **The default.** |
| `nur-ferien.ics` | Only the multi-day closures, no single days |
| `alles.ics` | Additionally the public holidays |

`ferien.ics` is deliberately left unchanged: people are already subscribed to
that URL, and narrowing it after the fact would remove dates from their
calendars without anyone asking.

| Platform | How to subscribe |
|---|---|
| Apple Calendar (iOS/macOS) | Open `webcal://malkreide.github.io/zuerich-schulferien-ics/ferien.ics` |
| Google Calendar / Android | Open `https://calendar.google.com/calendar/r?cid=webcal%3A%2F%2Fmalkreide.github.io%2Fzuerich-schulferien-ics%2Fferien.ics` and confirm |
| Other clients (Nextcloud, Thunderbird, …) | Add the raw HTTPS URL as a calendar subscription |

**Android users:** do not simply tap the HTTPS link in a browser — that
downloads a one-time static copy that never updates. Use the Google Calendar
link above instead.

## Verifying the feed

The feed is UTF-8 (no BOM, CRLF line endings). GitHub Pages serves it as
`Content-Type: text/calendar` **without** a `charset` parameter — response
headers are not configurable there. Some clients then guess wrong and render
umlauts as mojibake (`ZÃ¼rich` instead of `Zürich`). This affects the fetch
only, not the file.

Known case: **Windows PowerShell 5.1** decodes a response without `charset`
as ISO-8859-1. Set the encoding explicitly when inspecting the feed:

```powershell
# Windows PowerShell 5.1 — force UTF-8
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$r = [Net.WebClient]::new()
$r.Encoding = [Text.Encoding]::UTF8
$r.DownloadString("https://malkreide.github.io/zuerich-schulferien-ics/ferien.ics") -split "`r`n" | Select-Object -First 20
```

PowerShell 7+ (`pwsh`) defaults to UTF-8, so plain `Invoke-WebRequest` works
there. So does `curl`:

```bash
curl -s https://malkreide.github.io/zuerich-schulferien-ics/ferien.ics | head -20
```

Calendar clients (Apple Calendar, Google Calendar, Thunderbird, Nextcloud)
treat iCalendar as UTF-8 per RFC 5545 and are unaffected.

## Features

- Nightly automated refresh from the single source of truth (CKAN datastore)
- **Year overview** on the landing page — current and next school year as a
  table, no subscription needed
- **Reproducible output** — `DTSTAMP` comes from the source data, not the wall
  clock. Same input, same bytes: the nightly run no longer makes every
  subscriber re-download the feed
- **School entries only** — plain public holidays are filtered out, since they
  almost always fall inside a school-free block or on a weekend anyway
- **Titles fit a calendar** — the `Schulen Stadt Zürich schulfrei:` prefix is
  dropped and trailing parentheticals move into the description
- **`Schulschluss 12 Uhr` is a timed event at noon**, not an all-day one — that
  day is a short school day, not a day off
- Cutoff at the start of the year before last — no backlog reaching to 2018 in your calendar
- All-day events (`VALUE=DATE`) with correct exclusive end dates
- Deterministic SHA-256 UIDs over the raw source record — title changes update
  existing subscriptions in place instead of resyncing them
- `TRANSP:TRANSPARENT` — holidays never block your free/busy availability
- Sanity gate: implausible or truncated API responses fail the pipeline
  instead of overwriting the last known-good feed
- **Warns instead of running out quietly**: the build fails when the source
  reaches less than 180 days ahead, or when the running school year is missing —
  roughly half a year before the feed would go empty
- Fixture-based `pytest` suite that runs offline in CI
- Zero servers, zero secrets: GitHub Actions (OIDC) + GitHub Pages

## What the feed does not cover

- **Public holidays.** They exist in the source dataset but are deliberately
  excluded (see above). Calendar apps ship a Swiss holiday calendar of their own.
- **School-specific dates.** Staff training days, parent-teacher meetings and
  project weeks are set per school and are not part of the city-wide dataset.
- **Childcare.** A school-free day says nothing about whether after-school care
  or holiday childcare is open. No open data exists for this — ask your school.

## Data quirks worth knowing

- The CKAN `end_date` is **already exclusive** (iCal convention). Sportferien
  2026 run Feb 9–20 and are stored as `2026-02-09 → 2026-02-21`. The script
  therefore applies **no** `+1 day` correction — adding one would make every
  holiday a day too long.
- The dataset mixes school entries (prefixed `Schulen Stadt Zürich`) with plain
  public holidays. In the window from 2024 that is 76 school entries against 97
  holidays — 94 of which fall entirely inside an already school-free block, and
  22 of which land on weekends only. Only the school entries are published.
- Source titles run up to 137 characters. After cleanup the longest is 42; the
  remainder is preserved as the event `DESCRIPTION`.
- Some single-day records ship `end_date == start_date`; these are normalised
  to proper one-day events.
- Minor source inconsistencies — `Schulschluss 12 Uhr` alongside
  `Schulschluss um 12 Uhr`, `(KW29-33)` alongside `(KW 29-33)` — are normalised.
- The feed starts on 1 January of the year before last (`CUTOFF_YEARS_BACK = 2`,
  i.e. `2024-01-01` on 2026-08-22). The
  CKAN dataset reaches back to 2018; unfiltered, roughly two thirds of the
  entries would be pure history. An event straddling the cutoff (e.g.
  Weihnachtsferien 2023/24) is kept **in full** — the filter never truncates
  an ongoing holiday.
- UIDs hash `(raw summary, start, end)` — deliberately the *uncleaned* summary,
  so shortening a title updates existing subscriptions in place instead of
  resyncing them. A changed date still syncs to clients as "old event removed,
  new event added" rather than an in-place update. This is intentional: it keeps
  the generator stateless.

- The city publishes these dates **twice**: as the CKAN dataset this feed is
  built from, and as one static `.ics` per school year on the
  [Schulferien page](https://www.stadt-zuerich.ch/de/bildung/volksschule/schulferien.html).
  `scripts/compare_official_ics.py` checks the two against each other. As of
  2026-08-24, across all four offered school years, 104 records are identical
  and nothing differs unexplained. The only two systematic differences favour
  CKAN: the per-year `.ics` files cut the summer holidays at the 1 August
  school-year boundary (CKAN carries the block whole), and CKAN holds one
  same-span duplicate among the public holidays (`Pfingsten` /
  `Pfingstsonntag`, 2029-05-20) that the feed filters out anyway. There is
  therefore nothing in the `.ics` handover that the open dataset lacks.

## Prerequisites

- Python 3.10+
- `requests`, `icalendar` (see `requirements.txt`)

## Usage

```bash
pip install -r requirements-dev.txt
pytest -q                 # test suite, runs offline against fixtures
python generate_ics.py    # writes public/ferien.ics + public/index.html

python scripts/compare_official_ics.py   # needs network: compare both of the city's exports
```

## Project Structure

```
zuerich-schulferien-ics/
├── generate_ics.py           # fetch CKAN → filter → build ICS + page → sanity gate
├── tests/                    # pytest suite on fixtures, no network access
├── scripts/compare_official_ics.py  # cross-check against the city's own .ics downloads
├── requirements.txt
├── requirements-dev.txt
├── web/index.html            # landing page template (subscription instructions)
├── public/ferien.ics         # generated feed (deployed to GitHub Pages)
├── public/index.html         # rendered landing page (deployed alongside)
├── .github/workflows/deploy.yml    # nightly cron + manual trigger, OIDC deploy, failure alarm
└── .github/workflows/keepalive.yml # monthly heartbeat, keeps the cron from being auto-disabled
```

## Changelog

See [CHANGELOG.md](CHANGELOG.md)

## Contributing

Contributions are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md).

## Security

Please report vulnerabilities as described in [SECURITY.md](SECURITY.md).

## License

MIT License — see [LICENSE](LICENSE)

## Author

Hayal Özkan · [malkreide](https://github.com/malkreide)
