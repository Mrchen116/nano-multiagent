# M114 零-import 边界与 profile 口径收口

## Milestone 摘要
- Milestone: M114 / 多产品零-import 边界与 profile 验收口径收口
- Goal: 收敛 `SPEC.md` §5 的跨包依赖边界，并统一 `personal_assistant` 默认工具的实现、测试、文档口径。
- Gate: `cd /Users/czj/Repos/nano-multiagent && python -m pytest tests/unit/test_product_profiles.py tests/contract/test_cli_http_only_contract.py -q 2>&1 | tail -80`
- Worktree Gate: `python -m pytest /Users/czj/Repos/nano-multiagent/.worktrees/M114/tests/unit/test_product_profiles.py /Users/czj/Repos/nano-multiagent/.worktrees/M114/tests/contract/test_cli_http_only_contract.py -q`
- Scope: 边界相关代码、profile 装配、相关 tests 与必要 `SPEC.md`/文档
- Hard guards:
  - 不改 `ROADMAP.md`
  - 不手改 `data/dev-tasks.json`
  - 不做为测试而生的无意义 shim
  - 实现/测试/文档必须同口径

## Baseline
- `python -m pytest /Users/czj/Repos/nano-multiagent/.worktrees/M114/tests/unit/test_product_profiles.py /Users/czj/Repos/nano-multiagent/.worktrees/M114/tests/contract/test_cli_http_only_contract.py -q`
- 结果：`16 passed, 1 failed`
- 范围内失败：`tests/unit/test_product_profiles.py::test_personal_assistant_package_exports_default_modules`
- 原因：`src/agent/products/personal_assistant/toolsets.py` 仍把 `send_message` 放入默认工具集，和既有 profile 口径漂移。

## Roadpoints

### R1 收口 personal_assistant 默认工具与 profile 契约
- Context: `tests/unit/test_product_profiles.py` 已先暴露 `personal_assistant` 默认工具口径漂移；继续排查发现 `tests/unit/test_personal_assistant_profile.py`、bootstrap 与 `/v1/capabilities` 集成测试仍把 `send_message` 当默认工具，和更早 M77 任务文档中“默认保守集仅 read/task”的目标态冲突。
- Decision: 把 `src/agent/products/personal_assistant/toolsets.py` 收口为 `DEFAULT_TOOL_IDS=["read","task"]`、`OPTIONAL_TOOL_IDS=["send_message"]`；同步 unit/integration 测试只验证默认暴露 read/task，同时保留 `send_message` 为产品识别的 optional tool。
- Rationale: 这样既满足当前 `SPEC.md`/产品画像的保守默认口径，又不删除产品自有 `send_message` 能力本身，避免为了测试绿直接删实现。
- Evidence:
  - Tests: `python -m pytest /Users/czj/Repos/nano-multiagent/.worktrees/M114/tests/unit/test_product_profiles.py /Users/czj/Repos/nano-multiagent/.worktrees/M114/tests/unit/test_personal_assistant_profile.py /Users/czj/Repos/nano-multiagent/.worktrees/M114/tests/integration/test_personal_assistant_bootstrap_integration.py /Users/czj/Repos/nano-multiagent/.worktrees/M114/tests/integration/test_personal_assistant_server_integration.py -q` → `42 passed`
  - Entry: `bootstrap_product(PERSONAL_ASSISTANT_PROFILE)` 与 `create_app(product_profile=PERSONAL_ASSISTANT_PROFILE)` 默认只暴露 `read/task`，`send_message` 不再进入默认 registry/capabilities。
- Rollback: `da9b574`（R1 红灯测试）
- Commits: C1=`da9b574`, C2=`ccfe080`, C3=`待填`
- Next: R2 收口 `coding_cli` 对 `agent` 的直接 import，并把 SPEC §5 自动化验收落地。

### R2 收口 coding_cli ↔ agent 零-import 边界，并把 SPEC §5 验收规则落成自动化断言
- Context: `src/coding_cli/client.py` 仍直接 import `agent.platform.sdk.client`，导致 `SPEC.md` §5 的“四包零 Python import 依赖”无法判通过；现有 contract test 只检查 CLI 不碰 `agent.runtime`，不足以覆盖顶层包之间的零-import 验收。
- Decision: 将 `coding_cli.client` 改为 package-owned HTTP client 实现，不再引用 `agent` Python 符号；同时把 `tests/contract/test_cli_http_only_contract.py` 扩展为 AST 级扫描 `src/agent/`、`src/coding_cli/`、`src/personal_assistant/`、`src/IM/` 的跨包 import，并要求 `SPEC.md` §5 显式写出自动化验收口径；`tests/unit/test_apps_coding_cli_location.py` 同步改为断言 client surface 属于 `coding_cli.client`。
- Rationale: 直接消除唯一已知越界 import，比在文档里弱化“四包零 import”更符合 exit criteria；AST 扫描也避免了只靠字符串负向断言漏掉未来回流。
- Evidence:
  - Tests: `python -m pytest /Users/czj/Repos/nano-multiagent/.worktrees/M114/tests/unit/test_apps_coding_cli_location.py /Users/czj/Repos/nano-multiagent/.worktrees/M114/tests/contract/test_cli_http_only_contract.py -q` → `12 passed`
  - Tests: `cd /Users/czj/Repos/nano-multiagent/.worktrees/M114 && python -m pytest tests/unit/test_product_profiles.py tests/contract/test_cli_http_only_contract.py -q 2>&1 | tail -80` → `19 passed`
  - Entry: `inspect.getsource(coding_cli.client)` 不再出现 `agent.`；AST 扫描四个顶层包源码时无跨包 import 违规。
- Rollback: `50a627b`（R2 红灯测试）
- Commits: C1=`50a627b`, C2=`2cbb873`, C3=`待填`
- Next: Milestone 已满足 exit criteria，可交回主 agent 做后续集成/状态更新。
