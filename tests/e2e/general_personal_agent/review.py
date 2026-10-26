"""Evidence-linked external adjudication and honest repeated-run comparison."""

from __future__ import annotations

import json
from pathlib import Path

from .catalog import catalog, digest, write_json
from .runner import verified_files


def adjudicate(output: Path, review_path: Path) -> dict:
    """Apply an independent verdict only to the exact captured result and evidence.

    Args:
        output: Existing isolated run output directory.
        review_path: External reviewer JSON with assertion-level evidence references.

    Returns:
        A separate adjudicated result; raw observations are never overwritten.
    """
    raw_path = output / "result.json"
    raw = json.loads(raw_path.read_text())
    state = json.loads((output / "state.json").read_text())
    review = json.loads(review_path.read_text())
    if review.get("run_id") != raw["run_id"] or review.get("result_sha256") != digest(
        raw_path
    ):
        raise ValueError("review must bind the exact run and raw result bytes")
    if review.get("method") not in {"human", "independent_review"} or not review.get(
        "reviewer"
    ):
        raise ValueError("independent external reviewer identity and method required")
    if review["reviewer"] == state["manifest"]["personal"]["agent_id"]:
        raise ValueError("evaluated PA cannot grade itself")
    files = verified_files(review)
    by_path = {entry["path"]: entry for entry in files}
    case = catalog()[raw["case_id"]]
    assertions = review.get("assertions", [])
    expected = {
        f"{kind}:{i}"
        for kind in ("expect", "must_not", "review")
        for i in range(len(case[kind]))
    }
    if {row["id"] for row in assertions} != expected or len(assertions) != len(
        expected
    ):
        raise ValueError(
            "review must cover every original expectation, prohibition and adapter check exactly once"
        )
    for assertion in assertions:
        if assertion["verdict"] not in {
            "passed",
            "failed",
            "not_run",
            "blocked",
        } or not assertion.get("reason"):
            raise ValueError("every assertion requires a verdict and reason")
        if not assertion.get("references"):
            raise ValueError("every assertion requires traceable evidence")
        for ref in assertion["references"]:
            if ref.get("path") not in by_path or not ref.get("locator"):
                raise ValueError(
                    "assertion reference must name hashed file and exact locator"
                )
    verdicts = {row["verdict"] for row in assertions}
    status = (
        "failed"
        if "failed" in verdicts
        else "blocked"
        if "blocked" in verdicts
        else "not_run"
        if "not_run" in verdicts
        else "passed"
    )
    if status == "passed":
        if (
            raw["status"] == "failed"
            or not raw.get("execution_complete")
            or raw.get("collection_error")
        ):
            raise ValueError("incomplete or failed execution cannot become a full pass")
        evidence = json.loads((output / "evidence.json").read_text())
        if digest(output / "evidence.json") != raw["evidence"][
            "sha256"
        ] or evidence.get("errors"):
            raise ValueError("missing/changed/incomplete actual trace")
        kinds = {entry.get("kind") for entry in files}
        if not {"model_input", "tool_trace", "user_result"} <= kinds:
            raise ValueError(
                "pass requires actual provider input, tool trace and visible outcome"
            )
    parts = dict(raw["parts"])
    for name, part in review.get("parts", {}).items():
        if name not in parts or part.get("status") not in {
            "passed",
            "failed",
            "blocked",
            "not_run",
        }:
            raise ValueError("unknown part or part status")
        if not part.get("reason") or not part.get("references"):
            raise ValueError(
                "partial/fallback verdict needs its own reason and evidence"
            )
        for ref in part["references"]:
            if ref.get("path") not in by_path or not ref.get("locator"):
                raise ValueError("part evidence must name hashed file and locator")
        parts[name] = part
    if status == "passed" and any(
        parts.get(f"live_{name}", {}).get("status") != "passed"
        for name in case.get("required_live", [])
    ):
        raise ValueError(
            "required live part remains unverified; grade IM fallback separately"
        )
    result = {
        **raw,
        "status": status,
        "evidence_needs_review": status == "not_run",
        "diagnostic": "external evidence adjudication",
        "adjudication": {
            "path": str(review_path.resolve()),
            "sha256": digest(review_path),
        },
    }
    # Disconnected live integrations remain separate from a successful IM fallback.
    result["parts"] = parts
    if "im" not in review.get("parts", {}):
        result["parts"]["im"] = {
            "status": status,
            "diagnostic": "see assertion-level review",
        }
    write_json(output / "adjudicated-result.json", result)
    return result


def comparison(paths: list[Path]) -> dict:
    """Compare repeated labelled runs without treating blocked/not_run as passes."""
    groups = {}
    for root in paths:
        label = json.loads((root / "run-label.json").read_text())["label"]
        state = json.loads((root / "state.json").read_text())
        result_path = root / "adjudicated-result.json"
        if not result_path.exists():
            result_path = root / "result.json"
        result = json.loads(result_path.read_text())
        config = state["config"]
        signature = {
            key: config.get(key)
            for key in (
                "default_model",
                "reasoning_effort",
                "model_fallbacks",
                "tool_allowlist",
                "features",
                "skills",
            )
        }
        signature["approval"] = {
            key: state.get("manifest", {}).get(key)
            for key in ("approval_model", "approval_rules", "approval_effort")
        }
        signature["heartbeat_json"] = config.get("heartbeat_json")
        row = {
            "run_id": result["run_id"],
            "node_id": state["node_id"],
            "status": result["status"],
            "signature": signature,
            "metrics": result.get("metrics"),
            "result": str(result_path.resolve()),
        }
        groups.setdefault(result["case_id"], {}).setdefault(label, []).append(row)
    summary = {}
    for case_id, labels in groups.items():
        flat = [row for rows in labels.values() for row in rows]
        reasons = []
        if set(labels) != {"baseline", "candidate"}:
            reasons.append("both baseline and candidate required")
        if any(len(rows) < 3 for rows in labels.values()):
            reasons.append("at least three independent runs per condition required")
        if len({row["node_id"] for row in flat}) != len(flat) or len(
            {row["run_id"] for row in flat}
        ) != len(flat):
            reasons.append(
                "reused isolated node or run is not an independent repetition"
            )
        if len({json.dumps(row["signature"], sort_keys=True) for row in flat}) > 1:
            reasons.append(
                "model/tool/feature configuration differs; no like-for-like aggregate"
            )
        if any(row["status"] not in {"passed", "failed"} for row in flat):
            reasons.append("unadjudicated, blocked or not_run observations remain")
        summary[case_id] = {
            "comparable": not reasons,
            "reasons": reasons,
            "runs": labels,
            "counts": {
                label: {
                    status: sum(row["status"] == status for row in rows)
                    for status in ("passed", "failed", "blocked", "not_run")
                }
                for label, rows in labels.items()
            },
        }
    return {"format": "nano-pa-comparison-v1", "cases": summary}
