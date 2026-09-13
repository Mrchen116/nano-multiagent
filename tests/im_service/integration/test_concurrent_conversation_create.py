"""Concurrent HTTP creates keep each conversation and its participants intact."""

from concurrent.futures import ThreadPoolExecutor

import pytest

from .conftest import authorize, make_app_client, register_user


@pytest.mark.parametrize(("kind", "expected_count"), [("group", 24), ("direct", 1)])
def test_concurrent_conversation_creates_commit_complete_membership(
    tmp_path, kind, expected_count
) -> None:
    with make_app_client(tmp_path) as client:
        alice = register_user(client, username="alice")
        bob = register_user(client, username="bob")
        authorize(client, alice)

        def create(index):
            return client.post(
                "/im/v1/conversations",
                json={
                    "type": kind,
                    "title": f"Concurrent {index}",
                    "participant_ids": [alice.id, bob.id],
                },
            )

        with ThreadPoolExecutor(max_workers=8) as pool:
            responses = list(pool.map(create, range(24)))
        assert [r.status_code for r in responses] == [201] * 24
        ids = {r.json()["id"] for r in responses}
        assert len(ids) == expected_count
        for conversation_id in ids:
            response = client.get(f"/im/v1/conversations/{conversation_id}")
            assert response.status_code == 200
            assert len(response.json()["participants"]) == 2
