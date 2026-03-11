# M114 零-import 边界与 profile 口径收口

## Baseline
- Gate: `cd /Users/czj/Repos/nano-multiagent && python -m pytest tests/unit/test_product_profiles.py tests/contract/test_cli_http_only_contract.py -q 2>&1 | tail -80`
- Worktree Gate: `python -m pytest /Users/czj/Repos/nano-multiagent/.worktrees/M114/tests/unit/test_product_profiles.py /Users/czj/Repos/nano-multiagent/.worktrees/M114/tests/contract/test_cli_http_only_contract.py -q`
- Result: 16 passed, 1 failed
- Baseline failure:
  - `tests/unit/test_product_profiles.py::test_personal_assistant_package_exports_default_modules`
  - 现状 `src/agent/products/personal_assistant/toolsets.py` 仍把 `send_message` 放在默认工具集中，和既有产品画像口径漂移。
- Notes:
  - `src/coding_cli/client.py` 仍直接 `from agent.platform.sdk.client import ...`，与 `SPEC.md` §5 “四个包之间无 Python import 依赖” 冲突。
  - `COMMENTING_GUIDE.md` 已确认遵守：public API 写契约型 docstring，注释只解释意图/边界/代价。
  - `LOGBOOK.md` 相关约束：源码字符串边界门禁要避免把跨层包名写回源码；实现/测试/文档必须同口径。

## Roadpoints

### R1 收口 personal_assistant 默认工具与 profile 契约
- Status: DONE
- Acceptance:
  - `PERSONAL_ASSISTANT_PROFILE.default_tool_ids` 与 `src/agent/products/personal_assistant/toolsets.py` 一致。
  - 默认工具集为保守集，不再默认启用 `send_message`。
  - 若 `send_message` 仍被产品识别，其口径应明确为 optional，而非 default。
  - `tests/unit/test_product_profiles.py` 对默认/可选工具的断言与实现一致。
- Tests Plan:
  - unit: 选。直接锁定 `personal_assistant` 默认工具与 optional 工具契约，定位最快。
  - contract: 不单开；本 Roadpoint 以 profile/package surface 为主，contract 由 R2 统一覆盖架构边界。
  - integration: 不选。bootstrap/HTTP 现有产品测试已覆盖更长链路，本次只收默认值口径。
  - e2e: 不选。本里程碑不涉及入口行为变化。
- Expected Tests:
  - `tests/unit/test_product_profiles.py::test_personal_assistant_package_exports_default_modules`
  - 如需要，补一条 `optional_tool_ids` 断言到同文件。
- DoD:
  - Gate 全绿
  - R1 完成 C1/C2/C3
  - `PROGRESS/M114-零-import边界与profile口径收口.md` 记录决策、证据、提交 hash

### R2 收口 coding_cli ↔ agent 零-import 边界，并把 SPEC §5 验收规则落成自动化断言
- Status: DONE
- Acceptance:
  - `src/coding_cli/client.py` 不再直接 import `agent.*`。
  - `src/coding_cli/**` 与 `src/personal_assistant/**` 对其它顶层包的允许边界明确，且有自动化断言。
  - `SPEC.md` §5 明确“允许边界 + 自动化验收口径”，不再只停留在口号。
  - `tests/contract/test_cli_http_only_contract.py` 能同时验证 CLI HTTP-only 边界与多产品零-import 边界。
  - 既有 CLI HTTP client 行为契约不回退。
- Tests Plan:
  - unit: 选。更新 `coding_cli` surface 断言，保证应用层入口稳定但不再绑定 `agent.platform.sdk.client` 身份。
  - contract: 选。扫描顶层包 import 边界，并断言 `SPEC.md` §5 验收文案存在。
  - integration: 不选。HTTP client 运行链路已由现有 integration 覆盖，本次 gate 聚焦边界契约。
  - e2e: 不选。无真实入口语义变化。
- Expected Tests:
  - `tests/contract/test_cli_http_only_contract.py`
  - `tests/unit/test_apps_coding_cli_location.py`
  - Gate: `tests/unit/test_product_profiles.py` + `tests/contract/test_cli_http_only_contract.py`
- DoD:
  - Gate 全绿
  - R2 完成 C1/C2/C3
  - `PROGRESS/M114-零-import边界与profile口径收口.md` 写清验收规则、回滚点、提交 hash
