"""In-memory Settings adapter for the original IkaBot LoginFlow.

The upstream config.ini-based Settings implementation intentionally is
not used: Daedalus saves approved credentials only in the OS Keychain.
"""
from __future__ import annotations
from dataclasses import dataclass, field

@dataclass(frozen=True, repr=False)
class Settings:
    password: str = field(repr=False)
