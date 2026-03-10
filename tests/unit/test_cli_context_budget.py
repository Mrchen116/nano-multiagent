from nano_multiagent.apps.coding_cli.render.context_budget import extract_context_budget_metrics


def test_extract_context_budget_metrics_clamps_usage_ratio_above_one() -> None:
    payload = {
        "used_tokens": 47_349,
        "max_tokens": 8_192,
        "usage_ratio": 5.78,
    }

    metrics = extract_context_budget_metrics(payload)

    assert metrics == (47_349, 8_192, 1.0)
