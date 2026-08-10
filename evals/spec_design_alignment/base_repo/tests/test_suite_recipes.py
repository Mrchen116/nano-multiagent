from __future__ import annotations

import json
from pathlib import Path


EVALUATION_ROOT = Path(__file__).resolve().parents[2]
RECIPES_ROOT = EVALUATION_ROOT / "base_repo" / "recipes"
EXPERIMENT_ROOT = EVALUATION_ROOT / "experiments" / "feat_397_agent_team"
FRAMEWORK_COMMIT = "adb93d33a2ec5443a647dd367eb67557ac72e199"
FRAMEWORK_TREE = "025b16b8c900c2b40ac23b126f99eda94e280633"
EXPECTED_RECIPES = {
    "H01": "H01-feat-484-A.json",
    "H02": "H02-feat-510-A.json",
    "H03": "H03-feat-501-A.json",
    "H04": "H04-feat-519-A.json",
    "H05": "H05-feat-515-A.json",
    "H07": "H07-refactor-513-A.json",
    "P01": "P01-cross-node-agent-migration-A.json",
    "P02": "P02-agent-runtime-center-A.json",
}
CANONICAL_GIT = {
    "branch": "main",
    "author_name": "Repository Bootstrap",
    "author_email": "repository@invalid",
    "timestamp": "946684800 +0000",
    "message": "initial repository\n",
}
FORBIDDEN_BENCHMARK_ATOMS = {
    "Product@B",
    "baseline cutoff",
    "baseline product world",
    "A_USER",
    "A+USER",
    "arm A",
    "arm B",
    "当前 A 工作流",
}
H01_PROPOSED_CONTROL_PATHS = [
    "ROADMAP.md",
    "TASKS.md",
    "PROGRESS.md",
    "LOGBOOK.md",
    "TASKS",
    "PROGRESS",
    "ACCEPTANCE",
    "docs/brainstorms",
    "docs/IM-user-stream-migration-plan.md",
    "docs/IM前端蓝图.md",
]
LATE_NATIVE_ARCHIVE_LINEAGE_DROPS = {
    "bugfix-493-frontend-npm-audit": ["bugfix-495"],
    "bugfix-505-agent-switch-loading-rail": ["refactor-483"],
    "bugfix-507-agent-prompt-config": ["feat-397"],
    "bugfix-509-group-self-evolution-agent-attribution": ["feat-397"],
    "feat-338-kernel-message-sse": ["feat-336"],
    "feat-421-critical-path-e2e-suite": ["feat-397"],
    "feat-446-skill-view-tool": ["feat-444"],
    "feat-501-cross-channel-session-controls": ["refactor-477"],
    "refactor-480-typed-run-delivery-context": ["refactor-481"],
    "refactor-486-agent-native-repository-knowledge-system": ["feat-444"],
}
EXPECTED_ARCHIVE_LINEAGE_DROPS = {
    "H01": {
        "feat-338-kernel-message-sse": ["feat-336"],
        "feat-421-critical-path-e2e-suite": ["feat-397"],
        "feat-446-skill-view-tool": ["feat-444"],
    },
    "H02": {
        "bugfix-491-shadow-owner-recovery": ["bugfix-497"],
        "bugfix-493-frontend-npm-audit": ["bugfix-495", "bugfix-497"],
        "bugfix-496-feishu-orphan-listener": ["bugfix-497"],
        "bugfix-499-lark-skill-bundle": ["bugfix-497"],
        "bugfix-508-im-command-picker": ["feat-501"],
        "feat-338-kernel-message-sse": ["feat-336"],
        "feat-421-critical-path-e2e-suite": ["feat-397"],
        "feat-446-skill-view-tool": ["feat-444"],
        "refactor-486-agent-native-repository-knowledge-system": ["feat-444"],
    },
    "H03": {
        "bugfix-491-shadow-owner-recovery": ["bugfix-497"],
        "bugfix-493-frontend-npm-audit": ["bugfix-495", "bugfix-497"],
        "bugfix-496-feishu-orphan-listener": ["bugfix-497"],
        "bugfix-499-lark-skill-bundle": ["bugfix-497"],
        "feat-338-kernel-message-sse": ["feat-336"],
        "feat-421-critical-path-e2e-suite": ["feat-397"],
        "feat-446-skill-view-tool": ["feat-444"],
        "refactor-486-agent-native-repository-knowledge-system": ["feat-444"],
    },
    "H04": LATE_NATIVE_ARCHIVE_LINEAGE_DROPS,
    "H05": LATE_NATIVE_ARCHIVE_LINEAGE_DROPS,
    "H07": LATE_NATIVE_ARCHIVE_LINEAGE_DROPS,
    "P01": {
        "bugfix-493-frontend-npm-audit": ["bugfix-495"],
        "bugfix-507-agent-prompt-config": ["feat-397"],
        "bugfix-509-group-self-evolution-agent-attribution": ["feat-397"],
        "bugfix-511-unit-archive-ci-guard": ["feat-503"],
        "feat-338-kernel-message-sse": ["feat-336"],
        "feat-421-critical-path-e2e-suite": ["feat-397"],
        "feat-446-skill-view-tool": ["feat-444"],
        "refactor-486-agent-native-repository-knowledge-system": ["feat-444"],
    },
    "P02": {
        "bugfix-493-frontend-npm-audit": ["bugfix-495"],
        "bugfix-507-agent-prompt-config": ["feat-397"],
        "bugfix-509-group-self-evolution-agent-attribution": ["feat-397"],
        "bugfix-511-unit-archive-ci-guard": ["feat-503"],
        "feat-338-kernel-message-sse": ["feat-336"],
        "feat-421-critical-path-e2e-suite": ["feat-397"],
        "feat-446-skill-view-tool": ["feat-444"],
        "refactor-486-agent-native-repository-knowledge-system": ["feat-444"],
    },
}


def load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_formal_arm_a_recipes_cover_the_registered_suite() -> None:
    dataset = load_json(EVALUATION_ROOT / "dataset.json")
    registered = {entry["case_id"]: entry for entry in dataset["cases"]}

    assert set(registered) == set(EXPECTED_RECIPES)
    assert (
        registered["H02"]["case_ref"]
        == "cases/H02-feat-510-tool-approval-model/case.json"
    )

    for case_id, filename in EXPECTED_RECIPES.items():
        recipe = load_json(RECIPES_ROOT / filename)
        contract = recipe["contract"]

        assert recipe["schema_version"] == "2.0"
        assert recipe["case_id"] == case_id
        assert recipe["arm"]["id"] == "A"
        assert recipe["arm"]["ref"] == FRAMEWORK_COMMIT
        assert (
            recipe["scrub"]["change_unit_policy"]
            == "remove_active_and_retired_keep_completed_archive"
        )
        assert recipe["assertions"]["change_units_absent"] is True
        assert recipe["git"] == CANONICAL_GIT
        assert FORBIDDEN_BENCHMARK_ATOMS <= set(recipe["assertions"]["forbidden_text"])
        assert contract["method_id"] == "counterfactual-latest-base-v1"
        assert (
            contract["truth_formula"]
            == "Code@B + ProductClaims@B + DocsFramework@F + Workflow@W"
        )
        assert (
            contract["clocks"]["documentation_framework"]["commit"] == FRAMEWORK_COMMIT
        )
        assert contract["clocks"]["documentation_framework"]["tree"] == FRAMEWORK_TREE
        assert contract["clocks"]["workflow"]["commit"] == FRAMEWORK_COMMIT
        assert contract["layers"] == [
            "product_world",
            "documentation_world",
            "common_compatibility",
            "arm_bundle",
            "private_controls",
        ]
        assert recipe["seal"]["suite_status"] == "draft_unsealable"

    h01 = load_json(RECIPES_ROOT / EXPECTED_RECIPES["H01"])
    assert h01["docs_projection"]["mode"] == "dp1_counterfactual_latest"
    assert h01["docs_projection"]["product_claim_source"] == "baseline_only"
    assert h01["scrub"]["drop_proposed_control"] == H01_PROPOSED_CONTROL_PATHS
    changes_index = next(
        item
        for item in h01["arm"]["files"]
        if item["destination"] == "docs/changes/README.md"
    )
    assert changes_index["transform"] == {
        "kind": "keep_before_heading",
        "heading": "## Evidence 与本地产物",
        "expected_occurrences": 1,
    }
    assert (
        changes_index["output_sha256"]
        == h01["assertions"]["required_sha256"]["docs/changes/README.md"]
    )
    assert set(H01_PROPOSED_CONTROL_PATHS) <= set(h01["assertions"]["forbidden_paths"])
    assert h01["assertions"]["required_resolved_links"]["docs/changes/README.md"] == [
        "../development/change-workflow.md",
        "../development/change-workflow.md#什么时候不建-unit",
    ]
    assert {
        "## Evidence 与本地产物",
        "docs/development/evidence.md",
        "## 历史迁移",
        "docs/archive/legacy-development-records/README.md",
    } <= set(h01["assertions"]["forbidden_text_by_path"]["docs/changes/README.md"])
    generated = [
        *(item["content"] for item in h01["docs_projection"]["generated_files"]),
        *(item["content"] for item in h01["arm"]["generated_files"]),
    ]
    assert "## 架构红线\n" in generated[-1]
    assert not any(
        atom in content for atom in FORBIDDEN_BENCHMARK_ATOMS for content in generated
    )

    for case_id in ("H02", "H03", "H04", "H05", "H07", "P01", "P02"):
        recipe = load_json(RECIPES_ROOT / EXPECTED_RECIPES[case_id])
        assert "drop_proposed_control" not in recipe["scrub"]
        changes_index = next(
            item
            for item in recipe["arm"]["files"]
            if item["destination"] == "docs/changes/README.md"
        )
        assert "transform" not in changes_index


def test_unfinished_arms_are_explicitly_unsealable() -> None:
    treatment = load_json(EXPERIMENT_ROOT / "suite-treatment-lock.json")

    assert treatment["arms"]["A"]["readiness"] == "ready_materializable"
    assert treatment["arms"]["A_USER"]["readiness"] == "blocked"
    assert treatment["arms"]["A_USER"]["blockers"] == ["frozen_cross_fitted_profile"]
    assert treatment["arms"]["B"]["readiness"] == "blocked"
    assert treatment["arms"]["B"]["blockers"] == [
        "executable_agent_team_bundle",
        "frozen_cross_fitted_profile",
    ]


def test_archive_lineage_scrub_is_suite_wide_and_task_blind() -> None:
    for case_id, filename in EXPECTED_RECIPES.items():
        recipe = load_json(RECIPES_ROOT / filename)
        policy = recipe["scrub"]["archive_lineage"]
        dispositions = {
            Path(item["path"]).name: item["referenced_noncompleted_unit_ids"]
            for item in policy["drop_units"]
        }

        assert policy["policy"] == "drop_noncompleted_cross_references_v1"
        assert dispositions == EXPECTED_ARCHIVE_LINEAGE_DROPS[case_id]
        assert {item["path"] for item in policy["drop_units"]} <= set(
            recipe["assertions"]["forbidden_paths"]
        )
        assert (
            "docs/changes/feat-397-spec-design-agent-team"
            in recipe["assertions"]["forbidden_paths"]
        )
        assert "feat-397" in recipe["assertions"]["forbidden_text"]


def test_protocol_uses_canonical_main_and_formal_h02_contract() -> None:
    protocol = (EXPERIMENT_ROOT / "protocol.md").read_text(encoding="utf-8")

    assert "refs/heads/evaluation" not in protocol
    assert "refs/heads/main" in protocol
    assert "H02 的 portfolio" not in protocol
    assert "H02 的 after-output" not in protocol
    assert "D06 未获答" not in protocol
    assert "activated D11" not in protocol
    assert "H02 是正式 single-unit historical regression" in protocol
    assert "H02 以 `gate2_complete` 进入 S4" in protocol
