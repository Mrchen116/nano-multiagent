#!/usr/bin/env python3
"""Bidirectional 5-platform parity gate for pull requests and change units."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from docs_check import (
    LEGACY_ACTIVE_DESIGN_UNITS,
    PLATFORM_PARITY_ROWS,
    parse_platform_parity_matrix,
)

UNIT_BRANCH_RE = re.compile(
    r"^(?:unit|codex)/(?P<unit_id>(?:feat|bugfix|refactor|perf)-\d+)(?:-.+)?$"
)
EXEMPT_LINE_RE = re.compile(
    r"Platform-Parity-Exempt:\s*(?P<reason>\S.*)$", re.MULTILINE
)

PLATFORM_SURFACE_PREFIXES: dict[str, tuple[str, ...]] = {
    "Web": ("src/IM/frontend/", "src/IM/shared/", "packages/product-contracts/"),
    "Desktop (macOS)": (
        "apps/desktop/",
        ".github/workflows/desktop-candidate.yml",
        "scripts/build-desktop-macos",
    ),
    "Desktop (Windows)": (
        "apps/desktop/",
        "scripts/build-desktop-windows.ps1",
        ".github/workflows/desktop-candidate.yml",
    ),
    "iOS": ("src/IM/ios/",),
    "Node (macOS / Windows / Linux)": ("apps/node/",),
}

CLIENT_PLATFORMS = (
    "Web",
    "Desktop (macOS)",
    "Desktop (Windows)",
    "iOS",
)

SHARED_CLIENT_TRIGGER_PREFIXES = (
    "packages/product-contracts/src/",
    "src/IM/shared/",
    "apps/im-server/src/",
    "src/IM/frontend/src/",
)
NODE_ONLY_CONTRACT_FILES = frozenset(
    {
        "packages/product-contracts/src/node-rpc.ts",
        "packages/product-contracts/src/runtime-rpc.ts",
    }
)


def _matches_any_prefix(path: str, prefixes: tuple[str, ...]) -> bool:
    return any(path == prefix or path.startswith(prefix) for prefix in prefixes)


def _is_docs_only(changed_files: list[str]) -> bool:
    return bool(changed_files) and all(
        path.startswith("docs/") or path.endswith(".md") for path in changed_files
    )


def _find_unit_dir(
    repo_root: Path, head_ref: str, changed_files: list[str]
) -> Path | None:
    unit_id: str | None = None
    branch_match = UNIT_BRANCH_RE.fullmatch(head_ref.strip())
    if branch_match is not None:
        unit_id = branch_match.group("unit_id")

    for scope_dir in (repo_root / "docs/changes", repo_root / "docs/changes/archive"):
        if not scope_dir.is_dir():
            continue
        if unit_id is not None:
            for child in sorted(scope_dir.iterdir()):
                if child.is_dir() and (
                    child.name == unit_id or child.name.startswith(f"{unit_id}-")
                ):
                    return child

    for rel in changed_files:
        parts = Path(rel).parts
        if len(parts) >= 4 and parts[:2] == ("docs", "changes"):
            if parts[2] == "archive" and len(parts) >= 5:
                candidate = repo_root / "docs/changes/archive" / parts[3]
                if candidate.is_dir():
                    return candidate
            elif parts[2] not in {"archive", "retired"}:
                candidate = repo_root / "docs/changes" / parts[2]
                if candidate.is_dir():
                    return candidate
    return None


def _has_explicit_exemption(
    unit_dir: Path | None, pr_body: str, commit_messages: str
) -> bool:
    if EXEMPT_LINE_RE.search(pr_body) or EXEMPT_LINE_RE.search(commit_messages):
        return True
    if unit_dir is not None:
        for name in ("problem.md", "fix.md", "motivation.md"):
            doc = unit_dir / name
            if doc.is_file() and EXEMPT_LINE_RE.search(doc.read_text(encoding="utf-8")):
                return True
    return False


def evaluate_platform_parity(
    repo_root: Path,
    changed_files: list[str],
    *,
    head_ref: str = "",
    pr_body: str = "",
    commit_messages: str = "",
) -> list[str]:
    """Evaluate bidirectional 5-platform symmetry for a set of changed repository paths.

    Args:
        repo_root: Checkout root path.
        changed_files: Normalized POSIX relative paths modified in the change set.
        head_ref: Branch ref (e.g., ``unit/refactor-800-multi-platform-parity``).
        pr_body: Pull request description text, if available.
        commit_messages: Concatenated commit messages in the range, if available.

    Returns:
        List of human-readable violation strings (empty when compliant).
    """
    if not changed_files:
        return []

    errors: list[str] = []
    unit_dir = _find_unit_dir(repo_root, head_ref, changed_files)
    matrix: dict[str, tuple[str, str]] | None = None

    if unit_dir is not None:
        design_path = unit_dir / "design.md"
        is_bugfix_lite = (unit_dir / "fix.md").is_file() or (
            unit_dir / "problem.md"
        ).is_file()
        is_legacy = unit_dir.name in LEGACY_ACTIVE_DESIGN_UNITS
        if design_path.is_file() and not is_legacy and not is_bugfix_lite:
            rel_design = design_path.relative_to(repo_root)
            parsed, problems = parse_platform_parity_matrix(
                rel_design, design_path.read_text(encoding="utf-8")
            )
            if problems:
                errors.extend(problem.render() for problem in problems)
                return errors
            matrix = parsed

    if _is_docs_only(changed_files):
        return errors

    # Direction 1: Any platform declared as `native-sync` in design.md must have real code edits.
    if matrix is not None:
        for platform in PLATFORM_PARITY_ROWS:
            disposition, _ = matrix[platform]
            if disposition != "native-sync":
                continue
            prefixes = PLATFORM_SURFACE_PREFIXES[platform]
            if not any(_matches_any_prefix(path, prefixes) for path in changed_files):
                errors.append(
                    f"[NATIVE_SYNC_MISSING] design.md declares {platform!r} as 'native-sync', "
                    f"but no files under {prefixes} were modified."
                )

    # Direction 2: Shared contracts / shared vectors / im-server / Web UI triggers require
    # every client platform to be either updated in the diff or justified via matrix / exemption.
    triggers = [
        path
        for path in changed_files
        if path not in NODE_ONLY_CONTRACT_FILES
        and _matches_any_prefix(path, SHARED_CLIENT_TRIGGER_PREFIXES)
    ]
    if not triggers:
        return errors

    if _has_explicit_exemption(unit_dir, pr_body, commit_messages):
        return errors

    if unit_dir is not None and unit_dir.name in LEGACY_ACTIVE_DESIGN_UNITS:
        return errors

    for platform in CLIENT_PLATFORMS:
        if matrix is not None:
            disposition, _ = matrix[platform]
            if disposition in {"shared", "platform-exempt"}:
                continue
        if platform == "Web":
            touched = any(path.startswith("src/IM/frontend/") for path in changed_files)
        elif platform in {"Desktop (macOS)", "Desktop (Windows)"}:
            touched = any(path.startswith("apps/desktop/") for path in changed_files)
        else:
            touched = any(path.startswith("src/IM/ios/") for path in changed_files)
        if not touched:
            errors.append(
                f"[CLIENT_PARITY_MISSING] Shared/client surface modified ({triggers[0]}), "
                f"but {platform!r} has neither matching code edits nor a 'shared'/'platform-exempt' "
                "declaration in ## 五端对齐矩阵 (or 'Platform-Parity-Exempt: <reason>')."
            )

    return errors


def _git_changed_files(repo_root: Path, base_ref: str, head_sha: str) -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--name-only", f"{base_ref}...{head_sha}"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _git_commit_messages(repo_root: Path, base_ref: str, head_sha: str) -> str:
    result = subprocess.run(
        ["git", "log", "--format=%B", f"{base_ref}..{head_sha}"],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    return result.stdout


def run_self_test() -> int:
    """Run built-in bidirectional positive and negative gate assertions."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        full_unit = root / "docs/changes/archive/feat-801-sample"
        full_unit.mkdir(parents=True)
        (full_unit / "design.md").write_text(
            "# feat-801\n\n## 五端对齐矩阵\n\n"
            "| 平台 | 处置方式 | 受影响范围与理由 | 下游验证投影 |\n"
            "|---|---|---|---|\n"
            "| `Web` | `native-sync` | Web 更新 | vitest |\n"
            "| `Desktop (macOS)` | `native-sync` | Desktop 更新 | cargo test |\n"
            "| `Desktop (Windows)` | `native-sync` | Desktop 更新 | cargo test |\n"
            "| `iOS` | `native-sync` | iOS 更新 | NanoIMTests |\n"
            "| `Node (macOS / Windows / Linux)` | `platform-exempt` | 无节点改动 | 无 |\n",
            encoding="utf-8",
        )

        # 1. Docs-only stage commit passes even before implementation files land.
        assert (
            evaluate_platform_parity(
                root,
                ["docs/changes/archive/feat-801-sample/design.md"],
                head_ref="unit/feat-801-sample",
            )
            == []
        )

        # 2. Full code PR touching all declared native-sync platforms passes.
        assert (
            evaluate_platform_parity(
                root,
                [
                    "packages/product-contracts/src/chat.ts",
                    "src/IM/frontend/src/chat.tsx",
                    "apps/desktop/src/notifications.rs",
                    "src/IM/ios/NanoIM/Features/Chat/ChatStore.swift",
                ],
                head_ref="unit/feat-801-sample",
            )
            == []
        )

        # 3. Declaring iOS `native-sync` while omitting `src/IM/ios/**` fails (Direction 1).
        missing_ios_sync = evaluate_platform_parity(
            root,
            [
                "src/IM/frontend/src/chat.tsx",
                "apps/desktop/src/notifications.rs",
            ],
            head_ref="unit/feat-801-sample",
        )
        assert any(
            "NATIVE_SYNC_MISSING" in err and "iOS" in err for err in missing_ios_sync
        )

        # 4. Modifying shared contract + iOS without Web/Desktop and without matrix fails (Direction 2).
        missing_web_desktop = evaluate_platform_parity(
            root,
            [
                "packages/product-contracts/src/chat.ts",
                "src/IM/ios/NanoIM/Features/Chat/ChatStore.swift",
            ],
            head_ref="fix/ad-hoc-change",
        )
        assert any("Web" in err for err in missing_web_desktop)
        assert any("Desktop (macOS)" in err for err in missing_web_desktop)

        # 5. Modifying Web UI without touching iOS and without exemption fails (Direction 2).
        web_only_unjustified = evaluate_platform_parity(
            root,
            ["src/IM/frontend/src/features/chat/chat-page.tsx"],
            head_ref="fix/web-tweak",
        )
        assert any("iOS" in err for err in web_only_unjustified)

        # 6. Small non-unit fix with explicit `Platform-Parity-Exempt:` passes.
        assert (
            evaluate_platform_parity(
                root,
                ["src/IM/frontend/src/features/chat/chat-page.tsx"],
                head_ref="fix/web-css-spacing",
                commit_messages="fix: adjust web-only CSS padding\n\nPlatform-Parity-Exempt: Browser-only CSS spacing fix",
            )
            == []
        )

        # 7. Full unit declaring Desktop `shared` and iOS `platform-exempt` passes for Web-only edit.
        web_unit = root / "docs/changes/archive/feat-802-web-layout"
        web_unit.mkdir(parents=True)
        (web_unit / "design.md").write_text(
            "# feat-802\n\n## 五端对齐矩阵\n\n"
            "| 平台 | 处置方式 | 受影响范围与理由 | 下游验证投影 |\n"
            "|---|---|---|---|\n"
            "| `Web` | `native-sync` | 仅宽屏分栏样式 | vitest |\n"
            "| `Desktop (macOS)` | `shared` | 复用主窗口前端包 | 同 Web |\n"
            "| `Desktop (Windows)` | `shared` | 复用主窗口前端包 | 同 Web |\n"
            "| `iOS` | `platform-exempt` | 移动端单栏不适用桌面三栏 | 无 |\n"
            "| `Node (macOS / Windows / Linux)` | `platform-exempt` | 无节点变更 | 无 |\n",
            encoding="utf-8",
        )
        assert (
            evaluate_platform_parity(
                root,
                ["src/IM/frontend/src/features/chat/chat-page.tsx"],
                head_ref="unit/feat-802-web-layout",
            )
            == []
        )

    print("platform parity gate self-test passed (7/7 scenarios).")
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
    )
    parser.add_argument(
        "--base-ref",
        default=os.environ.get("GITHUB_BASE_REF", ""),
        help="Base branch name or git ref (defaults to origin/$GITHUB_BASE_REF or origin/develop).",
    )
    parser.add_argument(
        "--head-ref",
        default=os.environ.get("GITHUB_HEAD_REF", ""),
        help="Head branch name (defaults to GITHUB_HEAD_REF or current branch).",
    )
    parser.add_argument("--head-sha", default="HEAD")
    parser.add_argument("--pr-body", default=os.environ.get("GITHUB_PR_BODY", ""))
    parser.add_argument("--changed-files", nargs="*", default=None)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args(argv)

    if args.self_test:
        return run_self_test()

    repo_root = args.repo_root.resolve()
    head_ref = args.head_ref.strip()
    if not head_ref:
        branch_proc = subprocess.run(
            ["git", "symbolic-ref", "--short", "-q", "HEAD"],
            cwd=repo_root,
            check=False,
            capture_output=True,
            text=True,
        )
        head_ref = branch_proc.stdout.strip()

    base_ref = args.base_ref.strip()
    if base_ref and not base_ref.startswith("origin/") and "/" not in base_ref:
        candidate = f"origin/{base_ref}"
        probe = subprocess.run(
            ["git", "rev-parse", "--verify", "--quiet", candidate],
            cwd=repo_root,
            check=False,
            capture_output=True,
        )
        base_ref = candidate if probe.returncode == 0 else base_ref
    elif not base_ref:
        base_ref = "origin/develop"

    changed_files = (
        args.changed_files
        if args.changed_files is not None
        else _git_changed_files(repo_root, base_ref, args.head_sha)
    )
    commit_messages = (
        ""
        if args.changed_files is not None
        else _git_commit_messages(repo_root, base_ref, args.head_sha)
    )

    errors = evaluate_platform_parity(
        repo_root,
        changed_files,
        head_ref=head_ref,
        pr_body=args.pr_body,
        commit_messages=commit_messages,
    )
    if errors:
        print(
            f"platform parity check failed: {len(errors)} violation(s)", file=sys.stderr
        )
        for err in errors:
            print(f"  {err}", file=sys.stderr)
        return 1

    print(
        f"platform parity check passed: {len(changed_files)} changed file(s) verified against {base_ref}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
