"""Human-like mouse movement and typing emulation (anti-bot measure).

The pointer travels from the previous element to the target along a jittered,
easing path instead of teleporting, and text is typed with per-keystroke
delays — fields are only filled once the mouse has arrived.
"""

from __future__ import annotations

import logging
import random
import time

from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.actions import interaction
from selenium.webdriver.common.actions.action_builder import ActionBuilder
from selenium.webdriver.common.actions.pointer_input import PointerInput
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement

logger = logging.getLogger(__name__)

MIN_KEY_DELAY = 0.04
MAX_KEY_DELAY = 0.15


def _element_center(element: WebElement, jitter: int) -> tuple[float, float]:
    rect = element.rect
    return (
        rect["x"] + rect["width"] / 2 + random.uniform(-jitter, jitter),
        rect["y"] + rect["height"] / 2 + random.uniform(-jitter, jitter),
    )


def _viewport_size(browser: WebDriver) -> tuple[int, int]:
    """Current usable viewport in CSS px (inner), so pointer moves stay in bounds.

    Headless windows are small and elements can sit outside the visible area;
    chromedriver rejects any pointer coordinate there with 'move target out of
    bounds'. Falls back to a large default so jitter never trips the boundary.
    """
    try:
        inner = browser.execute_script("return [window.innerWidth, window.innerHeight]")
        if inner and len(inner) == 2 and inner[0] and inner[1]:
            return int(inner[0]), int(inner[1])
    except (WebDriverException, AttributeError):
        logger.debug("could not read inner viewport size", exc_info=True)
    try:
        size = browser.get_window_size()
        width, height = size.get("width"), size.get("height")
        if width and height:
            return int(width), int(height)
    except (WebDriverException, AttributeError):
        logger.debug("could not read window size", exc_info=True)
    return 1920, 1080


def _clamp(x: float, y: float, width: int, height: int) -> tuple[float, float]:
    return min(max(x, 1.0), float(width - 1)), min(max(y, 1.0), float(height - 1))


def human_move(browser: WebDriver, element: WebElement, from_element: WebElement | None = None) -> None:
    """Move the pointer to `element` along a human-like path.

    When `from_element` is given the pointer first walks to that element's
    location and then travels to the target with easing + random jitter.
    Every point is clamped into the current viewport: chromedriver rejects
    coordinates outside it (esp. small headless windows) with
    'move target out of bounds'.
    """
    width, height = _viewport_size(browser)
    tx, ty = _clamp(*_element_center(element, jitter=5), width, height)
    if from_element is None:
        sx, sy = tx + random.uniform(-140, 140), ty + random.uniform(-90, 90)
    else:
        sx, sy = _element_center(from_element, jitter=8)
    sx, sy = _clamp(sx, sy, width, height)

    pointer = PointerInput(interaction.POINTER_MOUSE, "mouse")
    actions = ActionBuilder(browser, mouse=pointer)
    actions.pointer_action.move_to_location(sx, sy)
    steps = random.randint(6, 10)
    for i in range(1, steps + 1):
        f = i / steps
        x = sx + (tx - sx) * f + random.uniform(-12, 12) * (1 - f)
        y = sy + (ty - sy) * f + random.uniform(-8, 8) * (1 - f)
        x, y = _clamp(x, y, width, height)
        actions.pointer_action.move_to_location(x, y)
    actions.pointer_action.pause(random.uniform(0.15, 0.4))
    actions.perform()


def human_click(browser: WebDriver, element: WebElement, from_element: WebElement | None = None) -> None:
    human_move(browser, element, from_element)
    ActionChains(browser).pause(random.uniform(0.05, 0.2)).click(element).perform()
    if random.random() < 0.8:
        _nudge(browser, magnitude=random.uniform(1.0, 5.0))


def _nudge(browser: WebDriver, magnitude: float) -> None:
    """Tiny random pointer move from the current position (hand settling).

    Best-effort: a relative move near a viewport edge may land out of bounds,
    which is ignored rather than allowed to break the surrounding flow.
    """
    pointer = PointerInput(interaction.POINTER_MOUSE, "mouse")
    actions = ActionBuilder(browser, mouse=pointer)
    actions.pointer_action.move_by(random.uniform(-magnitude, magnitude), random.uniform(-magnitude, magnitude))
    actions.pointer_action.pause(random.uniform(0.1, 0.35))
    try:
        actions.perform()
    except WebDriverException:
        logger.debug("pointer nudge moved out of bounds, ignoring")


def human_idle(browser: WebDriver, seconds: float) -> None:
    """Spend `seconds` waiting, with small random mouse micro-movements.

    Keeps the pointer subtly alive during waits (e.g. after clicking login,
    while the page responds) instead of freezing still.
    """
    remaining = seconds
    while remaining > 0.15:
        if random.random() < 0.75:
            _nudge(browser, magnitude=random.uniform(1.5, 7.0))
        chunk = min(remaining, random.uniform(0.25, 1.0))
        time.sleep(chunk)
        remaining -= chunk


def human_type(browser: WebDriver, element: WebElement, text: str, from_element: WebElement | None = None) -> None:
    """Move the mouse to the field, click it, then type with human delays."""
    human_click(browser, element, from_element)
    for ch in text:
        element.send_keys(ch)
        time.sleep(random.uniform(MIN_KEY_DELAY, MAX_KEY_DELAY))
