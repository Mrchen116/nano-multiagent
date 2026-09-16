import pytest

from IM.app import create_app


@pytest.mark.parametrize(
    "value",
    [
        "",
        "worker.example",
        "ftp://worker.example",
        "http://user:pass@worker.example",
        "https://worker.example?q=x",
        "https://worker.example#x",
    ],
)
def test_public_url_rejects_missing_or_ambiguous_entry(value):
    with pytest.raises(ValueError, match="IM_PUBLIC_URL"):
        create_app(public_url=value)


def test_public_url_is_required_when_environment_is_absent(monkeypatch):
    monkeypatch.delenv("IM_PUBLIC_URL", raising=False)
    with pytest.raises(ValueError, match="IM_PUBLIC_URL"):
        create_app()


def test_public_url_accepts_path_prefix(tmp_path):
    app = create_app(
        public_url="https://chat.example/app", db_path=tmp_path / "im.sqlite3"
    )
    assert app is not None
