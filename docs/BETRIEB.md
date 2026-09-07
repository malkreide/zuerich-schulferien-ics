# Betrieb und Übergabe

Dieses Dokument richtet sich an die Person oder Stelle, die den Feed betreibt —
nicht an Abonnentinnen und Abonnenten. Es beantwortet drei Fragen: Wer ist
zuständig, was tue ich bei einer Störung, und wie geht dieser Dienst
kontrolliert in andere Hände über.

## Was hier betrieben wird

Ein abonnierbarer Kalender-Feed. Das ist betrieblich etwas anderes als eine
Datei zum Herunterladen: Die Adresse liegt in fremden Kalendern, wird täglich
automatisch abgefragt und lässt sich nicht zurückrufen. Zwei Eigenschaften
folgen daraus und prägen jede Entscheidung in diesem Dokument.

- **Ein Ausfall ist unsichtbar.** Schlägt der nächtliche Lauf fehl, bleibt der
  zuletzt erfolgreich gebaute Feed auf GitHub Pages liegen und wird weiter
  ausgeliefert. Niemand bemerkt etwas — der Feed altert einfach still. Deshalb
  eröffnet der Workflow bei einem Fehlschlag automatisch ein Issue.
- **Eine Adressänderung bricht bestehende Abos.** Wer heute abonniert hat,
  bekommt keine Mitteilung über eine neue Adresse. Deshalb der Abschnitt
  «Umzug» weiter unten, und deshalb die eine Regel, die nie gebrochen wird.

## Die eine Regel

`UID_DOMAIN` in `generate_ics.py` wird **nicht verändert** — auch dann nicht,
wenn das Projekt einer anderen Person, einer Organisation oder einer eigenen
Domain gehört. Der Wert ist ein technischer Schlüssel, kein Absender.

Jeder Termin trägt eine UID, die auf diese Domain endet, und Kalender-Apps
erkennen abonnierte Termine an genau dieser UID. Wird sie umgeschrieben, gilt
der gesamte Feed als neu: Jeder Ferientermin verschwindet aus jedem
abonnierten Kalender und wird neu angelegt, Erinnerungen werden
zurückgesetzt, und Programme, die die alte Fassung behalten, zeigen jeden
Termin doppelt.

Der Wert sieht nach dem Namen des heutigen Kontos aus, und genau deshalb ist
er gefährdet: Eine gut gemeinte Suchen-und-Ersetzen-Aktion beim Umzug erwischt
ihn. `tests/test_generate_ics.py::test_uid_domain_survives_a_move` schlägt in
diesem Fall fehl. Schlägt dieser Test fehl, ist die Änderung der Fehler, nicht
der Test.

## Rollen

Vor dem produktiven Betrieb festhalten — mit Namen, nicht mit Funktionen:

| Rolle | Aufgabe |
|---|---|
| Fachliche Verantwortung | Entscheidet, was der Feed enthält und was er verspricht |
| Technische Betreuung | Reagiert auf Fehler-Issues, führt Aktualisierungen durch |
| Stellvertretung | Dasselbe, bei Abwesenheit — mit eigenem Zugriff, nicht mit geteiltem Passwort |
| Organisations-Owner | Mindestens drei Personen, siehe `docs/GOVERNANCE-SCHULAMT-ORG.md` |

Eine Betreuung, die an genau einer Person hängt, ist kein Betrieb, sondern ein
Hobby mit Publikum. Das ist bis zur Übergabe der Ist-Zustand dieses Projekts
und der Hauptgrund, ihn zu beenden.

## Wie der Dienst läuft

- `.github/workflows/deploy.yml` läuft nächtlich um 02:23 UTC, bei jedem Push
  auf `main` und auf manuelle Auslösung. Er testet, ruft den CKAN-Datastore
  ab, erzeugt drei `.ics`-Dateien und die Landing-Page und veröffentlicht
  alles auf GitHub Pages.
- Eine Plausibilitätsprüfung bricht den Lauf hart ab, wenn die Quelle
  unglaubwürdig aussieht (zu wenige Termine, weniger als 180 Tage Vorlauf,
  fehlendes laufendes Schuljahr). Ein kaputter Lauf überschreibt damit nie
  einen funktionierenden Feed.
- Schlägt etwas fehl, eröffnet oder ergänzt der Job `alert` das Issue
  «Feed-Build fehlgeschlagen».
- `.github/workflows/keepalive.yml` schreibt monatlich einen Zeitstempel nach
  `.github/last-heartbeat`. GitHub deaktiviert geplante Workflows in
  öffentlichen Repositories nach 60 Tagen ohne Aktivität — ohne diesen
  Herzschlag schaltet sich ein Projekt, das einfach funktioniert, nach zwei
  ruhigen Monaten selbst ab.

## Störungen

### Das Issue «Feed-Build fehlgeschlagen» ist offen

```bash
pip install -r requirements-dev.txt
python generate_ics.py          # zeigt die Abbruchmeldung im Klartext
```

Häufigste Ursachen, in dieser Reihenfolge:

1. **Die Stadt hat die Schreibweise der Titel geändert.** Veröffentlicht
   werden nur Datensätze mit dem Präfix `Schulen Stadt Zürich`. Fällt es weg,
   ist der Feed schlagartig leer und die Prüfung greift. Behebung:
   `SCHOOL_RECORD_RE` und `TITLE_PREFIX_RE` in `generate_ics.py` anpassen.
2. **Das nächste Schuljahr ist noch nicht publiziert.** Die Quelle muss 180
   Tage vorausreichen. Das ist kein Softwarefehler, sondern eine Nachfrage bei
   der datenliefernden Stelle.
3. **Die CKAN-API war nicht erreichbar.** Lauf manuell wiederholen
   (Actions → Generate and deploy ICS feed → Run workflow).

Ob die Abweichung an den Daten oder am Code liegt, klärt der Abgleich gegen
die offiziellen `.ics`-Dateien der Stadt:

```bash
python scripts/compare_official_ics.py    # braucht Netzzugriff
```

Issue schliessen, sobald ein Lauf wieder grün ist.

### Der Feed ist veraltet, aber nichts ist rot

Der Verdacht lautet: GitHub hat die geplanten Workflows deaktiviert.
Nachsehen unter Actions — deaktivierte Workflows werden dort mit einem
Hinweis und einer Schaltfläche zum Reaktivieren angezeigt. Danach prüfen, ob
der Keepalive noch läuft, und das Datum in `.github/last-heartbeat` ansehen.

### Ein Termin ist falsch

Zuerst `scripts/compare_official_ics.py` laufen lassen. Stimmt der Feed mit
den offiziellen Dateien der Stadt überein, liegt der Fehler in den
Originaldaten und kann nur bei der Quelle korrigiert werden — der Feed gibt
sie bewusst unverändert weiter. Das gehört auch so kommuniziert.

## Wiederkehrende Aufgaben

| Wann | Was |
|---|---|
| Jährlich, im Frühling | Ist das nächste Schuljahr in der Quelle vorhanden? Sonst nachfragen, bevor die 180-Tage-Prüfung anschlägt |
| Halbjährlich | Dependabot-Pull-Requests abarbeiten, Action-Pins prüfen |
| Halbjährlich | Zugriffsreview: Wer ist Owner, wer hat Schreibrechte, stimmt das noch |
| Bei Personalwechsel | CODEOWNERS, Rollen oben und die Zugänge nachführen |

## Umzug in eine andere Organisation

Der Feed ist so gebaut, dass ein Umzug keine Codeänderung braucht. Adresse und
Quellcode-Link kommen aus der Umgebung, gesetzt als Repository-Variablen unter
Settings → Secrets and variables → Actions → Variables:

| Variable | Bedeutung | Beispiel |
|---|---|---|
| `PAGES_CUSTOM_DOMAIN` | Eigene Domain, als reiner Hostname | `schulferien.stadt-zuerich.ch` |
| `FEED_BASE_URL` | Basisadresse der Feeds; überschreibt die Domain | `https://schulferien.stadt-zuerich.ch` |
| `REPO_URL` | Quellcode-Link auf der Landing-Page | `https://github.com/schulamt-zuerich/schulferien` |

Nicht gesetzt heisst unverändert: Ein Checkout ohne Konfiguration
veröffentlicht genau das, was heute ausgeliefert wird. Ein Tippfehler lässt
den Build scheitern, statt eine Seite zu publizieren, deren Abo-Schaltflächen
ins Leere zeigen.

### Reihenfolge

Die Reihenfolge ist der eigentliche Inhalt dieser Checkliste. **Zuerst die
Domain, dann der Transfer** — umgekehrt bricht man Abos zweimal statt keinmal.

1. **Eigene Domain beschaffen und aufschalten**, solange das Repository noch
   am alten Ort liegt. Ist der Feed erst unter der eigenen Adresse erreichbar,
   ist der Kontowechsel für Abonnentinnen und Abonnenten unsichtbar.
   - DNS-Eintrag auf GitHub Pages setzen (CNAME auf `<konto>.github.io`).
   - Settings → Pages → Custom domain eintragen, HTTPS erzwingen.
   - `PAGES_CUSTOM_DOMAIN` als Repository-Variable setzen, Workflow manuell
     auslösen, Landing-Page und `public/CNAME` prüfen.
   - Alte und neue Adresse eine Zeit lang parallel beobachten.
2. **Zielorganisation vorbereiten:** Owner benannt (mindestens drei),
   Funktionspostfach hinterlegt, Zwei-Faktor-Wiederherstellungscodes
   auffindbar abgelegt, Team für CODEOWNERS angelegt.
3. **Repository transferieren** (Settings → General → Transfer ownership).
   Transfer, nicht neu anlegen: History, Issues und die Weiterleitung der
   alten Adresse bleiben erhalten.
4. **In der Zielorganisation nachziehen:**
   - Pages aktivieren, Source «GitHub Actions», Custom domain erneut
     eintragen (die Einstellung reist nicht mit).
   - Repository-Variablen erneut setzen, `REPO_URL` auf die neue Adresse.
   - Actions aktivieren und den Workflow einmal manuell auslösen.
   - CODEOWNERS auf das Team der Organisation umstellen.
   - Sicherheitsmeldeweg prüfen: `SECURITY.md` nennt die private
     Schwachstellenmeldung — sie muss in der neuen Organisation aktiviert und
     einer erreichbaren Adresse zugeordnet sein.
5. **Texte nachführen:** `README.md`, `README.de.md`, `.github/repo-meta.yml`,
   `LICENSE` (Rechteinhaberin), CHANGELOG-Eintrag. Diese Dateien nennen
   Adressen im Fliesstext; sie sind bewusst nicht automatisiert, weil sie
   redaktionell und nicht technisch sind.
6. **Prüfen, mit einem echten Kalender**, nicht nur im Browser: Abo unter der
   neuen Adresse in Apple Kalender und Google Kalender anlegen, und ein
   bestehendes altes Abo daraufhin ansehen, ob Termine doppelt erscheinen.
   Erscheinen sie doppelt, wurde `UID_DOMAIN` verändert.
7. **Die alte Adresse mindestens zwölf Monate erreichbar lassen.** Sie steht
   in Abos, in Elternbriefen, in Lesezeichen. Ein Schuljahr ist die
   Mindestfrist, bevor sie verschwinden darf.

### Was ein Transfer nicht mitnimmt

Repository-Variablen, Pages-Einstellungen inklusive Custom Domain,
Branch-Schutzregeln und die Aktivierung von Actions. Alles davon nach dem
Transfer bewusst neu setzen — das Repository sieht sonst vollständig aus und
publiziert trotzdem nichts.

## Kontrollierte Abschaltung

Falls der Dienst je eingestellt wird, ist Stillschweigen die schlechteste
Variante: Der Feed bleibt in den Kalendern stehen und wird still falsch.
Stattdessen:

1. Auf der Landing-Page und im README ankündigen, mit Datum und Begründung.
2. Mindestens ein Schuljahr Vorlauf geben.
3. Bis zur Abschaltung weiterbauen — ein eingefrorener Feed ist gefährlicher
   als ein abgeschalteter, weil er weiterhin plausibel aussieht.
4. Nach Ablauf der Frist das Repository archivieren und die Adresse abstellen,
   damit Kalender-Apps einen klaren Fehler zeigen statt veralteter Termine.
