from __future__ import annotations

from prooflens.api.schemas import WebhookPayload
from prooflens.service.ids import normalize_id


def test_normalize_strips_and_uppercases():
    assert normalize_id("  rep-42 ") == "REP-42"
    assert normalize_id("abc") == "ABC"


def test_normalize_blank_and_none_become_none():
    assert normalize_id(None) is None
    assert normalize_id("") is None
    assert normalize_id("   ") is None
    assert normalize_id("\t\n") is None


def test_normalize_is_idempotent():
    once = normalize_id("  Rep-7 ")
    assert normalize_id(once) == once == "REP-7"


def test_webhook_payload_normalizes_rep_id():
    p = WebhookPayload(event_id="e1", opportunity_id="o1", rep_id="  rep-9 ")
    assert p.rep_id == "REP-9"
    p2 = WebhookPayload(event_id="e2", opportunity_id="o2", rep_id="   ")
    assert p2.rep_id is None
