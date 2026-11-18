#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import math
import time
import traceback

from requests import get, post
from requests.exceptions import RequestException

from ikabot.config import *
from ikabot.helpers.dns import getAddress


def getNewBlackBoxToken(session, retries=None, backoff=1.0):
    """Obtain a nonsecret *request* to the public blackbox API with bounded retries.

    Only transient transport failures are retried. A 400/422 parameter rejection
    gets the existing single user-agent-only compatibility fallback. No response
    body, bearer token or browser state is included in public error messages.
    This does not perform a Gameforge login or create an authenticated session.
    """
    if retries is None:
        retries = blackboxTokenRetries
    if type(retries) is not int or not 0 <= retries <= 3:
        raise ValueError("Blackbox API retries must be between 0 and 3")
    if (
        isinstance(backoff, bool) or not isinstance(backoff, (int, float))
        or not math.isfinite(backoff) or not 0 <= backoff <= 5
    ):
        raise ValueError("Blackbox retry backoff is invalid")

    address = getAddress(publicAPIServerDomain) + "/v1/token"
    user_agent = getattr(session, "api_user_agent", None) or session.user_agent
    params = {
        "user_agent": user_agent,
        "locale": session.locale,
        "timezone_id": session.timezone_id,
    }
    for attempt in range(retries + 1):
        try:
            response = get(
                address, params=params, verify=do_ssl_verify, timeout=blackboxTokenTimeout
            )
            if response.status_code in (400, 422):
                response = get(
                    address,
                    params={"user_agent": user_agent},
                    verify=do_ssl_verify,
                    timeout=blackboxTokenTimeout,
                )
        except RequestException as exc:
            if attempt >= retries:
                raise RuntimeError("Blackbox token API is unavailable; manual assistance required") from None
            time.sleep(min(float(backoff) * (2 ** attempt), 5.0))
            continue

        if response.status_code != 200:
            # Do not expose response.text, which can contain credentials or tokens.
            raise RuntimeError(f"Blackbox token API rejected request (HTTP {response.status_code})")
        try:
            payload = response.json()
        except ValueError as exc:
            raise RuntimeError("Blackbox token API returned invalid JSON") from exc
        if (
            not isinstance(payload, str) or not payload or len(payload) > 8192
            or any(c in payload for c in "\r\n\x00")
        ):
            raise RuntimeError("Blackbox token API returned an invalid token payload")
        return "tra:" + payload.removeprefix("tra:")

    raise RuntimeError("Blackbox token API unavailable")



def getPiratesCaptchaSolution(session, image):
    """This function returns the solution of the pirates captcha
    Parameters
    ----------
    session : ikabot.web.session.Session
        Session object
    image : bytes
        the image to be solved

    Returns
    -------
    solution : str
        solution of the captcha
    """
    address = getAddress(publicAPIServerDomain) + "/v1/decaptcha/pirate"
    files = {"image": image}
    response = post(address, files=files, verify=do_ssl_verify, timeout=900)
    assert response.status_code == 200, (
        "API response code is not OK: "
        + str(response.status_code)
        + "\n"
        + response.text
    )
    response = response.json()
    if "status" in response and response["status"] == "error":
        raise Exception(response["message"])
    return response
