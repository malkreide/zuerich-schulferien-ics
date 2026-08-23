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
  94 of 97 holiday records in a typical window fall *inside* a school-free
  block anyway, and 22 land on weekends, so the default feed leaves them out.
- Three feeds are published from one fetch (see ``FEED_VARIANTS``).
  ``ferien.ics`` is the advertised URL and its contents are *frozen*: people
  are already subscribed to it, so narrowing it would silently strip dates
  from their calendars. The narrower and wider cuts get their own filenames.
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
- DTSTAMP comes from the source record's ``created_date``, never from the wall
  clock. A wall-clock stamp made every nightly run emit a byte-different file
  even when nothing had changed, so the ETag rotated and every subscriber
  re-downloaded the whole feed. Identical input now produces identical bytes.
  Comparing against the previously deployed file is not an option: CI checks
  out a fresh tree and ``public/`` is generated, so there is nothing to compare.
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
import html
import re
import sys
from collections.abc import Callable
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
FEED_CAPTION = (
    "Ferien und schulfreie Tage der Volksschule der Stadt Zürich. "
    "Quelle: Open Data Zürich (Datensatz ssd_schulferien)."
)
PAGE_TEMPLATE = Path("web/index.html")
PAGE_FILE = OUTPUT_DIR / "index.html"
UID_DOMAIN = "zuerich-schulferien-ics.malkreide.github.io"
FEED_BASE_URL = "https://malkreide.github.io/zuerich-schulferien-ics"

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
# The source already spells this both with and without "um". Anchoring the
# whole string would let a rewording ("um 12.00 Uhr", "… für alle Stufen")
# silently fall back to an all-day event — a school day rendered as a day off,
# which is exactly what this branch exists to prevent. So: match the opening
# word plus a noon time, and keep any extra wording in the description.
HALF_DAY_RE = re.compile(r"^Schulschluss\b.*\b12(?:[.:]00)?\s*Uhr\b", re.IGNORECASE)

HALF_DAY_TITLE = "Schulschluss 12 Uhr"
HALF_DAY_NOTE = "Der Unterricht endet an diesem Tag um 12 Uhr."
HALF_DAY_START = time(12, 0)
# A point in time cannot be rendered by most clients, so the event gets a
# short visible block at noon rather than a zero-length duration.
HALF_DAY_DURATION = timedelta(minutes=30)
LOCAL_TZ = ZoneInfo("Europe/Zurich")

# German weekday abbreviations for the landing page's year overview.
WEEKDAYS = ("Mo", "Di", "Mi", "Do", "Fr", "Sa", "So")
# A Zurich school year runs from August to July: the summer holidays starting
# in July belong to the year that is ending, which is how parents read them.
SCHOOL_YEAR_START_MONTH = 8

# Sanity gate thresholds
MIN_EXPECTED_EVENTS = 30
# Share of fetched records that must look like school records. Guards against
# the city renaming the prefix, which would silently empty the feed.
MIN_SCHOOL_SHARE = 0.3
# The source must reach this far ahead. `latest_end < today` alone only fires
# once the data is *entirely* historic, by which point parents have been
# planning against a feed that quietly ran out. Half a year gives the
# maintainer time to notice the city has not published the next school year.
MIN_FORWARD_COVERAGE_DAYS = 180
# The school year containing today must carry at least this many events, so a
# source that keeps far-future entries but drops the current year is caught.
MIN_EVENTS_CURRENT_YEAR = 5
REQUEST_TIMEOUT = 30


@dataclass(frozen=True)
class SchoolEvent:
    """One publishable entry, already cleaned for display."""

    summary: str
    start: date
    end: date  # exclusive, iCal convention
    uid: str
    stamp: datetime  # DTSTAMP, from the source record — never the wall clock
    note: str | None = None
    half_day: bool = False
    school: bool = True  # False for a plain public holiday from the same source

    @property
    def last_day(self) -> date:
        """The last day a subscriber actually sees (``end`` is exclusive)."""
        return self.end - timedelta(days=1)

    @property
    def days(self) -> int:
        return (self.end - self.start).days

    @property
    def closure(self) -> bool:
        """A multi-day school closure — the kind that needs childcare arranged.

        ``days >= 2`` already excludes a half day: ``half_day`` is only set for
        a record spanning exactly one day, so no extra guard is needed here.
        """
        return self.school and self.days >= 2

    @property
    def description(self) -> str | None:
        parts = [p for p in (HALF_DAY_NOTE if self.half_day else None, self.note) if p]
        return " ".join(parts) or None


@dataclass(frozen=True)
class FeedVariant:
    """One published .ics file: which events go in, and how it introduces itself."""

    filename: str
    calname: str
    caption: str
    include: Callable[[SchoolEvent], bool]
    min_events: int
    blurb: str  # one line for the landing page


FEED_VARIANTS = (
    FeedVariant(
        # Frozen: this URL is already subscribed to. Narrowing it would strip
        # dates from calendars without anyone asking.
        filename="ferien.ics",
        calname="Schulferien Stadt Zürich",
        caption=FEED_CAPTION,
        include=lambda e: e.school,
        min_events=20,
        blurb="Ferien und einzelne schulfreie Tage. Die Standardauswahl.",
    ),
    FeedVariant(
        filename="nur-ferien.ics",
        calname="Schulferien Stadt Zürich (nur Ferien)",
        caption=(
            "Nur die mehrtägigen Schulschliessungen der Volksschule der Stadt "
            "Zürich. Quelle: Open Data Zürich (Datensatz ssd_schulferien)."
        ),
        include=lambda e: e.closure,
        min_events=8,
        blurb=(
            "Nur die mehrtägigen Schliessungen — ohne einzelne Tage wie "
            "Knabenschiessen oder den 1. Schultag."
        ),
    ),
    FeedVariant(
        filename="alles.ics",
        calname="Schulferien Stadt Zürich (mit Feiertagen)",
        caption=(
            "Ferien und schulfreie Tage der Volksschule der Stadt Zürich, "
            "zusätzlich die allgemeinen Feiertage aus demselben Datensatz. "
            "Quelle: Open Data Zürich (Datensatz ssd_schulferien)."
        ),
        include=lambda e: True,
        min_events=25,
        blurb=(
            "Zusätzlich die allgemeinen Feiertage. Nur sinnvoll, wenn im "
            "Kalender noch kein Feiertagsabo liegt."
        ),
    ),
)


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


def parse_stamp(rec: dict, start: date) -> datetime:
    """DTSTAMP for a record: when the source authored it, in UTC.

    Deliberately not ``datetime.now()``. Every record in the dataset carries
    ``created_date``; the fallback for one that does not is still derived from
    the record itself, so the output stays a pure function of the input.
    """
    raw = rec.get("created_date")
    if raw:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return parsed.astimezone(timezone.utc)
    return datetime.combine(start, time(0, 0), tzinfo=timezone.utc)


def make_uid(raw_summary: str, start: date, end: date) -> str:
    """Derive a stable UID from the *source* record, not the display title.

    Cleaning the title must not resync every subscriber, so the hash input is
    deliberately the untouched CKAN summary.
    """
    raw = f"volksschule-zuerich-{raw_summary}-{start.isoformat()}-{end.isoformat()}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"{digest}@{UID_DOMAIN}"


def half_day_key(text: str) -> str:
    """Fold the source's half-day spelling variants onto one comparable form.

    ``Schulschluss um 12.00 Uhr`` and ``Schulschluss 12 Uhr`` say the same
    thing, so canonicalising the first must not append the second as a note.
    Wording that survives this folding is genuine extra information and is kept.
    """
    text = re.sub(r"\b12[.:]00\b", "12", text.lower())
    return " ".join(re.sub(r"\bum\b", " ", text).split())


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
    """Parse and normalise every record into sorted ``SchoolEvent``s.

    Public holidays are kept here and marked ``school=False``; which feed they
    reach is a per-variant decision (see ``FEED_VARIANTS``). ``end`` is the
    exclusive iCal end date. A record is dropped only when it has *finished*
    before ``cutoff``; one straddling the cutoff (e.g. Weihnachtsferien
    2024/25) is kept in full so the holiday is not truncated.
    """
    events: list[SchoolEvent] = []

    for rec in records:
        raw_summary = rec["summary"].strip()
        start = parse_date(rec["start_date"])
        end = parse_date(rec["end_date"])  # already exclusive in the source

        if end < start:
            raise RuntimeError(
                f"Implausible record (end < start): {raw_summary} {start} → {end}"
            )

        if end == start:
            # Source inconsistency: most records use an exclusive end date,
            # but some single-day entries ship end == start. Normalise to a
            # proper one-day all-day event.
            end = start + timedelta(days=1)

        # Hashed *after* the normalisation above, matching what the feed has
        # always published for these records. Hashing the raw end instead would
        # hand every end == start record a new UID and resync it for existing
        # subscribers — the one thing the UID design exists to prevent.
        uid = make_uid(raw_summary, start, end)

        if end <= cutoff:
            continue

        summary, note = clean_title(raw_summary)

        # Only a genuine single-day record can become a timed noon event;
        # anything longer would silently lose its remaining days.
        half_day = bool(HALF_DAY_RE.match(summary)) and (end - start).days == 1
        if half_day:
            if half_day_key(summary) != half_day_key(HALF_DAY_TITLE):
                # Canonicalise the title but never drop wording that adds
                # something — a mere spelling variant adds nothing.
                note = " · ".join(p for p in (summary, note) if p)
            summary = HALF_DAY_TITLE

        events.append(
            SchoolEvent(
                summary=summary,
                start=start,
                end=end,
                uid=uid,
                stamp=parse_stamp(rec, start),
                note=note,
                half_day=half_day,
                school=is_school_record(raw_summary),
            )
        )

    return sorted(events, key=lambda e: (e.start, e.summary))


def variant_events(
    events: list[SchoolEvent], variant: FeedVariant
) -> list[SchoolEvent]:
    """The subset of ``events`` that this feed publishes."""
    return [e for e in events if variant.include(e)]


def build_calendar(events: list[SchoolEvent], variant: FeedVariant) -> Calendar:
    cal = Calendar()
    cal.add("prodid", "-//zuerich-schulferien-ics//Schulferien Generator//DE")
    cal.add("version", "2.0")
    cal.add("calscale", "GREGORIAN")
    cal.add("method", "PUBLISH")
    # RFC 7986 + de-facto extensions for client display and refresh behaviour
    cal.add("name", variant.calname)
    cal.add("x-wr-calname", variant.calname)
    cal.add("description", variant.caption)
    cal.add("x-wr-caldesc", variant.caption)
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

        event.add("dtstamp", ev.stamp)
        event.add("transp", "TRANSPARENT")  # do not block free/busy time
        event.add("categories", ["Schulferien"])
        cal.add_component(event)

    return cal


def check_source(records: list[dict], events: list[SchoolEvent], today: date) -> None:
    """Gate the fetched data before any file is written.

    Everything here fails the whole run: if the source is wrong, publishing a
    partly-wrong feed is worse than leaving the last known-good one in place.
    """
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
    if latest_end < today:
        raise RuntimeError(
            f"Latest event ends {latest_end}, entirely in the past; "
            "source data looks stale or wrong."
        )

    # Forward coverage: a feed that has quietly run out is useless to someone
    # planning next term, and nothing else here would notice.
    horizon = (latest_end - today).days
    if horizon < MIN_FORWARD_COVERAGE_DAYS:
        raise RuntimeError(
            f"Source covers only {horizon} more days (until {latest_end}, "
            f"minimum {MIN_FORWARD_COVERAGE_DAYS}); the city has probably not "
            "published the next school year yet."
        )

    # A source that keeps far-future entries but drops the running school year
    # would sail past the horizon check above.
    current = school_year(today)
    in_current = sum(1 for e in events if e.school and school_year(e.start) == current)
    if in_current < MIN_EVENTS_CURRENT_YEAR:
        raise RuntimeError(
            f"School year {current}/{current + 1} has only {in_current} events "
            f"(expected >= {MIN_EVENTS_CURRENT_YEAR}); the running year looks "
            "incomplete."
        )


def check_feed(
    variant: FeedVariant, events: list[SchoolEvent], ics_bytes: bytes
) -> None:
    """Gate one generated feed before it is written."""
    if len(events) < variant.min_events:
        raise RuntimeError(
            f"{variant.filename}: only {len(events)} events survive the filter "
            f"(expected >= {variant.min_events}); refusing to publish a "
            "near-empty feed."
        )

    # Round-trip: the generated bytes must parse back cleanly.
    reparsed = Calendar.from_ical(ics_bytes)
    n_events = sum(1 for c in reparsed.walk("VEVENT"))
    if n_events != len(events):
        raise RuntimeError(
            f"{variant.filename}: round-trip mismatch, {n_events} events in ICS "
            f"vs {len(events)} selected."
        )

    uids = [str(c["UID"]) for c in reparsed.walk("VEVENT")]
    if len(set(uids)) != len(uids):
        raise RuntimeError(f"{variant.filename}: duplicate UIDs in the generated feed.")


def cutoff_date(today: date) -> date:
    """First day that still gets published: 1 Jan, CUTOFF_YEARS_BACK years back."""
    return date(today.year - CUTOFF_YEARS_BACK, 1, 1)


def school_year(day: date) -> int:
    """Starting year of the school year `day` falls into. Aug 2026 → 2026."""
    return day.year if day.month >= SCHOOL_YEAR_START_MONTH else day.year - 1


def format_day(day: date, with_year: bool = True) -> str:
    """`Sa 3.10.2026` — weekday included because parents plan around it."""
    text = f"{WEEKDAYS[day.weekday()]} {day.day}.{day.month}."
    return f"{text}{day.year}" if with_year else text


def format_period(event: SchoolEvent) -> tuple[str, str]:
    """Human-readable (period, duration) for one event."""
    if event.half_day:
        return format_day(event.start), "halber Tag"

    days = (event.end - event.start).days
    if days == 1:
        return format_day(event.start), "1 Tag"

    last = event.last_day
    # The year is stated once unless the holiday crosses New Year.
    start_text = format_day(event.start, with_year=event.start.year != last.year)
    return f"{start_text} – {format_day(last)}", f"{days} Tage"


def keep_dates_together(text: str) -> str:
    """Bind ``Mo 5.10.`` with a non-breaking space.

    On a phone the cell has to wrap somewhere. Left alone it breaks at every
    space and a range becomes four lines; bound this way it breaks only at the
    dash between the two dates.
    """
    return re.sub(r"\b(" + "|".join(WEEKDAYS) + r") ", "\\1\u00a0", text)


def render_year_tables(events: list[SchoolEvent], today: date) -> str:
    """Render the current and next school year as HTML tables.

    Most visitors want to look a date up, not subscribe to anything. Building
    the table from the same events as the feed keeps the page from ever showing
    a date the feed does not contain.
    """
    current = school_year(today)
    blocks: list[str] = []

    for year in (current, current + 1):
        rows = [e for e in events if school_year(e.start) == year]
        if not rows:
            continue

        cells = []
        for event in sorted(rows, key=lambda e: e.start):
            period, duration = format_period(event)
            title = html.escape(event.summary)
            if event.note:
                title += f' <span class="hint">{html.escape(event.note)}</span>'
            cells.append(
                f"        <tr><td>{title}</td>"
                f"<td>{keep_dates_together(html.escape(period))}</td>"
                f"<td>{html.escape(duration)}</td></tr>"
            )

        blocks.append(
            f"  <h3>Schuljahr {year}/{str(year + 1)[-2:]}</h3>\n"
            '  <div class="table-wrap">\n'
            '    <table class="year">\n'
            "      <thead><tr><th>Termin</th><th>Zeitraum</th><th>Dauer</th></tr></thead>\n"
            "      <tbody>\n" + "\n".join(cells) + "\n      </tbody>\n"
            "    </table>\n"
            "  </div>"
        )

    if not blocks:
        # Unreachable while the staleness gate passes, but a page that silently
        # renders nothing here would be worse than one that says so.
        return "  <p>Für das laufende Schuljahr liegen derzeit keine Termine vor.</p>"
    return "\n".join(blocks)


def render_variant_rows(counts: dict[str, int]) -> str:
    """The feed picker on the landing page, one row per variant."""
    rows = []
    for variant in FEED_VARIANTS:
        url = f"{FEED_BASE_URL}/{variant.filename}"
        rows.append(
            '  <div class="variant">\n'
            f"    <h3>{html.escape(variant.calname)}</h3>\n"
            f"    <p>{html.escape(variant.blurb)} "
            f'<span class="count">{counts[variant.filename]} Termine</span></p>\n'
            '    <div class="feed-row">\n'
            f'      <div class="feed-url">{html.escape(url)}</div>\n'
            f'      <button class="copy" type="button" data-url="{html.escape(url)}">'
            "Kopieren</button>\n"
            "    </div>\n"
            "  </div>"
        )
    return "\n".join(rows)


def render_page(
    events: list[SchoolEvent],
    counts: dict[str, int],
    built: date,
    template: Path,
) -> str:
    """Fill the landing page template with what this run actually produced.

    The page states an event count and a coverage end date. Those must come
    from the generated feed rather than being hand-maintained in the HTML,
    otherwise the page starts lying the moment the data shifts. An unresolved
    or unknown placeholder is a hard error: a page rendering a literal
    ``{{EVENT_COUNT}}`` to subscribers is worse than a failed build.
    """
    values = {
        "EVENT_COUNT": str(len(events)),
        "RANGE_END": max(e.last_day for e in events).strftime("%d.%m.%Y"),
        "UPDATED": built.strftime("%d.%m.%Y"),
        "YEAR_TABLES": render_year_tables(events, built),
        "VARIANT_ROWS": render_variant_rows(counts),
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
    check_source(records, events, today)

    # Everything is generated and gated before the first write, so a failure
    # anywhere leaves the previously deployed feeds untouched on Pages.
    generated: dict[str, bytes] = {}
    counts: dict[str, int] = {}
    for variant in FEED_VARIANTS:
        selected = variant_events(events, variant)
        ics_bytes = build_calendar(selected, variant).to_ical()
        check_feed(variant, selected, ics_bytes)
        generated[variant.filename] = ics_bytes
        counts[variant.filename] = len(selected)

    primary = variant_events(events, FEED_VARIANTS[0])
    page_html = render_page(primary, counts, today, PAGE_TEMPLATE)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for filename, ics_bytes in generated.items():
        (OUTPUT_DIR / filename).write_bytes(ics_bytes)
    PAGE_FILE.write_text(page_html, encoding="utf-8")

    latest = max(parse_date(r["end_date"]) for r in records)
    summary = ", ".join(f"{name} {counts[name]}" for name in generated)
    print(
        f"OK: {len(records)} records → {summary} "
        f"(cutoff {cutoff}, latest source event ends {latest}, "
        f"{(latest - today).days} days of coverage ahead)."
    )
    print(f"OK: landing page written to {PAGE_FILE} ({len(page_html)} chars).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
