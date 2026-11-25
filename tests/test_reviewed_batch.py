"""Independent review checks must precede every dispatch."""
import pytest

from daedalus.operation_previews import OperationPreviews, PreviewUnavailable
from daedalus.reviewed_batch import dispatch_reviewed_batch, validated_batch_entries

ENTRIES = [
    {"account_id": a, "task": t, "preview_id": k * 43}
    for a, t, k in [("alpha", "constructionList", "a"), ("beta", "donate", "b"),
                    ("gamma", "sendResources", "c")]
]


class Client:
    def __init__(self, blocked=None, fail_at=None):
        self.blocked = blocked or []
        self.fail_at = fail_at
        self.calls = []

    def reviewed_batch_check(self, rows):
        assert rows == ENTRIES
        self.calls.append("check")
        return {"account_ids": [r["account_id"] for r in rows], "blocked": self.blocked}

    def start_reviewed_task(self, account, task, ticket, rid):
        self.calls.append((account, task, ticket, rid))
        return {"account_id": account, "task": task, "request_id": rid,
                "status": "unknown" if account == self.fail_at else "started"}


def test_blocked_account_prevents_any_start():
    client = Client(blocked=[{"account_id": "beta", "reason": "review_unavailable"}])
    result = dispatch_reviewed_batch(client, ENTRIES)
    assert result["blocked"] == client.blocked
    assert not result["submitted"] and result["halted"] is None
    assert client.calls == ["check"]


def test_each_account_has_independent_ticket_and_request():
    client = Client()
    result = dispatch_reviewed_batch(client, ENTRIES)
    assert len(result["submitted"]) == 3 and result["halted"] is None
    assert [call[:3] for call in client.calls[1:]] == [
        (r["account_id"], r["task"], r["preview_id"]) for r in ENTRIES]
    assert len({call[3] for call in client.calls[1:]}) == 3


def test_uncertain_receipt_halts_without_retry():
    client = Client(fail_at="beta")
    result = dispatch_reviewed_batch(client, ENTRIES)
    assert [r["account_id"] for r in result["submitted"]] == ["alpha"]
    assert result["halted"]["account_id"] == "beta"
    assert len(client.calls) == 3


@pytest.mark.parametrize("rows", [[], [ENTRIES[0]] * 2, [ENTRIES[0], {**ENTRIES[1],
    "preview_id": ENTRIES[0]["preview_id"]}], [{**ENTRIES[0], "task": "developer"}]])
def test_invalid_batches_rejected(rows):
    with pytest.raises(ValueError):
        validated_batch_entries(rows)


def test_check_is_read_only_scoped_and_expires():
    now = [100.0]
    tickets = OperationPreviews(ttl=10, clock=lambda: now[0])
    key = tickets.issue("alpha", "donate", {})
    tickets.check_unused(key, "alpha", "donate")
    tickets.check_unused(key, "alpha", "donate")
    with pytest.raises(PreviewUnavailable):
        tickets.check_unused(key, "beta", "donate")
    tickets.claim(key, "alpha", "donate", "request")
    with pytest.raises(PreviewUnavailable):
        tickets.check_unused(key, "alpha", "donate")
    key = tickets.issue("alpha", "donate", {})
    now[0] += 10
    with pytest.raises(PreviewUnavailable):
        tickets.check_unused(key, "alpha", "donate")
