"""OpenRouter usage parsing — cache/reasoning counts live in *_tokens_details."""
from __future__ import annotations
from services.llm.providers.openrouter import _parse_usage, _parse_llm_response


class TestUsageParsing:
    def test_nested_cached_and_reasoning_tokens(self):
        usage = _parse_usage({"usage": {
            "prompt_tokens": 28000, "completion_tokens": 200, "total_tokens": 28200, "cost": 0.0003,
            "prompt_tokens_details": {"cached_tokens": 27500},
            "completion_tokens_details": {"reasoning_tokens": 120},
        }})
        assert usage.cached_tokens == 27500
        assert usage.reasoning_tokens == 120
        assert usage.cost_usd == 0.0003

    def test_flat_fields_still_work(self):
        usage = _parse_usage({"usage": {"prompt_tokens": 10, "cached_tokens": 4, "reasoning_tokens": 2}})
        assert usage.cached_tokens == 4
        assert usage.reasoning_tokens == 2

    def test_missing_usage_and_null_details(self):
        assert _parse_usage({}).cached_tokens == 0
        usage = _parse_usage({"usage": {"prompt_tokens_details": None, "completion_tokens_details": None, "cost": None}})
        assert usage.cached_tokens == 0 and usage.reasoning_tokens == 0 and usage.cost_usd == 0.0

    def test_response_model_defaults_empty(self):
        resp = _parse_llm_response({"choices": [{"message": {"content": "hi"}, "finish_reason": "stop"}]})
        assert resp.model == ""
