"""Shared helpers for IM integration tests (re-export of tests/im_service/_auth_helpers)."""

from tests.im_service._auth_helpers import (  # noqa: F401
    AuthedUser,
    authorize,
    make_app_client,
    register_and_authorize,
    register_user,
    seed_user_under_owner,
)


def make_authed_client(
    tmp_path, *, username: str = "alice", display_name: str | None = None
):
    """Construct a TestClient, register one user, and authorize the client.

    Tests that only need a single authenticated owner can use this in one line.
    Tests that need a second tenant should reuse the same FastAPI app via a
    second TestClient against ``client.app``.
    """
    client = make_app_client(tmp_path)
    client.__enter__()
    try:
        user = register_user(client, username=username, display_name=display_name)
        authorize(client, user)
    except Exception:
        client.__exit__(None, None, None)
        raise
    return client, user
