#!/usr/bin/env python3
"""Generate a subscribable iCalendar feed for Zurich public school holidays.

Data source: Open Data Zurich (CKAN), dataset ``ssd_schulferien``
("Ferien und schulfreie Tage der Volksschule der Stadt Zürich").

Design decisions
----------------
- The CKAN ``end_date`` is already *exclusive* (iCal convention), verified
  against official holiday dates (e.g. Sportferien 2026: Feb 9-20 is stored
  as start 2026-02-09, end 2026-02-21). Therefore NO +1 day correction is
  applied. Do not "fix" this. ``tests/test_generate_ics.py`` guards it.
- The source mixes school entries (prefixed ``Schulen Stadt Zürich``) with
  plain public holidays (Neujahrstag, Ostersonntag, Nationalfeiertag, …).
  Only school entries are published: 94 of 97 holiday records in a typical
  window fall *inside* a school-free block anyway, and 22 land on weekends,
  so publishing them buries the school dates the feed exists for. Subscribers
  who want public holidays already have a calendar for them.
- Titles are display strings, not database strings. The redundant
  ``Schulen Stadt Zürich schulfrei:`` prefix is dropped (the calendar is
  already named) and a trailing parenthetical is moved into DESCRIPTION, so
  a 110-character record renders as "Frühlingsferien" in a month view
  without losing a word.
- ``Schulschluss 12 Uhr`` is emitted as a *timed* event at 12:00
  Europe/Zurich, not as an all-day event. It is the one entry where the day
  is not free: rendering it like a holiday is what a parent misreads.
- UIDs are deterministic SHA-256 hashes over the *raw* source summary plus
  the source dates. Hashing the raw rather than the cleaned title keeps UIDs
  stable across title changes, so existing subscriptions update in place
  instead of resyncing. A changed *date* still appears as "old event
  removed, new event added", which is acceptable for an informational feed
  and avoids state management.
- The script fails hard (non-zero exit) on implausible data so that a broken
  CKAN response never overwrites the last known-good feed on GitHub Pages.
- Only events reaching into the current or the two preceding calendar years
  are published (see ``CUTOFF_YEARS_BACK``). The source goes back to 2018, which
  buries subscribers under years of irrelevant past entries. An event that
  straddles the cutoff (e.g. Weihnachtsferien 2024/25) is kept in full.
- The landing page (``web/index.html``) is rendered into ``public/`` by the same
  run that writes the feed. Both artifacts therefore pass the same sanity gate:
  a broken CKAN response leaves the last known-good page *and* feed in place,
  and the page can never advertise numbers the feed does not contain.
"""

from __future__ import annotations

import hashlib
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from icalendar import Calendar, Event, Timezone, vText

CKAN_BASE = "https://data.stadt-zuerich.ch/api/3/action/datastore_search"
RESOURCE_ID = "aad477f6-db39-4d1b-92d8-0885f2d363d1"
PAGE_SIZE = 1000
OUTPUT_DIR = Path("public")
OUTPUT_FILE = OUTPUT_DIR / "ferien.ics"
PAGE_TEMPLATE = Path("web/index.html")
PAGE_FILE = OUTPUT_DIR / "index.html"
UID_DOMAIN = "zuerich-schulferien-ics.malkreide.github.io"

# Publish events from the start of this many calendar years ago. 2 => on any
# day in 2026 the feed starts at 2024-01-01.
CUTOFF_YEARS_BACK = 2

# Every school record in the source carries this prefix; plain public holidays
# do not. This is the only marker the dataset offers to tell them apart.
SCHOOL_RECORD_RE = re.compile(r"^Schulen Stadt Zürich\b")
# ... in two spellings: "Schulen Stadt Zürich: X" and "… schulfrei: X".
TITLE_PREFIX_RE = re.compile(r"^Schulen Stadt Zürich(?:\s+schulfrei)?:\s*")
# A trailing parenthetical, optionally preceded by the source's footnote
# asterisk: "Frühlingsferien* (ausnahmsweise KW 16 & 17, …)".
TRAILING_NOTE_RE = re.compile(r"\s*\*?\s*\(([^()]*)\)\s*$")
# The source spells this both with and without "um".
HALF_DAY_RE = re.compile(r"^Schulschluss\s+(?:um\s+)?12\s+Uhr$", re.IGNORECASE)

HALF_DAY_TITLE = "Schulschluss 12 Uhr"
HALF_DAY_NOTE = "Der Unterricht endet an diesem Tag um 12 Uhr."
HALF_DAY_START = time(12, 0)
# A point in time cannot be rendered by most clients, so the event gets a
# short visible block at noon rather than a zero-length duration.
HALF_DAY_DURATION = timedelta(minutes=30)
LOCAL_TZ = ZoneInfo("Europe/Zurich")

# Sanity gate thresholds
MIN_EXPECTED_EVENTS = 30
MIN_EXPECTED_PUBLISHED = 20
# Share of fetched records that must look like school records. Guards against
# the city renaming the prefix, which would silently empty the feed.
MIN_SCHOOL_SHARE = 0.3
REQUEST_TIMEOUT = 30


@dataclass(frozen=True)
class SchoolEvent:
    """One publishable entry, already cleaned for display."""

    summary: str
    start: date
    end: date  # exclusive, iCal convention
    uid: str
    note: str | None = None
    half_day: bool = False

    @property
    def description(self) -> str | None:
        parts = [p for p in (HALF_DAY_NOTE if self.half_day else None, self.note) if p]
        return " ".join(parts) or None


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


def make_uid(raw_summary: str, start: date, end: date) -> str:
    """Derive a stable UID from the *source* record, not the display title.

    Cleaning the title must not resync every subscriber, so the hash input is
    deliberately the untouched CKAN summary.
    """
    raw = f"volksschule-zuerich-{raw_summary}-{start.isoformat()}-{end.isoformat()}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"{digest}@{UID_DOMAIN}"


def is_school_record(summary: str) -> bool:
    """True for school entries, False for the plain public holidays alongside."""
    return bool(SCHOOL_RECORD_RE.match(summary.strip()))


def clean_title(raw: str) -> tuple[str, str | None]:
    """Strip the boilerplate prefix and lift a trailing parenthetical out.

    Returns ``(display_title, note)``. The note keeps the source wording
    verbatim so shortening the title loses no information.
    """
    title = TITLE_PREFIX_RE.sub("", raw.strip()).strip()

    note: str | None = None
    match = TRAILING_NOTE_RE.search(title)
    if match:
        note = match.group(1).strip() or None
        title = title[: match.start()]
    title = title.strip().rstrip("*").strip()

    if note:
        # Source inconsistency: "(KW29-33)" alongside "(KW 29-33)".
        note = re.sub(r"\bKW(\d)", r"KW \1", note)

    # A record consisting of nothing but the prefix would otherwise vanish.
    return title or raw.strip(), note


def select_events(records: list[dict], cutoff: date) -> list[SchoolEvent]:
    """Parse, filter and normalise records into sorted ``SchoolEvent``s.

    Public holidays are dropped (see module docstring). ``end`` is the
    exclusive iCal end date. A record is dropped only when it has *finished*
    before ``cutoff``; one straddling the cutoff (e.g. Weihnachtsferien
    2024/25) is kept in full so the holiday is not truncated.
    """
    events: list[SchoolEvent] = []

    for rec in records:
        raw_summary = rec["summary"].strip()
        if not is_school_record(raw_summary):
            continue

        start = parse_date(rec["start_date"])
        end = parse_date(rec["end_date"])  # already exclusive in the source

        if end < start:
            raise RuntimeError(
                f"Implausible record (end < start): {raw_summary} {start} → {end}"
            )

        # UID is bound to the record as fetched, before normalisation, so a
        # source-side one-day quirk does not shift existing subscriptions.
        uid = make_uid(raw_summary, start, end)

        if end == start:
            # Source inconsistency: most records use an exclusive end date,
            # but some single-day entries ship end == start. Normalise to a
            # proper one-day all-day event.
            end = start + timedelta(days=1)

        if end <= cutoff:
            continue

        summary, note = clean_title(raw_summary)

        # Only a genuine single-day record can become a timed noon event;
        # anything longer would silently lose its remaining days.
        half_day = bool(HALF_DAY_RE.match(summary)) and (end - start).days == 1
        if half_day:
            summary = HALF_DAY_TITLE

        events.append(
            SchoolEvent(
                summary=summary,
                start=start,
                end=end,
                uid=uid,
                note=note,
                half_day=half_day,
            )
        )

    return sorted(events, key=lambda e: (e.start, e.summary))


def build_calendar(events: list[SchoolEvent]) -> Calendar:
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

    # A TZID reference must resolve inside the same calendar (RFC 5545 §3.2.19),
    # so the VTIMEZONE ships only when a timed event actually needs it.
    if any(e.half_day for e in events):
        cal.add_component(
            Timezone.from_tzid(
                "Europe/Zurich",
                first_date=datetime(min(e.start for e in events).year, 1, 1),
                last_date=datetime(max(e.end for e in events).year + 1, 1, 1),
            )
        )

    now_utc = datetime.now(timezone.utc)

    for ev in events:
        event = Event()
        event.add("uid", vText(ev.uid))
        event.add("summary", ev.summary)

        if ev.half_day:
            begins = datetime.combine(ev.start, HALF_DAY_START, tzinfo=LOCAL_TZ)
            event.add("dtstart", begins)
            event.add("dtend", begins + HALF_DAY_DURATION)
        else:
            event.add("dtstart", ev.start)  # date value → VALUE=DATE (all-day)
            event.add("dtend", ev.end)

        if ev.description:
            event.add("description", ev.description)

        event.add("dtstamp", now_utc)
        event.add("transp", "TRANSPARENT")  # do not block free/busy time
        event.add("categories", ["Schulferien"])
        cal.add_component(event)

    return cal


def sanity_check(
    records: list[dict],
    events: list[SchoolEvent],
    ics_bytes: bytes,
) -> None:
    """Fail hard before deployment if the feed looks broken."""
    if len(records) < MIN_EXPECTED_EVENTS:
        raise RuntimeError(
            f"Only {len(records)} events fetched (expected >= {MIN_EXPECTED_EVENTS}); "
            "refusing to publish a possibly truncated feed."
        )

    # The school filter keys off a prefix the city controls. If that prefix
    # ever changes, fail loudly here rather than ship an empty calendar.
    school_records = sum(1 for r in records if is_school_record(r["summary"]))
    share = school_records / len(records)
    if share < MIN_SCHOOL_SHARE:
        raise RuntimeError(
            f"Only {school_records} of {len(records)} records match "
            f"{SCHOOL_RECORD_RE.pattern!r} ({share:.0%} < {MIN_SCHOOL_SHARE:.0%}); "
            "the source may have renamed the school prefix."
        )

    latest_end = max(parse_date(r["end_date"]) for r in records)
    if latest_end < date.today():
        raise RuntimeError(
            f"Latest event ends {latest_end}, entirely in the past; "
            "source data looks stale or wrong."
        )

    # The cutoff must never swallow the whole feed — that would mean the
    # source stopped publishing current school years.
    if len(events) < MIN_EXPECTED_PUBLISHED:
        raise RuntimeError(
            f"Only {len(events)} events survive the cutoff (expected >= "
            f"{MIN_EXPECTED_PUBLISHED}); refusing to publish a near-empty feed."
        )

    # Round-trip: the generated bytes must parse back cleanly.
    reparsed = Calendar.from_ical(ics_bytes)
    n_events = sum(1 for c in reparsed.walk("VEVENT"))
    if n_events != len(events):
        raise RuntimeError(
            f"Round-trip mismatch: {n_events} events in ICS vs {len(events)} selected."
        )


def cutoff_date(today: date) -> date:
    """First day that still gets published: 1 Jan, CUTOFF_YEARS_BACK years back."""
    return date(today.year - CUTOFF_YEARS_BACK, 1, 1)


def render_page(events: list[SchoolEvent], built: date, template: Path) -> str:
    """Fill the landing page template with what this run actually produced.

    The page states an event count and a coverage end date. Those must come
    from the generated feed rather than being hand-maintained in the HTML,
    otherwise the page starts lying the moment the data shifts. An unresolved
    or unknown placeholder is a hard error: a page rendering a literal
    ``{{EVENT_COUNT}}`` to subscribers is worse than a failed build.
    """
    # ``events`` holds exclusive iCal end dates; the last day a subscriber
    # actually sees is the day before.
    last_day = max(e.end for e in events) - timedelta(days=1)

    values = {
        "EVENT_COUNT": str(len(events)),
        "RANGE_END": last_day.strftime("%d.%m.%Y"),
        "UPDATED": built.strftime("%d.%m.%Y"),
    }

    html = template.read_text(encoding="utf-8")
    for key, value in values.items():
        html = html.replace("{{" + key + "}}", value)

    leftover = re.findall(r"\{\{[A-Z_]+\}\}", html)
    if leftover:
        raise RuntimeError(
            f"Unresolved placeholders in {template}: {sorted(set(leftover))}"
        )
    return html


def main() -> int:
    records = fetch_all_records()
    today = date.today()
    cutoff = cutoff_date(today)
    events = select_events(records, cutoff)
    cal = build_calendar(events)
    ics_bytes = cal.to_ical()
    sanity_check(records, events, ics_bytes)

    # Rendered before the first write so a template error aborts the run while
    # the previously deployed feed is still the last thing on Pages.
    page_html = render_page(events, today, PAGE_TEMPLATE)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_bytes(ics_bytes)
    PAGE_FILE.write_text(page_html, encoding="utf-8")

    latest = max(parse_date(r["end_date"]) for r in records)
    print(
        f"OK: {len(events)} of {len(records)} records written to {OUTPUT_FILE} "
        f"({len(ics_bytes)} bytes; cutoff {cutoff}, "
        f"{sum(1 for e in events if e.half_day)} half-day events, "
        f"latest source event ends {latest})."
    )
    print(f"OK: landing page written to {PAGE_FILE} ({len(page_html)} chars).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
