"""Opt-in, isolated human browser login with a verified world-cookie handoff.

The operator, not Daedalus, enters credentials and solves challenges. Playwright
is used only to display the official pages and read the world cookie after the
operator confirms completion. No persistent browser profile is created.
"""
from __future__ import annotations

import logging
import re
from collections.abc import Callable
from typing import Protocol

from daedalus.account_sessions import AccountSessionCoordinator, SessionBusyError
from daedalus.accounts import Account
from daedalus.saved_session_recovery import (
    CredentialStore,
    SavedSessionUnavailable,
    _email_binding,
    _real_restore,
    _require_cookie_account,
    _validated_world_cookie,
    _verify_and_save_world_cookie,
)

_WORLD = re.compile(r"s[0-9]{1,6}-[a-z]{2,4}\Z", re.IGNORECASE)


class HumanBrowser(Protocol):
    def open(self, lobby_url: str, world_url: str) -> None: ...
    def world_cookie(self, world_host: str) -> str | None: ...
    def close(self) -> None: ...


class PlaywrightHumanBrowser:
    """Ephemeral visible browser. Never fills forms, clicks CAPTCHA or logs secrets."""

    def __init__(self) -> None:
        self._playwright = None
        self._browser = None
        self._context = None

    def open(self, lobby_url: str, world_url: str) -> None:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise SavedSessionUnavailable(
                "Install the optional browser-recovery extra and Playwright Chromium"
            ) from exc
        try:
            self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.launch(headless=False)
            self._context = self._browser.new_context(accept_downloads=False)
            # Do not navigate automatically to a world URL: that can create
            # an unintended login/session. The operator navigates manually.
            self._context.new_page().goto(lobby_url, wait_until="domcontentloaded", timeout=30000)
        except Exception as exc:
            raise SavedSessionUnavailable("Unable to launch the protected login browser") from exc

    def world_cookie(self, world_host: str) -> str | None:
        if self._context is None:
            raise SavedSessionUnavailable("The assisted browser is not open")
        try:
            matches = [
                cookie for cookie in self._context.cookies(["https://" + world_host + "/"])
                if cookie.get("name") == "ikariam"
                and cookie.get("domain", "").lstrip(".").casefold() == world_host.casefold()
                and cookie.get("secure") is True
            ]
        except Exception as exc:
            raise SavedSessionUnavailable("Unable to inspect the authenticated world cookie") from exc
        if len(matches) != 1:
            return None
        return _validated_world_cookie(matches[0].get("value"))

    def close(self) -> None:
        try:
            if self._context is not None:
                self._context.close()
            if self._browser is not None:
                self._browser.close()
        finally:
            if self._playwright is not None:
                self._playwright.stop()
            self._context = self._browser = self._playwright = None


def recover_with_human_browser(
    account: Account,
    coordinator: AccountSessionCoordinator,
    *,
    confirmed: bool,
    human_confirm: Callable[[], bool],
    browser: HumanBrowser | None = None,
    credential_store: CredentialStore | None = None,
    restore: Callable[[Account, str, str], object] = _real_restore,
) -> dict[str, str]:
    """Hold the exact owner lease across human login, verification and keyring save.

    Remote deployment fallback: run this on the authoritative host inside an
    authenticated graphical remote-desktop session. Never tunnel browser
    cookies over Daedalus API or create a second engine login.
    """
    if confirmed is not True:
        raise SavedSessionUnavailable("Explicit browser recovery consent is required")
    _require_cookie_account(account, coordinator)
    _email_binding(account, credential_store)
    if _WORLD.fullmatch(account.world) is None:
        raise SavedSessionUnavailable("A canonical world is required")
    world_host = f"{account.world.casefold()}.ikariam.gameforge.com"
    client = browser or PlaywrightHumanBrowser()
    try:
        with coordinator.acquire(account.id):
            try:
                client.open("https://lobby.ikariam.gameforge.com/", "https://" + world_host + "/")
                if human_confirm() is not True:
                    raise SavedSessionUnavailable("The operator did not confirm completed login")
                cookie = client.world_cookie(world_host)
                if cookie is None:
                    raise SavedSessionUnavailable("No verified world cookie found; manual help is needed")
                return _verify_and_save_world_cookie(
                    account, cookie, credential_store=credential_store, restore=restore,
                )
            finally:
                try:
                    client.close()
                except Exception:  # noqa: BLE001 - never expose browser errors or secrets
                    logging.getLogger("daedalus.browser_recovery").warning(
                        "Ephemeral browser cleanup was incomplete"
                    )
    except SessionBusyError as exc:
        raise SavedSessionUnavailable("Another worker owns this account on the host") from exc
