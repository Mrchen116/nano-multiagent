"""Protect task record semantics that do not require HTTP or database fixtures."""

import pytest
from IM.domain.task_graphs import (
    TaskGraphError,
    apply_operations,
    new_node,
    validate_document,
)


def plan():
    def task(key, parent, title, **fields):
        return new_node(
            node_id=key,
            container_id=parent,
            title=title,
            actor="Nano",
            now="now",
            **fields,
        )

    return {
        "schema_version": 1,
        "root_node_id": "root",
        "revision": 1,
        "nodes": [
            task("root", None, "Goal", mode="dag"),
            task("A", "root", "Research", mode="explore"),
            task("B", "root", "Build"),
            task("X", "A", "X", status="done", result="Negative result"),
            task("Y", "A", "Y"),
        ],
        "dependencies": [{"from": "A", "to": "B"}],
    }


def apply(document, operations, note="Recorded from discussion"):
    return apply_operations(
        document, operations, actor="Nano", now="later", change_note=note
    )[0]


def test_short_node_ids_stay_stable_across_batches_and_reordering():
    root = "n1"
    document = {
        "schema_version": 1,
        "root_node_id": root,
        "revision": 1,
        "nodes": [
            new_node(
                node_id=root,
                container_id=None,
                title="Goal",
                mode="dag",
                actor="Nano",
                now="now",
            )
        ],
        "dependencies": [],
    }
    added = apply(
        document,
        [
            {
                "op": "add_task",
                "client_ref": "A",
                "container_id": root,
                "title": "Research",
            },
            {
                "op": "add_task",
                "client_ref": "B",
                "container_id": root,
                "title": "Build",
            },
            {"op": "add_dependency", "from": "@A", "to": "@B"},
        ],
    )
    assert [node["id"] for node in added["nodes"]] == [root, "n2", "n3"]
    updated = apply(
        added,
        [
            {
                "op": "update_task",
                "node_id": "n2",
                "patch": {"title": "Research finished", "status": "done", "order": 10},
            },
            {"op": "update_task", "node_id": root, "patch": {"title": "Existing goal"}},
            {
                "op": "add_task",
                "client_ref": "C",
                "container_id": root,
                "title": "Release",
            },
            {"op": "add_dependency", "from": "n3", "to": "@C"},
        ],
    )
    assert [node["id"] for node in updated["nodes"]] == [root, "n2", "n3", "n4"]
    assert updated["root_node_id"] == root
    assert updated["nodes"][1]["title"] == "Research finished"
    assert updated["nodes"][1]["status"] == "done"
    assert updated["dependencies"] == [
        {"from": "n2", "to": "n3"},
        {"from": "n3", "to": "n4"},
    ]


def test_exploration_source_and_selection_do_not_reparent_or_complete_work():
    document = plan()
    updated = apply(
        document,
        [
            {
                "op": "add_task",
                "client_ref": "Z",
                "container_id": "A",
                "title": "Z",
                "derived_from_id": "X",
                "mode": "dag",
            },
            {
                "op": "add_task",
                "client_ref": "Z1",
                "container_id": "@Z",
                "title": "Validate",
            },
            {
                "op": "select_candidate",
                "scope_id": "A",
                "node_id": "@Z",
                "reason": "Promising",
            },
            {"op": "update_task", "node_id": "A", "patch": {"status": "done"}},
        ],
    )
    by_title = {n["title"]: n for n in updated["nodes"]}
    assert by_title["Z"]["container_id"] == "A"
    assert by_title["Z"]["derived_from_id"] == "X"
    assert by_title["Validate"]["container_id"] == by_title["Z"]["id"]
    assert by_title["Build"]["status"] == by_title["Goal"]["status"] == "todo"
    assert by_title["X"]["result"] == "Negative result"
    with pytest.raises(TaskGraphError, match="change_note"):
        apply(
            updated,
            [{"op": "update_task", "node_id": "A", "patch": {"status": "doing"}}],
            note="",
        )
    reopened = apply(
        updated,
        [
            {
                "op": "update_task",
                "node_id": "A",
                "patch": {"status": "doing", "result": "Need another measurement"},
            }
        ],
    )
    assert next(n for n in reopened["nodes"] if n["id"] == "A")["status"] == "doing"
    with pytest.raises(TaskGraphError, match="non-dropped"):
        apply(
            updated,
            [
                {
                    "op": "update_task",
                    "node_id": by_title["Z"]["id"],
                    "patch": {"status": "dropped"},
                }
            ],
        )
    cleared = apply(
        updated,
        [
            {
                "op": "update_task",
                "node_id": by_title["Z"]["id"],
                "patch": {"status": "dropped"},
            },
            {
                "op": "select_candidate",
                "scope_id": "A",
                "node_id": None,
                "reason": "Try another direction",
            },
        ],
    )
    assert (
        next(n for n in cleared["nodes"] if n["id"] == "A")["selected_candidate_id"]
        is None
    )
    assert document == plan()


@pytest.mark.parametrize(
    "operation",
    [
        {"op": "add_dependency", "from": "X", "to": "B"},
        {"op": "add_dependency", "from": "B", "to": "A"},
        {"op": "set_derivation", "node_id": "X", "derived_from_id": "X"},
        {"op": "select_candidate", "scope_id": "root", "node_id": None},
        {"op": "select_candidate", "scope_id": "A", "node_id": "B"},
        {"op": "update_task", "node_id": "A", "patch": {"mode": "dag"}},
        {"op": "update_task", "node_id": "B", "patch": {"mode": []}},
        {"op": "update_task", "node_id": "B", "patch": {"status": []}},
        {"op": "update_task", "node_id": "B", "patch": {"order": True}},
        {
            "op": "update_task",
            "node_id": "B",
            "patch": {"links": ["javascript:alert(1)"]},
        },
        {"op": "update_task", "node_id": "B", "patch": {"container_id": "A"}},
        {
            "op": "add_task",
            "client_ref": "N",
            "container_id": "@future",
            "title": "Unknown",
        },
    ],
)
def test_invalid_graph_edits_preserve_original(operation):
    original = plan()
    with pytest.raises(TaskGraphError):
        apply(original, [operation])
    assert original == plan()


def test_empty_leaf_can_be_subdivided_and_graph_limits_are_enforced():
    updated = apply(
        plan(),
        [
            {"op": "update_task", "node_id": "B", "patch": {"mode": "dag"}},
            {"op": "add_task", "client_ref": "N", "container_id": "B", "title": "Next"},
        ],
    )
    assert len(updated["nodes"]) == 6
    root = new_node(
        node_id="0",
        container_id=None,
        title="root",
        mode="dag",
        actor="Nano",
        now="now",
    )
    tree = {
        "schema_version": 1,
        "root_node_id": "0",
        "nodes": [root],
        "dependencies": [],
    }
    for index in range(1, 8):
        tree["nodes"].append(
            new_node(
                node_id=str(index),
                container_id=str(index - 1),
                title="Deep",
                mode="dag",
                actor="Nano",
                now="now",
            )
        )
    validate_document(tree)
    tree["nodes"].append(
        new_node(
            node_id="8", container_id="7", title="Too deep", actor="Nano", now="now"
        )
    )
    with pytest.raises(TaskGraphError, match="eight levels"):
        validate_document(tree)
    wide = {
        "schema_version": 1,
        "root_node_id": "0",
        "nodes": [root],
        "dependencies": [],
    }
    for index in range(1, 500):
        wide["nodes"].append(
            new_node(
                node_id=str(index),
                container_id="0",
                title="Child",
                actor="Nano",
                now="now",
            )
        )
    validate_document(wide)
    wide["nodes"].append(
        new_node(
            node_id="500", container_id="0", title="Too many", actor="Nano", now="now"
        )
    )
    with pytest.raises(TaskGraphError, match="500 nodes"):
        validate_document(wide)
