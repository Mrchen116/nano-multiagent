from agent.platform.http_api.auth import extract_bearer_token


def test_extract_bearer_token_accepts_valid_header() -> None:
    assert extract_bearer_token("Bearer abc123") == "abc123"


def test_extract_bearer_token_rejects_invalid_header() -> None:
    assert extract_bearer_token(None) is None
    assert extract_bearer_token("") is None
    assert extract_bearer_token("Basic abc123") is None
    assert extract_bearer_token("Bearer") is None
