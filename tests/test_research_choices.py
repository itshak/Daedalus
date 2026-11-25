"""Account-bound study menu projection and worker revalidation."""
from unittest.mock import Mock

import pytest
from ikabot.function import research

from daedalus.research_choices import validate_studies, validate_study_choice


def advisor(name="Navigation"):
    return {
        "js_researchAdvisorProgressTxt0": "available",
        "js_researchAdvisorNextResearchName0": name,
        "js_researchAdvisorChangeResearchType0": {"ajaxrequest": "view=researchAdvisor&type=seafaring"},
        "js_researchAdvisorNextResearchName1": "Not available",
        "js_researchAdvisorChangeResearchType1": {"ajaxrequest": "view=researchAdvisor&type=military"},
        "unrelated": "ignored",
    }


def test_projection_does_not_expose_raw_advisor_requests():
    rows = research.native_study_choices(advisor())
    assert rows == [{"index": 0, "name": "Navigation", "research_type": "seafaring"}]
    assert validate_studies(rows) == rows
    with pytest.raises(ValueError):
        validate_studies(rows + rows)
    with pytest.raises(ValueError):
        validate_study_choice({**rows[0], "url": "arbitrary"})
    with pytest.raises(ValueError):
        research.native_study_choices(advisor("<script>"))
    assert research.native_study_choices({}) == []


def test_study_checks_fresh_availability_and_never_retries(monkeypatch):
    session = Mock()
    choice = research.native_study_choices(advisor())[0]
    fresh = Mock(return_value=advisor())
    monkeypatch.setattr(research, "get_studies", fresh)
    monkeypatch.setattr(research, "getCity", lambda _: {"id": "111"})
    assert research.prepare_research(session, study_choice=choice) == {"study_choice": choice}
    session.post.assert_not_called()
    with pytest.raises(ValueError, match="separately"):
        research.prepare_research(session, study_choice=choice, qty=1)
    fresh.return_value = advisor("Different next study")
    with pytest.raises(ValueError, match="changed"):
        research.do_it.__wrapped__(session, study_choice=choice)
    session.post.assert_not_called()
    fresh.return_value = advisor()
    research.do_it.__wrapped__(session, study_choice=choice)
    session.post.assert_called_once()
    assert session.post.call_args.kwargs == {"retry_on_failure": False}
    assert "function=doResearch" in session.post.call_args.args[0]
