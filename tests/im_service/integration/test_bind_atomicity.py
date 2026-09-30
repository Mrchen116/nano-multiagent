"""Concurrent local device handoffs serialize their expected owner and epoch."""

from concurrent.futures import ThreadPoolExecutor
from fastapi.testclient import TestClient
from IM.infra.device_binding import DeviceBindingStore
from .conftest import authorize, make_app_client, register_user
from tests.im_service.device_binding_helpers import prepare_binding


def test_two_prepared_recipients_cannot_both_commit(tmp_path):
    with make_app_client(tmp_path) as client:
        alice = register_user(client, username="alice")
        bob = register_user(client, username="bob")
        authorize(client, alice)
        first = prepare_binding(client, tmp_path, node_id="node-race")
        authorize(client, bob)
        second = prepare_binding(client, tmp_path, node_id="node-race")
        from pathlib import Path

        db = Path(
            client.app.state.connection.execute("PRAGMA database_list").fetchone()[
                "file"
            ]
        )

        def commit(payload):
            try:
                return DeviceBindingStore(db).commit(**payload)["state"]
            except ValueError:
                return "rejected"

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(commit, (first, second)))
        assert sorted(results) == ["committed", "rejected"]
        owner = client.app.state.connection.execute(
            "SELECT owner_id FROM nodes WHERE node_id='node-race'"
        ).fetchone()[0]
        assert owner in (alice.owner_id, bob.owner_id)
