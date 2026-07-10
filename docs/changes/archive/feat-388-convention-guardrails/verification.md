# Verification Report: feat-388

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | 9/9 |
| Correctness | 8/9 |
| Coherence | 有偏离 |

No critical issues. 2 warning(s) to consider. Ready for PR (with noted improvements).

---

## Completeness

- Tasks: 9/9 complete（M1 全部 roadpoints R1–R6 均标 DONE）
- Spec 覆盖：
  - R1 产品包只能 import agent.sdk — 有实现（R2 矩阵测试间接覆盖 personal_assistant；coding_cli 有专属函数）
  - R2 四顶层包横向零互相 import — 有实现
  - R3 core 不反向依赖 platform/products — 有实现，xfail 已移除
  - B-1 全仓统一 formatter — 有实现（ruff format 全绿）
  - B-2 通用 correctness — 有实现（ruff check 全绿）
  - 零容忍（存量全清，无 baseline/xfail 永久豁免）— 已满足
  - CI 前后端双 job — 有实现
  - PostToolUse hook — 有实现
  - stop-require-explicit-ok.py 自门控 — 有实现

---

## Correctness

| Requirement / Scenario | 实现位置（file:line） | 测试覆盖 | 状态 |
|---|---|---|---|
| R1 产品包穿透内核被拦（编码循环内） | `.claude/hooks/ruff-guardrail.py:69–86`（边界契约测试在 src/ 修改时触发） | `test_cli_http_only_contract.py::test_cli_only_uses_agent_sdk_not_agent_internals`（仅 coding_cli）+ `test_top_level_packages_keep_zero_import_boundaries`（覆盖 personal_assistant） | covered（见 WARNING-1） |
| R1 产品包穿透内核被拦（远端兜底） | `.github/workflows/ci.yml:29–30`（ruff check + pytest -m "not e2e"） | CI yaml 结构经 review 确认 | covered |
| R1 合法走 agent.sdk 不误报 | `_SIBLING_FORBIDDEN_PREFIXES` 只禁 core/platform/products，不禁 agent.sdk；`test_cli_http_only_contract.py:87–107` | `test_top_level_packages_keep_zero_import_boundaries` | covered |
| R2 顶层包横向互相 import 被拦 | `test_cli_http_only_contract.py:148–160`（`_SIBLING_FORBIDDEN_PREFIXES` 矩阵，4 个包全覆盖） | `test_top_level_packages_keep_zero_import_boundaries`（全绿，2342 passed） | covered |
| R3 core 反向 import 被拦 | `test_core_no_platform_imports.py:28–41`（正向断言，无 xfail） | 同测试函数，1 passed | covered |
| R3 现存反向依赖已消除 | 全仓 ruff check 全绿、pytest 全绿、xfail 已移除 | `test_core_packages_do_not_import_platform_product_or_app_surfaces` | covered |
| B-1 格式不规范被自动规整（编码循环内） | `.claude/hooks/ruff-guardrail.py:43–48`（`ruff format <file>` autofix） | 无独立单测（hook 行为），tasks.md 标"实测验证" | covered（WARNING-2） |
| B-1 格式违规进不了远端 | `.github/workflows/ci.yml:26`（`ruff format --check .`） | CI 结构 review | covered |
| B-2 可自动修的卫生问题被自动修 | `.claude/hooks/ruff-guardrail.py:50–55`（`ruff check --fix` autofix） | 同上，实测验证 | covered（WARNING-2） |
| B-2 不可自动修的被回喂/拦截 | `.claude/hooks/ruff-guardrail.py:57–95`（exit 2 + stderr） | 同上，实测验证 | covered（WARNING-2） |
| 现有代码零违规上线（零容忍） | 全仓 `ruff check .` 全绿 + `ruff format --check .` 全绿 + `pytest -m "not e2e"` 2342 passed | 无 xfail/baseline 残留 | covered |
| CI 前端测试被破坏时 CI 红 | `.github/workflows/ci.yml:32–54`（frontend job，vitest run） | CI yaml 结构 review；无 npm run build | covered |
| 前后端测试全绿才放行 | 两 job 并行，任一红 workflow 红（GitHub Actions 默认行为） | CI yaml 结构确认 | covered |
| 上线时前端测试已全绿（bugfix-390 依赖已兑现） | tasks.md 退出标准已勾选 | 依赖 bugfix-390（PR #71 已并 main） | covered |

---

## Coherence

| design 决策 | 遵守? | 代码证据（file:line） |
|---|---|---|
| D1 双引擎：ruff 负责卫生、pytest 契约负责边界 | 是 | `pyproject.toml:43–47`（ruff select F/B006/E722）；`tests/contract/test_cli_http_only_contract.py`（R1/R2）；`tests/contract/test_core_no_platform_imports.py`（R3） |
| D2 PostToolUse hook + stop-require-explicit-ok.py 自门控 + disableAllHooks: false | 是 | `.claude/settings.json:44–54`（PostToolUse matcher Edit\|Write）；`.claude/settings.json:57`（`"disableAllHooks": false`）；`.claude/hooks/stop-require-explicit-ok.py:26–38`（session_managed 门控） |
| D3 两个并行 job（python + frontend），前端不跑 npm run build | 是 | `.github/workflows/ci.yml`（两 job 无 needs 依赖）；ci.yml:51（注释明确不跑 build） |
| D4 B-2 裁剪集：select F/B006/E722，排 B008 | 是 | `pyproject.toml:46–47`（`select = ["F", "B006", "E722"]`，`ignore = ["B008"]`） |
| D5 固定 ruff 版本，零容忍不留 baseline/xfail | 是 | `pyproject.toml:28`（`ruff==0.15.*`）；全量测试无 xfail 残留 |
| per-file-ignores 各条豁免均有合理依据（非掩盖真违规） | **部分偏离** | 见 WARNING-1 详述 |

---

## Issues

### CRITICAL（提 PR 前必须修）

无。

### WARNING（应该修）

**WARNING-1：R1 对 `personal_assistant` 的专属 CLI 函数覆盖缺失，命名误导**

`test_cli_only_uses_agent_sdk_not_agent_internals` 函数（`tests/contract/test_cli_http_only_contract.py:62`）只调用了 `_collect_cli_agent_internal_imports(package_name="coding_cli")`，没有对 `personal_assistant` 做相同的 R1 专属扫描。`personal_assistant` 的 R1 约束目前由 `test_top_level_packages_keep_zero_import_boundaries`（R2 矩阵测试）的 `_SIBLING_FORBIDDEN_PREFIXES["personal_assistant"]` 间接覆盖——R2 矩阵里恰好也禁止了 `agent.core/platform/products`，因此实际约束有效，但 spec 明确"R1 = 产品包（coding_cli / personal_assistant）只能走 agent.sdk"，语义上应有专属的正向说明。

修复建议：在 `test_cli_only_uses_agent_sdk_not_agent_internals` 中对 `personal_assistant` 也调用 `_collect_cli_agent_internal_imports(package_name="personal_assistant")`，或将函数重命名为 `test_products_only_use_agent_sdk_not_agent_internals` 并循环两个包。文件：`tests/contract/test_cli_http_only_contract.py:62–75`。

**WARNING-2：PostToolUse hook B-1/B-2 autofix 行为缺单元测试**

hook 的 autofix + exit 2 回喂行为（`.claude/hooks/ruff-guardrail.py:43–95`）在 tasks.md 退出标准中标注为"实测验证"（`- [x] PostToolUse hook 实测：…`），但没有任何自动化单元测试覆盖 hook 的 I/O 契约（给定含 F401 文件 → 触发 format/fix 后 exit 0；给定含 `import agent.core` 文件 → exit 2 + stderr 含违规摘要）。若 hook 脚本被修改，该行为将悄然失效。注：`tests/unit/test_background_hook_*.py` 中的 `# noqa: unreachable` 两处（`tests/unit/test_background_hook_fork.py:753`、`tests/unit/test_background_hook_turn_meta.py:252`）为 refactor-372 既存存量，不属于本 unit 问题。

修复建议：在 `tests/unit/` 下新增 `test_ruff_guardrail_hook.py`，用 `subprocess` 或 `tmp_path` + 脚本直调模拟 stdin JSON，覆盖：(1) 给定含 F401 的 `.py` → exit 0 且文件被修复；(2) 给定含 `from agent.core import x` 的 `src/` 文件 → exit 2 且 stderr 包含违规信息；(3) 非 `.py` 或非 `src/tests/` 路径 → exit 0 不处理。

### SUGGESTION（可以修）

**SUGGESTION-1：`test_cli_http_only_contract.py` 中 `import pytest` 未实际使用**

`tests/contract/test_cli_http_only_contract.py:13` import 了 `pytest`，但该文件已移除所有 `@pytest.mark.xfail` 用法，`pytest` 符号在文件中不再被引用。该 dead import 被 `tests/**` 的 F401 豁免静默屏蔽。

修复建议：删除 `tests/contract/test_cli_http_only_contract.py:13` 的 `import pytest` 一行。
