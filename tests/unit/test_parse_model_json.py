"""parse_model_json handles string, fenced-string, AND already-parsed dict.

Cloudflare Workers AI's OpenAI-compatible endpoint returns `message.content`
as an already-decoded JSON object (a dict), not a JSON string like Groq/OpenAI.
The parser must accept both without crashing on `.strip()`.
"""
from __future__ import annotations

from prooflens.vision.schema import parse_model_json


def test_parses_plain_json_string():
    assert parse_model_json('{"a": 1, "b": "x"}') == {"a": 1, "b": "x"}


def test_parses_fenced_json_string():
    assert parse_model_json('```json\n{"a": 1}\n```') == {"a": 1}


def test_passes_through_already_parsed_dict():
    # Cloudflare returns message.content already decoded as a dict.
    assert parse_model_json({"plausibility": 80, "reason": "ok"}) == {
        "plausibility": 80,
        "reason": "ok",
    }
