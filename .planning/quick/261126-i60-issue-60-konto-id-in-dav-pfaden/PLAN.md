---
quick_id: 261126-i60
type: quick
autonomous: true
---

# Quick 261126-i60: Konto-ID statt Login-Name in DAV-Pfaden (Issue 60)

## Anlass

Issue 60 (LDAP/AD): Login-Name (`imedina`) und Nextcloud-User-ID (GUID
`B9642E94-77DA-4189-9CF3-155646E581ED`) unterscheiden sich. Im OAuth-Weg baut
`deps._credentials_from_oauth` die `Credentials` mit `user=identity.nc_user` (Login-Name aus
Login Flow v2). `Credentials.user` dient als Basic-Name (richtig) und als Segment aller
DAV-Pfade `/remote.php/dav/files/<user>/` (falsch, 404). Gleiches bei Login per E-Mail.
Die kanonische Konto-ID liegt serverseitig in der Verbindungszeile (`nc_account_id`,
`principal_of`) und steht als `identity.principal` schon bereit.

## Lösung

- `Credentials` bekommt `account_id: str = ""` (Konto-ID, nur aus dem gespeicherten Wert)
  und die Eigenschaft `account` (`account_id or user`). Basic-Auth bleibt beim Login-Namen,
  alle Pfade und ID-Vergleiche nutzen `account`.
- OAuth-Weg: `account_id=identity.principal`. Legacy-Zeilen ohne `nc_account_id`: principal
  ist der Login-Name, Verhalten unverändert.
- Impersonation (AppAPI-Header braucht die User-ID): `user=identity.principal`.
- AppAPI-Header-Weg: `user` ist bereits die User-ID, unverändert.
- Passthrough/stdio (Basic mit eingegebenem Namen): keine verlässliche ID ohne Netzaufruf,
  unverändert und dokumentiert.
- Stellen: dav.files_url, search_scope, _home_prefix, versions_url, uploads_url;
  systemtags.home_url, confirm_admin; caldav.calendars_home_url; carddav.addressbooks_home_url;
  Cache-Keys in capabilities.py und exclusion.py.

## Tasks

1. RED: tests/unit/test_account_id_paths.py mit Login != ID (`imedina`, `ivan@example.com`),
   Commit `test:`.
2. GREEN: Umsetzung, Commit `fix:`.
3. Gegenprobe: Mutation (account -> user) macht die neuen Tests rot, zurücknehmen.
4. Gates wie CI: ruff check, ruff format --check, pyright (latest), vulture, pytest
   tests/unit tests/contract. Integration (Docker) steht aus.

## Regeln

Kein Push, kein Tag, kein GitHub-Kommentar, kein Docker, keine Store-Aktion, CHANGELOG und
Version nicht bumpen.
