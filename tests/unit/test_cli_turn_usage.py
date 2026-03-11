from coding_cli.coding_cli.render.turn_usage import extract_turn_usage_metrics


def test_extract_turn_usage_metrics_returns_none_when_missing_usage() -> None:
    assert extract_turn_usage_metrics({"session_id": "sess_1"}) is None


def test_extract_turn_usage_metrics_accepts_canonical_fields() -> None:
    metrics = extract_turn_usage_metrics(
        {
            "usage": {
                "prompt_tokens": 120,
                "completion_tokens": 35,
                "total_tokens": 155,
            }
        }
    )
    assert metrics == (120, 35, 155)


def test_extract_turn_usage_metrics_falls_back_to_prompt_plus_completion() -> None:
    metrics = extract_turn_usage_metrics(
        {
            "usage": {
                "prompt_tokens": 120,
                "completion_tokens": 35,
            }
        }
    )
    assert metrics == (120, 35, 155)
