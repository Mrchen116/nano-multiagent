from __future__ import annotations

import json
from pathlib import Path
import shutil

import pytest

from evals.spec_design_alignment.experiments.feat_532_spec_memory import runner


def load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def copied_pilot(tmp_path: Path) -> Path:
    source = runner.EXPERIMENT_ROOT / "pilot/results/h02-pilot-v1"
    artifacts = tmp_path / "artifacts"
    shutil.copytree(source, artifacts)
    return artifacts


def reseal_evidence_manifest(artifacts: Path) -> None:
    runner.write_json(
        artifacts / "evidence-manifest.json", runner.evidence_manifest(artifacts)
    )


@pytest.mark.parametrize(
    ("path", "value"),
    [
        ("final_visible_files", []),
        ("exit_code", 9),
        ("os_sandbox.profile_sha256", "0" * 64),
        ("tools.command_execution_observed", False),
    ],
)
def test_replay_rejects_post_call_attestation_tamper(
    tmp_path: Path, path: str, value: object
) -> None:
    artifacts = copied_pilot(tmp_path)
    context = artifacts / "contexts/candidate-baseline-01"
    actual = load_json(context / "actual.json")
    target = actual
    parts = path.split(".")
    for part in parts[:-1]:
        target = target[part]
    target[parts[-1]] = value
    runner.write_json(context / "actual.json", actual)
    reseal_evidence_manifest(artifacts)

    with pytest.raises(runner.PilotError, match="attestation"):
        runner.replay_pilot(artifacts)


def test_replay_requires_exact_persistent_invocation_chain(tmp_path: Path) -> None:
    artifacts = copied_pilot(tmp_path)
    shutil.rmtree(artifacts / "contexts/candidate-baseline-06")
    reseal_evidence_manifest(artifacts)

    with pytest.raises(runner.PilotError, match="invocation matrix"):
        runner.replay_pilot(artifacts)


def test_replay_binds_evaluation_copy_to_role_output(tmp_path: Path) -> None:
    artifacts = copied_pilot(tmp_path)
    audit_path = artifacts / "evaluation/run-audit-T1.json"
    audit = load_json(audit_path)
    audit["findings"] = [
        {
            "type": "unsupported_material_judgment",
            "severity": "warning",
            "evidence": "forged evaluation-side copy",
            "context_refs": ["O01"],
        }
    ]
    runner.write_json(audit_path, audit)
    reseal_evidence_manifest(artifacts)

    with pytest.raises(runner.PilotError, match="evaluation output drift"):
        runner.replay_pilot(artifacts)


def test_batch_audit_critical_flag_matches_contradictions() -> None:
    batch = {
        "formal_eligible": False,
        "critical_error": False,
        "contradictions": [
            {
                "first_transcript": "T1",
                "second_transcript": "T2",
                "evidence": "substantive contradiction",
            }
        ],
    }

    with pytest.raises(runner.PilotError, match="batch auditor critical flag"):
        runner.validate_batch_audit(batch)


def test_next_scheme_trace_summary_is_recomputed_from_memory_trace() -> None:
    traces = {
        "T1": {"formal_eligible": False, "events": []},
        "T2": {
            "formal_eligible": False,
            "events": [
                {
                    "memory_id": "M01",
                    "state": "used",
                    "affected_behavior": "x",
                    "rationale": "x",
                },
                {
                    "memory_id": "M02",
                    "state": "rejected",
                    "affected_behavior": "x",
                    "rationale": "x",
                },
                {
                    "memory_id": "M03",
                    "state": "overridden",
                    "affected_behavior": "x",
                    "rationale": "x",
                },
            ],
        },
    }
    proposal = {
        "schema_version": "1.0",
        "formal_eligible": False,
        "scheme_id": "next-v1",
        "parent_scheme_id": "direct-load-broad-first-docs-v0",
        "trace_summary": {"loaded": 0, "used": 0, "rejected": 1, "overridden": 1},
        "build_policy": "Prefer reusable principles.",
        "consumption_policy": "Direct-load applicable entries.",
        "delta": ["Rank by cross-document recurrence."],
        "hypothesis": "Less irrelevant context improves alignment.",
        "forbidden_case_specific_atoms": ["H02", "feat-510"],
    }

    with pytest.raises(runner.PilotError, match="trace summary"):
        runner.verify_next_scheme(
            proposal,
            ["H02", "feat-510"],
            runner.summarize_memory_traces(traces),
        )
