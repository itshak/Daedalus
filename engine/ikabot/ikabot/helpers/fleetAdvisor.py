"""Shared military advisor reader for standard and verified cookie sessions."""
import json
import re

from ikabot.config import actionRequest


def advisor_data(session, target):
    """Read the existing advisor without implicit reauthentication."""
    if getattr(session, "_daedalus_cookies_only", False) is True:
        # Use the existing protected same-world GET transport; do not
        # reauthenticate, read stored cookies, or switch to legacy POST.
        html = session.get(f"view=militaryAdvisor&currentCityId={target}")
        marker = re.search(r"ajax\.Responder,\s*(?=\[)", html)
        if marker is None:
            raise ValueError("Advisor response unavailable")
        raw, _ = json.JSONDecoder(strict=False).raw_decode(html[marker.end():])
        return raw
    url = ("view=militaryAdvisor&oldView=city&oldBackgroundView=city&backgroundView=city"
           f"&currentCityId={target}&actionRequest={actionRequest}&ajax=1")
    return json.loads(session.post(url, retry_on_failure=False), strict=False)
