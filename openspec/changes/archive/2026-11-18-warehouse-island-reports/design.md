# Island-grouped reports design

Use the already-present city coordinates returned by upstream `getIdsOfCities(session)` during the current warehouse request. Validate against a restrictive numeric `x:y` island-coordinate pattern; an invalid field becomes null and cannot echo arbitrary HTML, tokens or secret strings.

The typed IPC adapter accepts an optional island field, which keeps older compatible engine versions usable. The pure reporting layer includes an optional `island` column and a TXT exporter that groups known coordinates and explicitly labels unknown islands.

The GUI groups only after applying its existing 220K filter. No game worker lifecycle, API authorization or account owner changes. Unit tests cover malformed island values, unknown/zero resource quantities, sorting and headless Qt export controls.
