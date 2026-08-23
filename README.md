# Zürich Schulferien ICS Feed

![Version](https://img.shields.io/badge/version-1.0.0-blue)
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

| Platform | How to subscribe |
|---|---|
| Apple Calendar (iOS/macOS), Outlook | Open `webcal://malkreide.github.io/zuerich-schulferien-ics/ferien.ics` |
| Google Calendar / Android | Open `https://calendar.google.com/calendar/r?cid=https://malkreide.github.io/zuerich-schulferien-ics/ferien.ics` and confirm |
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
- Cutoff at the start of the year before last — no backlog reaching to 2018 in your calendar
- All-day events (`VALUE=DATE`) with correct exclusive end dates
- Deterministic SHA-256 UIDs — no duplicate events on feed regeneration
- `TRANSP:TRANSPARENT` — holidays never block your free/busy availability
- Sanity gate: implausible or truncated API responses fail the pipeline
  instead of overwriting the last known-good feed
- Zero servers, zero secrets: GitHub Actions (OIDC) + GitHub Pages

## Data quirks worth knowing

- The CKAN `end_date` is **already exclusive** (iCal convention). Sportferien
  2026 run Feb 9–20 and are stored as `2026-02-09 → 2026-02-21`. The script
  therefore applies **no** `+1 day` correction — adding one would make every
  holiday a day too long.
- Some single-day records ship `end_date == start_date`; these are normalised
  to proper one-day events.
- The feed starts on 1 January of the year before last (`CUTOFF_YEARS_BACK = 2`,
  i.e. `2024-01-01` on 2026-08-22). The
  CKAN dataset reaches back to 2018; unfiltered, roughly two thirds of the
  entries would be pure history. An event straddling the cutoff (e.g.
  Weihnachtsferien 2023/24) is kept **in full** — the filter never truncates
  an ongoing holiday.
- UIDs hash `(summary, start, end)`. A changed date syncs to clients as
  "old event removed, new event added" rather than an in-place update. This
  is intentional: it keeps the generator stateless.

## Prerequisites

- Python 3.10+
- `requests`, `icalendar` (see `requirements.txt`)

## Usage

```bash
pip install -r requirements.txt
python generate_ics.py    # writes public/ferien.ics + public/index.html
```

## Project Structure

```
zuerich-schulferien-ics/
├── generate_ics.py           # fetch CKAN → build ICS + page → sanity gate
├── requirements.txt
├── web/index.html            # landing page template (subscription instructions)
├── public/ferien.ics         # generated feed (deployed to GitHub Pages)
├── public/index.html         # rendered landing page (deployed alongside)
└── .github/workflows/deploy.yml  # nightly cron + manual trigger, OIDC deploy
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

Hayal Oezkan · [malkreide](https://github.com/malkreide)
