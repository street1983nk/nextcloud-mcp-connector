---
quick_id: 261126-i60
status: code-complete
date: 2026-11-26
---

# Quick 261126-i60: Konto-ID in DAV-Pfaden (Issue 60, Grundlage 0.9.1)

Lokal auf main, nicht gepusht. Version und CHANGELOG unverändert, das macht der Release-Schritt nach Owner-Freigabe.

## Commits

- fbbab53a test: account id and login name differ in every DAV path (issue 60, red)
- 6ee89ea5 test: give the fake tool context its AppAPI headers (issue 60, red)
- 7bfb19e7 fix: name DAV homes by the account id, sign in with the login name (issue 60)
- 2c506e02 docs(quick-261126-i60): plan of the account id in DAV paths (issue 60)

## Ergebnis

- `Credentials` hat jetzt `account_id` und `account` (`account_id or user`). Basic Auth nutzt weiter `user`, also den Login-Namen. Alle DAV-Homes und ID-Vergleiche nutzen `account`: Dateien, Suche, Versionen, Uploads, das Parsen der Home-hrefs, das systemtags-Home, der Admin-Vergleich, das Kalender- und das Adressbuch-Home (Aufgaben inklusive).
- OAuth-Weg: `account_id = identity.principal`. Der Wert kommt nur aus der gespeicherten Zeile, nie aus dem Request. Legacy-Zeilen ohne `nc_account_id` behalten den Login-Namen.
- Impersonation: Der AppAPI-Header nennt den principal und nicht den Login-Namen. Die heutige Quelle (`exchange_appapi.py`) setzt beide Werte gleich.
- Die Caches sind jetzt über `identity_key = (base_url, user, account)` verschlüsselt. Das ist nie gröber als vorher, so kann sich kein Eintrag über zwei Konten teilen.
- Passthrough und stdio bleiben unverändert, denn ohne einen Netzaufruf pro Request gibt es keine verlässliche ID. Das ist im Code dokumentiert.
- `_home_prefix` bleibt bewusst ohne `quote`, weil die hrefs segmentweise decodiert verglichen werden. Ein Test belegt das.

## Gegenprobe

- Mutation zurück auf den Login-Namen: 31 von 37 neuen Tests rot.
- Die 6 grünen Tests prüfen gewollt gleichbleibendes Verhalten: Basic-Login, Legacy-Fall und repr.

## Gates (lokal)

- ruff, ruff format (417 Dateien), pyright (latest): 0 Fehler.
- vulture: rc 0.
- Tool-Budget-Gate: grün.
- pytest tests/unit tests/contract: 8349 passed, 37 skipped.

## Offen

- Docker-Integrationstests und `pytest -m matrix`.
- Live-Test mit Login per E-Mail und mit einem Konto, dessen ID abweicht: Dateien, Suche, Versionen, Upload, Tags/Admin, Kalender, Aufgaben, Kontakte.
- Release 0.9.1 mit CHANGELOG (Vorschlag im Chat 26.11.), secure-phase, Owner-Freigabe, Tag, Store.
- Danach Antwort in Issue 60.
