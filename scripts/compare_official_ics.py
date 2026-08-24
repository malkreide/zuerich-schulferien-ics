#!/usr/bin/env python3
"""Cross-check the city's official .ics downloads against the CKAN dataset.

The City of Zurich publishes the same school holidays twice: as one static
``.ics`` per school year on the Schulferien page, and as the CKAN dataset
``ssd_schulferien`` that this repository's feed is built from. Nothing
guarantees the two stay in step — they are separate exports, and only CKAN
is under a documented update process.

This script downloads every ``.ics`` the page offers and compares it record
by record against the datastore. It exists for two jobs:

1. **Retiring the manual handover.** Whoever receives the ``.ics`` files by
   hand can point at a run of this script instead of trusting that the open
   dataset carries the same dates.
2. **Drift alarm.** Two independent exports of one source of truth are a
   cheap consistency check. A school record present in one and missing from
   the other means somebody's export is stale.

Two differences are *expected* and are classified rather than reported:

- **Truncated summer holidays.** The per-school-year files cut the summer
  holidays at the school-year boundary: the 2026/27 file carries
  ``2026-08-01 → 2026-08-15`` where CKAN holds the whole block
  ``2026-07-13 → 2026-08-15``. CKAN is the more complete of the two, so this
  is not drift. Only an ``.ics`` entry whose summary *and* exclusive end
  match a CKAN record that starts *earlier* is accepted as truncated — a
  rule that can hide a shortened event, never a missing one.
- **Same-span duplicates in CKAN.** The dataset carries both ``Pfingsten``
  and ``Pfingstsonntag`` for 2029-05-20, where the city file has only the
  first. A CKAN-only record is accepted as a duplicate when another record
  covering exactly the same span *is* in the city file.

Exit status is driven by school records only — those are what
``ferien.ics`` and ``nur-ferien.ics`` publish. Unexplained differences among
plain public holidays are printed as a warning: the city's own files
demonstrably omit some, so failing on them would cry wolf.

Usage::

    python scripts/compare_official_ics.py

Needs network access, so it is deliberately not part of the offline
``pytest`` suite. ``tests/test_compare_official_ics.py`` covers the parsing
and classification logic on fixtures.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urljoin

import requests
from icalendar import Calendar

# generate_ics.py sits at the repo root, so a bare `python scripts/…` run has
# only scripts/ on sys.path. Reusing its constants rather than copying them
# keeps one definition of the school-record prefix and the fetch.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from generate_ics import (  # noqa: E402
    REQUEST_TIMEOUT,
    SCHOOL_RECORD_RE,
    fetch_all_records,
    parse_date,
)

SCHULFERIEN_PAGE = (
    "https://www.stadt-zuerich.ch/de/bildung/volksschule/schulferien.html"
)
ICS_HREF_RE = re.compile(r'href="([^"]+\.ics)"', re.IGNORECASE)


@dataclass(frozen=True, order=True)
class Entry:
    """One dated record, normalised so the two exports can be compared."""

    start: date
    end: date  # exclusive, iCal convention — both sources use it
    summary: str

    @property
    def school(self) -> bool:
        return bool(SCHOOL_RECORD_RE.match(self.summary))

    def __str__(self) -> str:
        return f"{self.start} → {self.end}  {self.summary}"


@dataclass(frozen=True)
class Report:
    """The outcome of one comparison, split into explained and unexplained."""

    matched: set[Entry]
    truncated: set[Entry]  # in the .ics, shortened at the school-year boundary
    duplicated: set[Entry]  # in CKAN, a same-span twin of a record the city has
    only_ics: set[Entry]  # unexplained
    only_ckan: set[Entry]  # unexplained

    @property
    def drifted(self) -> set[Entry]:
        """Unexplained differences that would reach the published feed."""
        return {e for e in self.only_ics | self.only_ckan if e.school}


def discover_ics_urls(page_html: str, base_url: str = SCHULFERIEN_PAGE) -> list[str]:
    """Pull every ``.ics`` download off the Schulferien page, in page order.

    Scraped rather than hard-coded: the page gains a school year every year
    and drops the one that ended, and a hard-coded list would quietly compare
    fewer and fewer years while still reporting success.
    """
    seen: dict[str, None] = {}
    for href in ICS_HREF_RE.findall(page_html):
        seen.setdefault(urljoin(base_url, href), None)
    return list(seen)


def normalise(summary: str) -> str:
    """Collapse whitespace so a stray trailing blank is not read as drift.

    Two records in the city's files carry a trailing space that the CKAN
    export does not (2028 and 2030 Frühlingsferien). That is a formatting
    artefact of the export, not a different event.
    """
    return " ".join(summary.split())


def parse_ics(data: bytes) -> set[Entry]:
    """Read one published ``.ics`` into comparable entries.

    All-day events arrive as ``date``; a timed one would arrive as
    ``datetime`` and is reduced to its date, since CKAN stores dates only.
    """
    entries: set[Entry] = set()
    for event in Calendar.from_ical(data).walk("VEVENT"):
        start = event.decoded("DTSTART")
        end = event.decoded("DTEND")
        if isinstance(start, datetime):
            start = start.date()
        if isinstance(end, datetime):
            end = end.date()
        entries.add(Entry(start, end, normalise(str(event["SUMMARY"]))))
    return entries


def records_to_entries(records: list[dict]) -> set[Entry]:
    """Convert raw CKAN rows into the same shape as the ``.ics`` entries."""
    return {
        Entry(
            parse_date(rec["start_date"]),
            parse_date(rec["end_date"]),
            normalise(rec["summary"]),
        )
        for rec in records
    }


def classify(city: set[Entry], ckan: set[Entry]) -> Report:
    """Compare both exports over the span the city's files actually cover.

    CKAN reaches back to 2018 and the city only publishes upcoming school
    years, so the comparison is restricted to the window the ``.ics`` files
    span. Outside it, "missing" would only mean "not offered any more".
    """
    if not city:
        raise ValueError("No entries parsed from the city's .ics files.")

    lo = min(e.start for e in city)
    hi = max(e.start for e in city)
    ckan_window = {e for e in ckan if lo <= e.start <= hi}

    only_ics = city - ckan_window
    only_ckan = ckan_window - city

    # Accepted only when CKAN holds the *same* event over a longer span.
    truncated = {
        e
        for e in only_ics
        if any(
            c.summary == e.summary and c.end == e.end and c.start < e.start
            for c in ckan
        )
    }
    # Accepted only when the twin is genuinely present in the city's export.
    duplicated = {
        e
        for e in only_ckan
        if any(
            c != e and c.start == e.start and c.end == e.end and c in city for c in ckan
        )
    }

    return Report(
        matched=city & ckan_window,
        truncated=truncated,
        duplicated=duplicated,
        only_ics=only_ics - truncated,
        only_ckan=only_ckan - duplicated,
    )


def render(report: Report, sources: list[str]) -> str:
    """Format the comparison for a terminal or a CI log."""
    lines = [
        f"Verglichen: {len(sources)} .ics-Dateien der Stadt gegen den CKAN-Datensatz."
    ]
    for url in sources:
        lines.append(f"  - {url}")
    lines += [
        "",
        f"Identisch in beiden Quellen        : {len(report.matched)}",
        f"Nur .ics, an Schuljahresgrenze gek.: {len(report.truncated)} "
        f"(CKAN führt den Eintrag vollständig)",
        f"Nur CKAN, Dublette gleicher Daten  : {len(report.duplicated)}",
        f"Unerklärt nur in den .ics          : {len(report.only_ics)}",
        f"Unerklärt nur im CKAN-Datensatz    : {len(report.only_ckan)}",
    ]
    for label, entries in (
        ("An der Schuljahresgrenze gekürzt", report.truncated),
        ("Dubletten im CKAN-Datensatz", report.duplicated),
        ("UNERKLÄRT — nur in den .ics der Stadt", report.only_ics),
        ("UNERKLÄRT — nur im CKAN-Datensatz", report.only_ckan),
    ):
        if entries:
            lines += ["", f"--- {label} ---"]
            lines += [f"  {entry}" for entry in sorted(entries)]
    return "\n".join(lines)


def main() -> int:
    page = requests.get(SCHULFERIEN_PAGE, timeout=REQUEST_TIMEOUT)
    page.raise_for_status()
    urls = discover_ics_urls(page.text)
    if not urls:
        print(
            f"FEHLER: Auf {SCHULFERIEN_PAGE} wurde keine einzige .ics-Datei gefunden. "
            "Die Seite wurde vermutlich umgebaut — der Abgleich prüft sonst nichts.",
            file=sys.stderr,
        )
        return 2

    city: set[Entry] = set()
    for url in urls:
        resp = requests.get(url, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        city |= parse_ics(resp.content)

    report = classify(city, records_to_entries(fetch_all_records()))
    print(render(report, urls))

    if report.drifted:
        print(
            "\nFEHLER: Schul-Einträge weichen zwischen den beiden Exporten der Stadt ab. "
            "Einer von beiden ist veraltet — vor dem nächsten Release klären.",
            file=sys.stderr,
        )
        return 1

    holiday_noise = (report.only_ics | report.only_ckan) - report.drifted
    if holiday_noise:
        print(
            f"\nWarnung: {len(holiday_noise)} Feiertags-Einträge weichen ab. "
            "Sie erreichen nur alles.ics, nicht den Standard-Feed.",
        )
    print("\nOK: Kein unerklärter Unterschied bei den Schul-Einträgen.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
