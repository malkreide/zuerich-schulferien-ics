#!/usr/bin/env python3
"""Generate a subscribable iCalendar feed for Zurich public school holidays.

Data source: Open Data Zurich (CKAN), dataset ``ssd_schulferien``
("Ferien und schulfreie Tage der Volksschule der Stadt Zürich").

Design decisions
----------------
- The CKAN ``end_date`` is already *exclusive* (iCal convention), verified
  against official holiday dates (e.g. Sportferien 2026: Feb 9-20 is stored
  as start 2026-02-09, end 2026-02-21). Therefore NO +1 day correction is
  applied. Do not "fix" this.
- UIDs are deterministic SHA-256 hashes over (summary, start, end). A changed
  date therefore appears to clients as "old event removed, new event added",
  which is acceptable for an informational feed and avoids state management.
- The script fails hard (non-zero exit) on implausible data so that a broken
  CKAN response never overwrites the last known-good feed on GitHub Pages.
"""

from __future__ import annotations

import hashlib
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests
from icalendar import Calendar, Event, vText

CKAN_BASE = "https://data.stadt-zuerich.ch/api/3/action/datastore_search"
RESOURCE_ID = "aad477f6-db39-4d1b-92d8-0885f2d363d1"
PAGE_SIZE = 1000
OUTPUT_DIR = Path("public")
OUTPUT_FILE = OUTPUT_DIR / "ferien.ics"
UID_DOMAIN = "zuerich-schulferien-ics.malkreide.github.io"

# Sanity gate thresholds
MIN_EXPECTED_EVENTS = 30
REQUEST_TIMEOUT = 30


def fetch_all_records() -> list[dict]:
    """Fetch every record from the CKAN datastore, verifying completeness."""
    records: list[dict] = []
    offset = 0
    total: int | None = None

    while True:
        resp = requests.get(
            CKAN_BASE,
            params={"resource_id": RESOURCE_ID, "limit": PAGE_SIZE, "offset": offset},
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        payload = resp.json()
        if not payload.get("success"):
            raise RuntimeError(f"CKAN API reported failure: {payload}")

        result = payload["result"]
        total = result["total"]
        batch = result["records"]
        records.extend(batch)

        if not batch or len(records) >= total:
            break
        offset += PAGE_SIZE

    if total is None or len(records) != total:
        raise RuntimeError(
            f"Incomplete fetch: got {len(records)} records, API reports total={total}"
        )
    return records


def parse_date(value: str) -> date:
    """Parse CKAN timestamp strings like '2026-02-09T00:00:00Z' to a date."""
    return datetime.fromisoformat(value.replace("Z", "+00:00")).date()


def make_uid(summary: str, start: date, end: date) -> str:
    raw = f"volksschule-zuerich-{summary}-{start.isoformat()}-{end.isoformat()}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"{digest}@{UID_DOMAIN}"


def build_calendar(records: list[dict]) -> Calendar:
    cal = Calendar()
    cal.add("prodid", "-//zuerich-schulferien-ics//Schulferien Generator//DE")
    cal.add("version", "2.0")
    cal.add("calscale", "GREGORIAN")
    cal.add("method", "PUBLISH")
    # RFC 7986 + de-facto extensions for client display and refresh behaviour
    cal.add("name", "Schulferien Stadt Zürich")
    cal.add("x-wr-calname", "Schulferien Stadt Zürich")
    cal.add(
        "description",
        "Ferien und schulfreie Tage der Volksschule der Stadt Zürich. "
        "Quelle: Open Data Zürich (Datensatz ssd_schulferien).",
    )
    cal.add(
        "x-wr-caldesc",
        "Ferien und schulfreie Tage der Volksschule der Stadt Zürich. "
        "Quelle: Open Data Zürich (Datensatz ssd_schulferien).",
    )
    cal.add("refresh-interval;value=duration", "PT24H")
    cal.add("x-published-ttl", "PT24H")
    cal.add("color", "blue")

    now_utc = datetime.now(timezone.utc)

    for rec in sorted(records, key=lambda r: (r["start_date"], r["summary"])):
        start = parse_date(rec["start_date"])
        end = parse_date(rec["end_date"])  # already exclusive in the source
        summary = rec["summary"].strip()

        if end < start:
            raise RuntimeError(
                f"Implausible record (end < start): {summary} {start} → {end}"
            )
        if end == start:
            # Source inconsistency: most records use an exclusive end date,
            # but some single-day entries ship end == start. Normalise to a
            # proper one-day all-day event.
            end = start + timedelta(days=1)

        event = Event()
        event.add("uid", vText(make_uid(summary, start, end)))
        event.add("summary", summary)
        event.add("dtstart", start)  # date value → VALUE=DATE (all-day)
        event.add("dtend", end)
        event.add("dtstamp", now_utc)
        event.add("transp", "TRANSPARENT")  # do not block free/busy time
        event.add("categories", ["Schulferien"])
        cal.add_component(event)

    return cal


def sanity_check(records: list[dict], ics_bytes: bytes) -> None:
    """Fail hard before deployment if the feed looks broken."""
    if len(records) < MIN_EXPECTED_EVENTS:
        raise RuntimeError(
            f"Only {len(records)} events fetched (expected >= {MIN_EXPECTED_EVENTS}); "
            "refusing to publish a possibly truncated feed."
        )

    latest_end = max(parse_date(r["end_date"]) for r in records)
    if latest_end < date.today():
        raise RuntimeError(
            f"Latest event ends {latest_end}, entirely in the past; "
            "source data looks stale or wrong."
        )

    # Round-trip: the generated bytes must parse back cleanly.
    reparsed = Calendar.from_ical(ics_bytes)
    n_events = sum(1 for c in reparsed.walk("VEVENT"))
    if n_events != len(records):
        raise RuntimeError(
            f"Round-trip mismatch: {n_events} events in ICS vs {len(records)} records."
        )


def main() -> int:
    records = fetch_all_records()
    cal = build_calendar(records)
    ics_bytes = cal.to_ical()
    sanity_check(records, ics_bytes)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_bytes(ics_bytes)

    latest = max(parse_date(r["end_date"]) for r in records)
    print(
        f"OK: {len(records)} events written to {OUTPUT_FILE} "
        f"({len(ics_bytes)} bytes, latest event ends {latest})."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
