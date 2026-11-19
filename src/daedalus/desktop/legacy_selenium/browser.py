"""WebDriver factory (Firefox/Chrome) with webdriver-manager driver provisioning.

Chrome uses undetected-chromedriver to strip automation fingerprints and
reduce CAPTCHA challenges, with a plain chromedriver fallback.
"""

from __future__ import annotations

import logging
import os
import platform
import re
import subprocess
import sys
import urllib.request

from selenium.common.exceptions import (
    InvalidSessionIdException,
    NoSuchWindowException,
    WebDriverException,
)
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.webdriver import WebDriver as ChromeDriver
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.firefox.webdriver import WebDriver as FirefoxDriver
from selenium.webdriver.remote.webdriver import WebDriver

logger = logging.getLogger(__name__)

# Headless Chrome on macOS/Linux can crash with
# ``InvalidSessionIdException: session deleted as the browser has closed the connection
# ... disconnected from DevTools``. The two proven mitigations are disabling the GPU
# process (which is unnecessary in headless) and avoiding the tiny /dev/shm on Linux.
# The background-throttling flags are intentionally *not* set: in headless the game tab
# is considered a background tab and throttling it kills the DevTools heartbeat.
_CHROME_STABILITY_ARGS = (
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-gpu",
    "--disable-dev-shm-usage",
    "--disable-renderer-backgrounding",
    "--disable-backgrounding-occluded-windows",
    "--disable-hang-monitor",
    "--disable-ipc-flooding-protection",
)


def is_session_alive(driver) -> bool:
    """Cheaply confirm the browser session is still connected and alive."""
    if driver is None:
        return False
    try:
        handles = getattr(driver, "window_handles", None)
        if handles is not None and not handles:
            return False
        try:
            _ = driver.current_url  # the round-trip itself is the liveness probe
            return True
        except (NoSuchWindowException, WebDriverException):
            if handles and hasattr(driver, "switch_to"):
                try:
                    driver.switch_to.window(handles[-1])
                    _ = driver.current_url
                    return True
                except Exception:
                    return False
            return False
    except (InvalidSessionIdException, WebDriverException):
        return False
    except Exception:
        return False


def create_driver(browser: str = "firefox", headless: bool = False) -> WebDriver:
    """Create a maximized driver instance for the given browser."""
    browser = browser.lower()
    if browser == "chrome":
        driver = _create_chrome(headless)
    else:
        driver = _create_firefox(headless)
    driver.set_page_load_timeout(60)
    try:
        driver.maximize_window()
    except WebDriverException:
        logger.debug("window maximize failed (headless=%s)", headless)
    logger.info("driver created: %s (headless=%s)", browser, headless)
    return driver


def _find_chrome_executable() -> str | None:
    """Locate a Chrome/Chromium binary (mirrors uc's own lookup, used to pin the path)."""
    candidates = []
    if sys.platform == "darwin":
        candidates.extend(
            [
                "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                "/Applications/Chromium.app/Contents/MacOS/Chromium",
            ]
        )
    for entry in os.environ.get("PATH", "").split(os.pathsep):
        for name in ("google-chrome", "chromium", "chromium-browser", "chrome", "google-chrome-stable"):
            candidates.append(os.path.join(entry, name))
    for candidate in candidates:
        if candidate and os.path.exists(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return None


def _create_chrome(headless: bool) -> WebDriver:
    try:
        import undetected_chromedriver as uc

        options = uc.ChromeOptions()
        if headless:
            options.add_argument("--headless=new")
            options.add_argument("--window-size=1920,1080")
        for arg in _CHROME_STABILITY_ARGS:
            options.add_argument(arg)
        driver = uc.Chrome(
            options=options,
            browser_executable_path=_find_chrome_executable(),
            driver_executable_path=_ensure_chromedriver(),
            use_subprocess=False,
        )
        logger.info("undetected chrome driver active")
        return driver
    except Exception as exc:  # noqa: BLE001
        logger.warning("undetected-chromedriver failed (%s); falling back to plain chromedriver", exc)
        from webdriver_manager.chrome import ChromeDriverManager

        options = ChromeOptions()
        if headless:
            options.add_argument("--headless=new")
            options.add_argument("--window-size=1920,1080")
        for arg in _CHROME_STABILITY_ARGS:
            options.add_argument(arg)
        service = ChromeService(ChromeDriverManager().install())
        return ChromeDriver(service=service, options=options)


def _chrome_major_version() -> str | None:
    """Major version of the installed Chrome (from Info.plist, no spawn)."""
    import plistlib

    try:
        with open("/Applications/Google Chrome.app/Contents/Info.plist", "rb") as fh:
            version = plistlib.load(fh).get("CFBundleShortVersionString", "")
    except OSError:
        return None
    return version.split(".")[0] if version else None


def _chromedriver_platform() -> str | None:
    """chrome-for-testing platform tag for this OS/arch, or None if unknown."""
    if sys.platform != "darwin":
        return None
    if platform.machine() in ("arm64", "aarch64"):
        return "mac-arm64"
    return "mac-x64"


def _chromedriver_download_url(major: str, plat: str) -> str | None:
    """Resolve the chrome-for-testing download URL for a Chrome major version."""
    import json

    url = "https://googlechromelabs.github.io/chrome-for-testing/latest-versions-per-milestone-with-downloads.json"
    try:
        with urllib.request.urlopen(url, timeout=60) as resp:
            data = json.load(resp)
        for entry in data["milestones"][major]["downloads"].get("chromedriver", []):
            if entry["platform"] == plat:
                return entry["url"]
    except Exception:
        logger.debug("could not resolve chromedriver URL for %s/%s", major, plat, exc_info=True)
    return None


def _ensure_chromedriver() -> str | None:
    """Ensure a native-arch chromedriver matching the installed Chrome exists.

    undetected-chromedriver's patcher only knows 'mac-x64' on macOS, which
    cannot run on Apple Silicon ('Bad CPU type in executable'), silently
    forcing the plain-chromedriver fallback. The correct driver is fetched
    from chrome-for-testing and cached next to uc's own data dir.
    """
    major = _chrome_major_version()
    plat = _chromedriver_platform()
    if not major or not plat:
        return None
    cache_dir = os.path.join(os.path.expanduser("~"), "Library", "Application Support", "undetected_chromedriver")
    target = os.path.join(cache_dir, f"chromedriver-{plat}-{major}")
    if os.path.exists(target) and os.access(target, os.X_OK) and _driver_signed(target):
        return target
    url = _chromedriver_download_url(major, plat)
    if not url:
        return None
    import io
    import zipfile

    logger.info("downloading chromedriver %s (%s)", major, plat)
    with urllib.request.urlopen(url, timeout=120) as resp:
        blob = resp.read()
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        name = next(n for n in zf.namelist() if n.endswith("/chromedriver"))
        raw = zf.read(name)
    os.makedirs(cache_dir, exist_ok=True)
    tmp = target + ".tmp"
    with open(tmp, "wb") as fh:
        fh.write(raw)
    os.chmod(tmp, 0o755)
    _patch_and_resign_driver(tmp)
    os.replace(tmp, target)
    logger.info("chromedriver ready at %s", target)
    return target


def _driver_signed(path: str) -> bool:
    """True when the driver passes codesign validation (macOS adhoc signing)."""
    if sys.platform != "darwin":
        return True
    try:
        return (
            subprocess.run(
                ["codesign", "--verify", path],
                check=False,
                capture_output=True,
                timeout=30,
            ).returncode
            == 0
        )
    except (OSError, subprocess.TimeoutExpired):
        return False


def _patch_and_resign_driver(path: str) -> None:
    """Apply uc's marker patch to the driver and restore its code signature.

    undetected-chromedriver skips patching (leaving the binary untouched) when
    it already contains the marker string, and its in-place patch breaks the
    adhoc signature Apple Silicon enforces at load time (the kernel then kills
    the driver with 'CODESIGNING Invalid Page'). Re-signing adhoc after the
    patch keeps the binary loadable.
    """
    marker = b"undetected chromedriver"
    try:
        with open(path, "rb") as fh:
            content = fh.read()
        match = re.search(rb"\{window\.cdc.*?;\}", content)
        if match and marker not in content:
            content = content.replace(
                match[0],
                b'{console.log("undetected chromedriver 1337!")}'.ljust(len(match[0]), b" "),
            )
            with open(path, "wb") as fh:
                fh.write(content)
            logger.info("pre-patched chromedriver at %s", path)
        if sys.platform == "darwin":
            subprocess.run(
                ["codesign", "--force", "--sign", "-", path],
                check=True,
                capture_output=True,
                timeout=120,
            )
    except Exception:
        logger.debug("chromedriver patch/resign failed", exc_info=True)


def quit_driver(driver: WebDriver) -> None:
    """Quit the driver and kill leftover browser processes.

    uc launches Chrome detached and its own quit() may leave the browser
    running (windows close but the app stays in the dock). Leftover Chrome
    processes for this run are identified by their --user-data-dir argument.
    """
    user_data_dir = getattr(driver, "user_data_dir", None)
    try:
        driver.quit()
    except Exception:
        logger.debug("driver quit raised", exc_info=True)
    if user_data_dir:
        try:
            subprocess.run(
                ["pkill", "-f", f"--user-data-dir={user_data_dir}"],
                capture_output=True,
                check=False,
            )
            logger.debug("cleaned up leftover chrome (user-data-dir=%s)", user_data_dir)
        except OSError as exc:
            logger.debug("could not run pkill: %s", exc)


def _create_firefox(headless: bool) -> WebDriver:
    from webdriver_manager.firefox import GeckoDriverManager

    options = FirefoxOptions()
    if headless:
        options.add_argument("--headless")
        options.add_argument("--width=1920")
        options.add_argument("--height=1080")
    service = FirefoxService(GeckoDriverManager().install())
    return FirefoxDriver(service=service, options=options)
