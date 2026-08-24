# Zürich Schulferien ICS Feed

![Version](https://img.shields.io/badge/version-2.0.0-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Python](https://img.shields.io/badge/python-3.10+-blue)

> Abonnierbarer iCal-Feed für die Schulferien der Volksschule der Stadt Zürich, generiert aus Open Data Zürich (CKAN)

🇬🇧 [English Version](README.md)

> **Hinweis:** Dies ist ein unabhängiges Open-Source-Projekt und kein
> offizieller Dienst der Stadt Zürich. Datenquelle:
> [Open Data Zürich](https://data.stadt-zuerich.ch/dataset/ssd_schulferien)
> (Datensatz `ssd_schulferien`).

## Übersicht

Die Stadt Zürich publiziert die Schulferien als statische ICS-Dateien pro
Schuljahr, die Nutzerinnen und Nutzer jedes Jahr neu herunterladen und
importieren müssen. Dieses Projekt macht aus den zugrunde liegenden offenen
Daten einen **dauerhaft abonnierbaren** iCalendar-Feed unter einer stabilen
URL: Kalender-Apps fragen ihn automatisch ab, und Änderungen an Ferienterminen
erreichen alle Abonnentinnen und Abonnenten ohne manuelles Zutun.

Ein GitHub-Actions-Workflow ruft den CKAN-Datastore nächtlich ab, generiert
eine RFC-5545-konforme `.ics`-Datei und publiziert sie auf GitHub Pages.

## Abonnieren

Eine Landing-Page mit Schritt-für-Schritt-Anleitung liegt unter
[malkreide.github.io/zuerich-schulferien-ics](https://malkreide.github.io/zuerich-schulferien-ics/)
— nicht-technische Nutzerinnen und Nutzer besser dorthin schicken als in dieses README.

Stabile Feed-URL:

```
https://malkreide.github.io/zuerich-schulferien-ics/ferien.ics
```

Es gibt denselben Datenbestand in drei Zuschnitten — einer genügt:

| Feed | Inhalt |
|---|---|
| `ferien.ics` | Ferien und einzelne schulfreie Tage. **Die Standardauswahl.** |
| `nur-ferien.ics` | Nur die mehrtägigen Schliessungen, ohne einzelne Tage |
| `alles.ics` | Zusätzlich die allgemeinen Feiertage |

`ferien.ics` bleibt bewusst unverändert: Unter dieser Adresse laufen bereits
Abos, und sie nachträglich zu verengen würde Termine aus fremden Kalendern
entfernen, ohne dass jemand gefragt wurde.

| Plattform | Abo-Weg |
|---|---|
| Apple Kalender (iOS/macOS) | `webcal://malkreide.github.io/zuerich-schulferien-ics/ferien.ics` öffnen |
| Google Kalender / Android | `https://calendar.google.com/calendar/r?cid=https://malkreide.github.io/zuerich-schulferien-ics/ferien.ics` öffnen und bestätigen |
| Andere Clients (Nextcloud, Thunderbird, …) | Roh-URL als Kalenderabonnement eintragen |

**Android:** Den HTTPS-Link nicht einfach im Browser antippen — das lädt eine
einmalige statische Kopie herunter, die sich nie aktualisiert. Stattdessen den
Google-Kalender-Link oben verwenden.

## Feed prüfen

Der Feed ist UTF-8 (ohne BOM, CRLF-Zeilenenden). GitHub Pages liefert ihn als
`Content-Type: text/calendar` **ohne** `charset`-Parameter aus — Header lassen
sich dort nicht konfigurieren. Manche Clients raten dann falsch und stellen
Umlaute als Mojibake dar (`ZÃ¼rich` statt `Zürich`). Das betrifft nur die
Anzeige beim Abrufen, nicht die Datei.

Bekannter Fall: **Windows PowerShell 5.1** dekodiert eine Antwort ohne
`charset` als ISO-8859-1. Zum Prüfen deshalb die Kodierung explizit setzen:

```powershell
# Windows PowerShell 5.1 — erzwingt UTF-8
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$r = [Net.WebClient]::new()
$r.Encoding = [Text.Encoding]::UTF8
$r.DownloadString("https://malkreide.github.io/zuerich-schulferien-ics/ferien.ics") -split "`r`n" | Select-Object -First 20
```

PowerShell 7+ (`pwsh`) verwendet standardmässig UTF-8, dort genügt
`Invoke-WebRequest`. Ebenso `curl`:

```bash
curl -s https://malkreide.github.io/zuerich-schulferien-ics/ferien.ics | head -20
```

Kalender-Clients (Apple Kalender, Google Kalender, Thunderbird, Nextcloud)
behandeln iCalendar gemäss RFC 5545 grundsätzlich als UTF-8 und sind von
diesem Verhalten nicht betroffen.

## Funktionen

- Nächtliche automatische Aktualisierung aus der Single Source of Truth (CKAN-Datastore)
- **Jahresübersicht** auf der Landing-Page — laufendes und kommendes Schuljahr
  als Tabelle, ohne Abo
- **Reproduzierbare Ausgabe** — `DTSTAMP` stammt aus den Quelldaten, nicht von der
  Wanduhr. Gleiche Eingabe, gleiche Bytes: der nächtliche Lauf löst keinen
  unnötigen Neu-Download bei allen Abonnenten aus
- **Nur Schultermine** — allgemeine Feiertage werden herausgefiltert, weil sie
  fast immer ohnehin in den Ferien oder auf einem Wochenende liegen
- **Kalendertaugliche Titel** — das Präfix `Schulen Stadt Zürich schulfrei:`
  entfällt, Klammerzusätze wandern in die Beschreibung
- **`Schulschluss 12 Uhr` als Termin um 12 Uhr**, nicht als Ganztagestermin —
  an diesem Tag ist nicht schulfrei
- Zeitfenster ab Beginn des vorletzten Jahres — keine Altlasten zurück bis 2018 im Kalender
- Ganztägige Termine (`VALUE=DATE`) mit korrekt exklusiven Enddaten
- Deterministische SHA-256-UIDs über die Rohdaten — Titeländerungen aktualisieren
  bestehende Abos, statt sie neu zu synchronisieren
- `TRANSP:TRANSPARENT` — Ferien blockieren nie die Frei/Gebucht-Anzeige
- Sanity-Gate: unplausible oder unvollständige API-Antworten lassen die
  Pipeline fehlschlagen, statt den letzten guten Feed zu überschreiben
- **Vorwarnung statt stillem Auslaufen**: Reicht die Quelle weniger als 180 Tage
  in die Zukunft oder fehlt das laufende Schuljahr, schlägt der Build fehl —
  rund ein halbes Jahr, bevor der Feed inhaltlich leer liefe
- Testsuite auf Fixtures (`pytest`), läuft ohne Netz in der CI
- Keine Server, keine Secrets: GitHub Actions (OIDC) + GitHub Pages

## Was der Feed nicht abdeckt

- **Allgemeine Feiertage.** Sie stehen im Originaldatensatz, sind hier aber
  bewusst nicht enthalten (siehe oben). Kalender-Apps bringen dafür einen
  eigenen Schweizer Feiertagskalender mit.
- **Schulinterne Termine.** Weiterbildungstage, Elterngespräche oder
  Projektwochen legt jede Schule selbst fest; sie sind nicht Teil des
  stadtweiten Datensatzes.
- **Betreuung.** Schulfrei heisst nicht automatisch, dass Hort oder
  Ferienbetreuung geschlossen sind oder offen haben. Dazu gibt es keine
  offenen Daten — Auskunft gibt die Schule.

## Wissenswerte Eigenheiten der Daten

- Das CKAN-`end_date` ist **bereits exklusiv** (iCal-Konvention). Die
  Sportferien 2026 dauern vom 9. bis 20. Februar und sind als
  `2026-02-09 → 2026-02-21` gespeichert. Das Skript wendet deshalb **keine**
  `+1 Tag`-Korrektur an — sie würde jeden Ferientermin einen Tag zu lang machen.
- Einzelne eintägige Einträge liefern `end_date == start_date`; diese werden
  zu korrekten Eintages-Terminen normalisiert.
- Der Feed beginnt am 1. Januar des vorletzten Jahres (`CUTOFF_YEARS_BACK = 2`,
  am 22.08.2026 also `2024-01-01`). Der
  CKAN-Datensatz reicht zurück bis 2018; ungefiltert wären rund zwei Drittel
  der Termine reine Vergangenheit. Ein Termin, der über die Grenze reicht
  (etwa die Weihnachtsferien 2023/24), bleibt **vollständig** erhalten — der
  Filter kürzt nie einen laufenden Termin.
- Der Datensatz mischt Schultermine (Präfix `Schulen Stadt Zürich`) mit
  allgemeinen Feiertagen. Im Fenster ab 2024 sind das 76 Schultermine gegenüber
  97 Feiertagen — von denen 94 vollständig in einem ohnehin schulfreien Block
  liegen und 22 ausschliesslich auf Wochenenden. Publiziert werden nur die
  Schultermine.
- Die Titel sind Datenbankstrings bis 137 Zeichen Länge. Nach dem Kürzen bleiben
  maximal 42 — der Rest steht als `DESCRIPTION` am Termin.
- Kleinere Inkonsistenzen der Quelle: `Schulschluss 12 Uhr` neben
  `Schulschluss um 12 Uhr`, `(KW29-33)` neben `(KW 29-33)`. Beides wird
  normalisiert.
- Die UIDs hashen `(roher summary, start, end)` — bewusst die *unbereinigte*
  Zusammenfassung, damit eine Titeländerung bestehende Abos aktualisiert statt
  sie neu zu synchronisieren. Eine Datums­änderung erscheint dagegen als «alter
  Termin entfernt, neuer Termin hinzugefügt». Das ist beabsichtigt: Der
  Generator bleibt zustandslos.

- Die Stadt publiziert diese Termine **zweimal**: als CKAN-Datensatz, aus dem
  dieser Feed gebaut wird, und als je eine statische `.ics` pro Schuljahr auf
  der [Schulferien-Seite](https://www.stadt-zuerich.ch/de/bildung/volksschule/schulferien.html).
  `scripts/compare_official_ics.py` gleicht beide gegeneinander ab. Stand
  24.08.2026, über alle vier angebotenen Schuljahre: 104 Einträge identisch,
  keine unerklärte Abweichung. Die beiden systematischen Unterschiede sprechen
  für CKAN — die Jahresdateien schneiden die Sommerferien an der
  Schuljahresgrenze (1. August) ab, während CKAN den Block vollständig führt,
  und CKAN enthält bei den Feiertagen eine Dublette mit gleichem Zeitraum
  (`Pfingsten` / `Pfingstsonntag`, 20.05.2029), die der Feed ohnehin
  herausfiltert. In der `.ics`-Übergabe steckt also nichts, was der offene
  Datensatz nicht hätte.

## Voraussetzungen

- Python 3.10+
- `requests`, `icalendar` (siehe `requirements.txt`)

## Verwendung

```bash
pip install -r requirements-dev.txt
pytest -q                 # Testsuite, läuft offline auf Fixtures
python generate_ics.py    # schreibt public/ferien.ics + public/index.html

python scripts/compare_official_ics.py   # mit Netz: beide Exporte der Stadt vergleichen
```

## Projektstruktur

```
zuerich-schulferien-ics/
├── generate_ics.py           # CKAN abrufen → filtern → ICS + Seite bauen → Sanity-Gate
├── tests/                    # pytest-Suite auf Fixtures, ohne Netzzugriff
├── scripts/compare_official_ics.py  # Abgleich mit den .ics-Dateien der Stadt
├── requirements.txt
├── requirements-dev.txt
├── web/index.html            # Vorlage der Landing-Page (Abo-Anleitung)
├── public/ferien.ics         # generierter Feed (deployt auf GitHub Pages)
├── public/index.html         # gerenderte Landing-Page (wird mitdeployt)
├── .github/workflows/deploy.yml    # nächtlicher Cron, OIDC-Deploy, Alarm bei Fehlschlag
└── .github/workflows/keepalive.yml # monatlicher Heartbeat gegen das Abschalten des Cron
```

## Changelog

Siehe [CHANGELOG.md](CHANGELOG.md)

## Mitwirken

Beiträge sind willkommen — siehe [CONTRIBUTING.md](CONTRIBUTING.md).

## Sicherheit

Schwachstellen bitte wie in [SECURITY.md](SECURITY.md) beschrieben melden.

## Lizenz

MIT-Lizenz — siehe [LICENSE](LICENSE)

## Autor

Hayal Özkan · [malkreide](https://github.com/malkreide)
