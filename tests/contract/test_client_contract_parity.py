"""Contracts for cross-platform enum generation, exhaustive matching, and parity gates."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import docs_check  # noqa: E402

EXPECTED_ENUM_NAMES = {
    "TaskModeContract",
    "TaskStatusContract",
    "AgentLifecycleDesiredContract",
    "AgentLifecycleObservedContract",
    "CollaborationScopeContract",
    "WorkerRuntimeContract",
    "MessageReceiptStatusContract",
    "UserNotificationKindContract",
}

SWIFT_CONTRACT_CASE_MARKERS = (
    "TaskModeContract",
    "TaskStatusContract",
    "AgentLifecycleDesiredContract",
    "AgentLifecycleObservedContract",
    "CollaborationScopeContract",
    "WorkerRuntimeContract",
    "MessageReceiptStatusContract",
    "UserNotificationKindContract",
    "case .proposed",
    "case .inReview",
    "case .stopUnconfirmed",
    "case .humanMessage",
    "case .workPermission",
)

RUST_CONTRACT_CASE_MARKERS = (
    "TaskModeContract::",
    "TaskStatusContract::",
    "AgentLifecycleDesiredContract::",
    "AgentLifecycleObservedContract::",
    "CollaborationScopeContract::",
    "WorkerRuntimeContract::",
    "MessageReceiptStatusContract::",
    "UserNotificationKindContract::",
)


def extract_brace_blocks(source: str, keyword: str) -> list[tuple[int, str]]:
    """Extract brace-balanced ``switch`` or ``match`` blocks with 1-based start lines."""
    pattern = re.compile(rf"\b{keyword}\b[^{{;\n]*\{{")
    blocks: list[tuple[int, str]] = []
    for match in pattern.finditer(source):
        brace_start = match.end() - 1
        depth = 0
        index = brace_start
        in_string = False
        escape = False
        while index < len(source):
            ch = source[index]
            if in_string:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_string = False
            else:
                if ch == '"':
                    in_string = True
                elif ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        line = source.count("\n", 0, match.start()) + 1
                        blocks.append((line, source[match.start() : index + 1]))
                        break
            index += 1
    return blocks


def find_contract_wildcard_violations(source: str, language: str) -> list[int]:
    """Return 1-based start lines of contract enum switch/match blocks using wildcards."""
    keyword = "switch" if language == "swift" else "match"
    markers = (
        SWIFT_CONTRACT_CASE_MARKERS
        if language == "swift"
        else RUST_CONTRACT_CASE_MARKERS
    )
    wildcard_re = (
        re.compile(r"(?m)^\s*(?:default\s*:|case\s+_\s*:)")
        if language == "swift"
        else re.compile(r"(?m)^\s*_\s*=>")
    )
    violations: list[int] = []
    for line, block in extract_brace_blocks(source, keyword):
        if not any(marker in block for marker in markers):
            continue
        if wildcard_re.search(block):
            violations.append(line)
    return violations


def test_generated_client_contracts_are_fresh_and_complete() -> None:
    """Generated Swift and Rust contracts match @nano/product-contracts without drift."""
    result = subprocess.run(
        ["pnpm", "exec", "tsx", "scripts/generate-client-contracts.ts", "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout

    swift_text = (ROOT / "src/IM/ios/NanoIM/Client/GeneratedContracts.swift").read_text(
        encoding="utf-8"
    )
    rust_text = (ROOT / "apps/desktop/src/generated_contracts.rs").read_text(
        encoding="utf-8"
    )
    for enum_name in EXPECTED_ENUM_NAMES:
        assert f"enum {enum_name}:" in swift_text
        assert f"pub enum {enum_name}" in rust_text


def test_brace_scanner_catches_contract_wildcards_without_local_false_positives() -> (
    None
):
    """Wildcard check flags contract enum defaults while ignoring unrelated switches."""
    swift_sample = """
    func httpLabel(_ status: Int) -> String {
        switch status {
        case 200: return "ok"
        default: return "other"
        }
    }
    func badTaskSwitch(_ status: TaskStatusContract) -> String {
        switch status {
        case .proposed: return "p"
        default: return "oops"
        }
    }
    """
    assert find_contract_wildcard_violations(swift_sample, "swift") == [9]

    rust_sample = """
    fn local_num(x: u32) -> &'static str {
        match x {
            1 => "one",
            _ => "other",
        }
    }
    fn bad_kind(k: UserNotificationKindContract) -> &'static str {
        match k {
            UserNotificationKindContract::Mention => "m",
            _ => "fallback",
        }
    }
    """
    assert find_contract_wildcard_violations(rust_sample, "rust") == [9]


def test_ios_and_desktop_contract_matches_have_no_wildcard_fallbacks() -> None:
    """Consumer switch/match blocks over generated contract enums must be exhaustive."""
    violations: list[str] = []
    for swift_file in sorted((ROOT / "src/IM/ios/NanoIM").rglob("*.swift")):
        if swift_file.name == "GeneratedContracts.swift":
            continue
        lines = find_contract_wildcard_violations(
            swift_file.read_text(encoding="utf-8"), "swift"
        )
        violations.extend(f"{swift_file.relative_to(ROOT)}:{line}" for line in lines)

    for rust_file in sorted((ROOT / "apps/desktop/src").rglob("*.rs")):
        if rust_file.name == "generated_contracts.rs":
            continue
        lines = find_contract_wildcard_violations(
            rust_file.read_text(encoding="utf-8"), "rust"
        )
        violations.extend(f"{rust_file.relative_to(ROOT)}:{line}" for line in lines)

    assert not violations, (
        f"Contract enum switch/match blocks must not use default:/_ =>: {violations}"
    )


def test_shared_golden_vectors_are_symlinked_into_ios_tests() -> None:
    """iOS NanoIMTests bundle symlinks point directly to canonical src/IM/shared vectors."""
    for name in (
        "avatar-test-cases.json",
        "unread-badge-test-cases.json",
        "timeline-divider-test-cases.json",
    ):
        ios_link = ROOT / "src/IM/ios/Tests" / name
        shared_target = ROOT / "src/IM/shared" / name
        assert shared_target.is_file(), f"Missing canonical vector {shared_target}"
        assert ios_link.is_symlink(), f"Expected tracked symlink at {ios_link}"
        assert ios_link.resolve() == shared_target.resolve()


def test_platform_parity_gate_and_docs_matrix_validator(tmp_path: Path) -> None:
    """Bidirectional PR gate self-test and docs_check matrix validator enforce 5 rows."""
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/check_platform_parity.py"), "--self-test"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout

    bad_design = Path("docs/changes/feat-899-missing-ios/design.md")
    _, problems = docs_check.parse_platform_parity_matrix(
        bad_design,
        "# feat-899\n\n## 五端对齐矩阵\n\n"
        "| 平台 | 处置方式 | 理由 |\n|---|---|---|\n"
        "| `Web` | `shared` | ok |\n",
    )
    codes = {problem.code for problem in problems}
    assert "PLATFORM_MATRIX_INCOMPLETE" in codes


def test_node_directory_fsync_is_confined_to_platform_io() -> None:
    """Directory handle sync must stay centralized in apps/node/src/platform-io.ts."""
    offenders = [
        path.relative_to(ROOT).as_posix()
        for path in sorted((ROOT / "apps/node/src").rglob("*.ts"))
        if path.name != "platform-io.ts"
        and "directory.sync()" in path.read_text(encoding="utf-8")
    ]
    assert not offenders, (
        f"Use syncDirectoryIfSupported from platform-io.ts: {offenders}"
    )


def test_web_frontend_avoids_node_bound_product_contracts_root_barrel() -> None:
    """Browser runtime imports must use browser-safe @nano/product-contracts/* subpaths."""
    barrel_value_import = re.compile(
        r"""^\s*import\s+(?!type\b)[\s\S]*?from\s+['"]@nano/product-contracts['"]""",
        re.MULTILINE,
    )
    offenders = [
        path.relative_to(ROOT).as_posix()
        for path in sorted((ROOT / "src/IM/frontend/src").rglob("*.ts*"))
        if barrel_value_import.search(path.read_text(encoding="utf-8"))
    ]
    assert not offenders, (
        "Import browser runtime helpers from @nano/product-contracts/<subpath> so "
        f"Rollup never pulls in node:crypto from root barrel: {offenders}"
    )
