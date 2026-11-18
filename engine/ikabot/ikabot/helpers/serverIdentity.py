"""Fail-closed player-name attestation from a fresh, server-served game page.

Do not infer the player's identity from Session.username, a saved account, a
lobby account list or the caller's request. Only an exact marker in the HTTPS
world page received with the game cookie can attest the active player. This
module performs NO requests and never retains or exposes game-page HTML.
"""
from __future__ import annotations

import json
import re
import unicodedata
from html.parser import HTMLParser

_ALLOWED_IDS = frozenset({"avatarName", "playerName", "js_avatarName"})
_SCRIPT_GAME = re.compile(r"(?:\bvar\s+|\bwindow\.)?\bgame\s*=\s*\{")
_SCRIPT_NAME = re.compile(r'["\x27]avatarName["\x27]\s*:\s*("(?:[^"\\\\]|\\\\.)*")')
_SCRIPT_TAG = re.compile(r"<script(?:\s[^>]*)?>([\s\S]*?)</script\s*>", re.IGNORECASE)
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


def _name(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = unicodedata.normalize("NFC", " ".join(value.split()))
    if not normalized or len(normalized) > 100 or _CONTROL.search(normalized):
        return None
    return normalized


# HTML void tags do not have matching end tags. Tracking them as open
# elements would hide the real player marker inside the toolbar.
_VOID_TAGS = frozenset({
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link",
    "meta", "param", "source", "track", "wbr",
})


class _OwnerHeader(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._elements: list[tuple[str, bool]] = []
        self._capture_at: int | None = None
        self._content: list[str] = []
        self.candidates: list[str] = []
        self.invalid = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        classes = set((attributes.get("class") or "").split())
        is_toolbar = tag == "div" and (
            attributes.get("id") == "GF_toolbar" or "GF_toolbar" in classes
        )
        # The live Ikariam self-name is in <div id="GF_toolbar"> ...
        # <li class="avatarName">PLAYER</li>, not an id="avatarName" node.
        # An unscoped avatarName CSS class is not proof of account identity.
        is_live_avatar = (
            tag == "li" and "avatarName" in classes
            and any(toolbar for _, toolbar in self._elements)
        )
        is_legacy_avatar = (
            tag in {"span", "div", "a", "strong"}
            and attributes.get("id") in _ALLOWED_IDS
        )
        if self._capture_at is None and (is_live_avatar or is_legacy_avatar):
            self._capture_at = len(self._elements)
            self._content = []
        if tag not in _VOID_TAGS:
            self._elements.append((tag, is_toolbar))

    def handle_data(self, data: str) -> None:
        if self._capture_at is not None:
            self._content.append(data)

    def handle_endtag(self, tag: str) -> None:
        # HTMLParser does not repair omitted closing tags. Close through the
        # nearest matching start tag and reject captured malformed markup.
        index = next(
            (i for i in range(len(self._elements) - 1, -1, -1)
             if self._elements[i][0] == tag), None,
        )
        if index is None:
            return
        if self._capture_at is not None and index <= self._capture_at:
            if index != self._capture_at:
                self.invalid = True
            candidate = _name("".join(self._content))
            if candidate is None:
                self.invalid = True
            else:
                self.candidates.append(candidate)
            self._capture_at = None
            self._content = []
        del self._elements[index:]


def attest_player_from_world_html(html: object, expected_player: str) -> bool:
    """Require at least one unambiguous server-page *self* name, never metadata.

    Modern Ikariam layouts may express the current avatar as a named header
    or as the game configuration's avatarName. Missing/changed layout is NOT
    proof of identity: recovery and task start remain disabled until reviewed.
    """
    expected = _name(expected_player)
    if (
        expected is None or not isinstance(html, str) or len(html) > 2_000_000
        or not html
    ):
        return False
    parser = _OwnerHeader()
    try:
        parser.feed(html)
        parser.close()
    except (ValueError, AssertionError):
        return False
    if parser.invalid or parser._capture_at is not None:
        return False
    names = parser.candidates
    for script in _SCRIPT_TAG.finditer(html):
        data = script.group(1)
        if not _SCRIPT_GAME.search(data):
            continue
        for match in _SCRIPT_NAME.finditer(data):
            try:
                parsed = _name(json.loads(match.group(1)))
            except (ValueError, TypeError):
                return False
            if parsed is None:
                return False
            names.append(parsed)
    return bool(names) and all(name.casefold() == expected.casefold() for name in names)
