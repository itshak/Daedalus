# Design — desktop migration

Review local `src/ikabot/gui`, `models.py`, `report.py` and settings file by file before porting. Rename the GUI package to avoid colliding with the upstream engine's `ikabot` import name. Preserve native PySide6 Fluent look and macOS window behavior; audit dependency licenses.

Replace the Selenium-only report runner with a typed Daedalus backend API client. Keep CSV, JSON, text, island-grouped exports and the 220K unsecured-resource filter. Provide generic task forms driven by engine schemas, with dedicated views for warehouses, wine and construction.

Handle backend login-required notifications without ever logging raw credentials or creating independent browser game sessions for reporting.
