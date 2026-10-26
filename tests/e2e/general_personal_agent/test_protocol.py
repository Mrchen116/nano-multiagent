"""Protect the evaluation protocol from manufacturing success or leaking scope."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from .catalog import catalog, digest, select, write_json
from .evidence import timeline, turns
from .review import adjudicate, comparison
from .runner import validate_manifest, verified_files


def test_every_scenario_has_explicit_executable_mapping():
    cases = catalog()
    assert len(cases) == 58
    assert set(select("smoke")) <= cases.keys()
    assert len(cases["M08"]["steps"][0]["text"]) > 3575
    assert cases["P05"]["enable_heartbeat"] is True
    assert not cases["P03"].get("enable_heartbeat", False)
    assert cases["S03"]["steps"][0]["op"] == "checkpoint"
    with pytest.raises(ValueError):
        select("M01,M01")


@pytest.mark.parametrize(
    "url,node",
    [
        ("http://127.0.0.1:8011", "wt-example"),
        ("https://public.example:18000", "wt-example"),
        ("http://127.0.0.1:18000", "production"),
    ],
)
def test_reject_nonisolated_manifest(tmp_path, url, node):
    path = tmp_path / "manifest.json"
    write_json(path, {"im_url": url, "node_id": node, "personal": {"agent_id": "pa"}})
    with pytest.raises(ValueError):
        validate_manifest(path)


def test_changed_checkpoint_evidence_is_rejected(tmp_path):
    path = tmp_path / "native-event.json"
    path.write_text("actual event")
    receipt = {"files": [{"path": str(path), "sha256": digest(path)}]}
    verified_files(receipt)
    path.write_text("changed")
    with pytest.raises(ValueError):
        verified_files(receipt)


class Response:
    def __init__(self, value):
        self.value = value

    def raise_for_status(self):
        return None

    def json(self):
        return self.value


class Client:
    _auth_headers = {}

    def __init__(self, responses):
        self.responses, self.paths = iter(responses), []
        self._http = self

    def get(self, path, **kwargs):
        self.paths.append((path, kwargs["params"]))
        return Response(next(self.responses))


def test_work_capture_follows_turn_and_item_pages():
    client = Client(
        [
            {
                "turns": [
                    {
                        "session_id": "s",
                        "turn_id": "t1",
                        "items": [],
                        "next_items_cursor": 1,
                    }
                ],
                "next_cursor": "t1",
            },
            {
                "turns": [{"session_id": "s", "turn_id": "t0", "items": []}],
                "next_cursor": None,
            },
            {
                "items": [
                    {
                        "kind": "tool",
                        "payload": {"name": "memory", "detail": {"revision": 2}},
                    }
                ],
                "next_cursor": None,
            },
        ]
    )
    result = turns(client, "/im/v1/agents/pa/work")
    assert len(result["turns"]) == 2
    assert result["turns"][0]["items"][0]["payload"]["detail"]["revision"] == 2
    assert client.paths[-1][0].endswith("/sessions/s/turns/t1/items")


def test_timeline_preserves_order_across_pages():
    client = Client(
        [
            {"items": [{"id": "new"}], "next_before_message_id": "new"},
            {"items": [{"id": "old"}], "next_before_message_id": None},
        ]
    )
    assert timeline(client, "c") == [{"id": "old"}, {"id": "new"}]


def prepare_review(tmp_path, complete=True):
    case = catalog()["M01"]
    write_json(tmp_path / "state.json", {"manifest": {"personal": {"agent_id": "pa"}}})
    write_json(tmp_path / "evidence.json", {"errors": []})
    raw = {
        "case_id": "M01",
        "run_id": "run",
        "status": "not_run",
        "execution_complete": complete,
        "evidence": {"sha256": digest(tmp_path / "evidence.json")},
        "parts": {"im": {"status": "not_run"}},
    }
    write_json(tmp_path / "result.json", raw)
    trace = tmp_path / "independent-provider-capture.json"
    trace.write_text('{"request": "actual input"}')
    review = {
        "run_id": "run",
        "result_sha256": digest(tmp_path / "result.json"),
        "method": "human",
        "reviewer": "independent-human",
        "files": [
            {"path": str(trace), "sha256": digest(trace), "kind": kind}
            for kind in ("model_input", "tool_trace", "user_result")
        ],
        "assertions": [
            {
                "id": f"{kind}:{i}",
                "verdict": "passed",
                "reason": text,
                "references": [{"path": str(trace), "locator": "/request"}],
            }
            for kind in ("expect", "must_not", "review")
            for i, text in enumerate(case[kind])
        ],
    }
    write_json(tmp_path / "review.json", review)
    return review


def test_incomplete_checkpoint_run_cannot_become_pass(tmp_path):
    prepare_review(tmp_path, complete=False)
    with pytest.raises(ValueError, match="incomplete"):
        adjudicate(tmp_path, tmp_path / "review.json")


def test_self_grade_or_missing_assertion_cannot_pass(tmp_path):
    review = prepare_review(tmp_path)
    review["reviewer"] = "pa"
    write_json(tmp_path / "review.json", review)
    with pytest.raises(ValueError, match="grade itself"):
        adjudicate(tmp_path, tmp_path / "review.json")
    review["reviewer"] = "independent"
    review["assertions"].pop()
    write_json(tmp_path / "review.json", review)
    with pytest.raises(ValueError, match="every original"):
        adjudicate(tmp_path, tmp_path / "review.json")


def test_adjudication_keeps_raw_observation_immutable(tmp_path):
    prepare_review(tmp_path)
    old = (tmp_path / "result.json").read_bytes()
    assert adjudicate(tmp_path, tmp_path / "review.json")["status"] == "passed"
    assert (tmp_path / "result.json").read_bytes() == old


def test_comparison_rejects_reused_nodes_and_unreviewed_results(tmp_path):
    roots = []
    for label in ("baseline", "candidate"):
        for repeat in range(3):
            root = tmp_path / f"{label}-{repeat}"
            roots.append(root)
            write_json(root / "run-label.json", {"label": label})
            write_json(root / "state.json", {"config": {}, "node_id": "same-node"})
            write_json(
                root / "result.json",
                {"case_id": "M01", "run_id": root.name, "status": "not_run"},
            )
    row = comparison(roots)["cases"]["M01"]
    assert not row["comparable"]
    assert any("reused" in reason for reason in row["reasons"])
    assert row["counts"]["baseline"]["passed"] == 0


def test_observation_waits_for_real_root_and_child_completion_without_requiring_a_reply(
    monkeypatch,
):
    from . import runner

    run = runner.Run.__new__(runner.Run)
    run.client, run.agent, run.timeout = object(), "pa", 60
    clock = [0]
    monkeypatch.setattr(runner.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(runner.time, "time", lambda: clock[0])
    monkeypatch.setattr(
        runner.time, "sleep", lambda seconds: clock.__setitem__(0, clock[0] + seconds)
    )

    def get(_client, path, **_kwargs):
        if path.endswith("/turns"):
            return {"turns": [{"status": "running" if clock[0] < 26 else "completed"}]}
        return {
            "main_execution": "running" if clock[0] < 22 else "idle",
            "revision": min(clock[0], 27),
            "other_executions": [{"session_id": "child"}],
        }

    monkeypatch.setattr(runner, "get", get)
    result = run.step({"op": "observe", "seconds": 20}, 0)
    assert result["settled"]["at"] >= 32
    assert result["settled"]["work"]["main_execution"] == "idle"
