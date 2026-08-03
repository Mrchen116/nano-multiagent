# refactor-489-M5: coding-cli-tests — Tasks

> 对齐: ../design.md 的 refactor-489-M5 行与决策 1

## 目标

保留 CLI 用户入口、公开命令、机器可读接口和 SDK 边界的真实保护；删除只绑定退役 HTTP 架构、历史文件布局、私有实现或一次迁移终态的测试，并把重复覆盖收敛到当前最低 seam。

## 退出标准

- [ ] CLI 无参 REPL、公开斜杠命令、`llm-config get`、`--text` NDJSON、`--resume`、运行中 steer 和非 TTY 输出仍由真实 `run_cli` 入口保护。
- [ ] `coding_cli -> agent.sdk` 边界只由 contract seam 拥有，root unit 不重复扫描历史布局或私有导出。
- [ ] 退役 HTTP、历史文件布局、私有实现、无调用者 helper 和重复迁移测试已删除或合并。
- [ ] context-budget 假绿已删除；既有 out-of-unit 产品缺口未被文字断言或无 issue 的 xfail 掩盖，并有直接复现证据。
- [ ] M5 scoped tests、相关 CLI contract、ruff、diff/scope 检查通过。

## 测试策略

- 被测行为（来自退出标准）：用户从 `run_cli` 进入 REPL 与自动化命令时，公开命令、流式结果、错误、TTY/非 TTY 输出、steer 与资源关闭仍可观察；产品仅经 `agent.sdk` 触达内核。
- 已有测试在：本 milestone 的 root CLI tests（收敛与扩展）；SDK import 边界在 `tests/contract/test_cli_sdk_only_contract.py`，不新建重复 root 扫描。
- 落层/目录/marker：`tests/unit/` 与既有 `tests/contract/`，marker：无。
- 可选依赖 importorskip：无。
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：真实 `run_cli` context-budget 缺口复现命令输出，仅记录在 `progress.md`。

### 受影响的既有测试处置

| 风险 / 行为 | 既有测试 | 处置 | 理由与保留或替代保护 | 验证 |
|---|---|---|---|---|
| CLI 公开 REPL 命令、会话与错误行为 | `tests/unit/test_cli_repl_commands.py::test_*`、`tests/unit/test_cli_async_repl_sdk.py::test_run_cli_*` | rewrite-merge | 风险仍在；保留直接经过 `run_cli` 的最小用户旅程，合并同一 stub/path 的重复测试并删除只检查 SDK 方法名的迁移断言 | scoped pytest + CLI contract |
| `--text` NDJSON、`--resume` 和当前 model 提交 | `tests/unit/test_cli_text_sse.py::test_run_cli_text_mode_*` | keep | 直接经过公开自动化入口，处于最低合适层；清除文件内已退役 SSE 术语和重复 REPL 路径 | scoped pytest |
| 运行中输入 steer 与空闲新 run | `tests/unit/test_cli_repl_steering.py::test_*` | keep | 直接经过 REPL 入口并控制真实并发窗口，保护 current spec 的独立时序风险 | scoped pytest |
| SDK-only import 边界 | `tests/unit/test_apps_coding_cli_location.py`、`tests/unit/test_cli_structure.py::test_cli_commands_surface_matches_app_commands_module` | delete | root tests只守历史导出/模块位置；当前架构风险由 `tests/contract/test_cli_sdk_only_contract.py` 的 AST 边界在正确层拥有 | contract pytest |
| 退役 HTTP、managed/remote、health 与历史文件终态 | `tests/unit/test_coding_cli_dead_http_files_removed.py`、`tests/unit/test_apps_coding_cli_location.py::test_legacy_cli_root_is_removed`、`tests/unit/test_cli_async_repl_sdk.py::test_run_cli_no_*` | delete | 这些是迁移终态/文件布局残留；当前 SDK-only/无 HTTP 风险已有 contract seam，公开 `llm-config set` 缺失则按 current automation spec 保留 parser 行为测试 | scoped + contract pytest |
| 私有模块位置、bridge 别名、render phase 与内核关闭实现 | `tests/unit/test_cli_structure.py`、`tests/unit/test_cli_refactor_boundaries.py::test_commands_*`、`tests/unit/test_cli_async_repl_sdk.py::test_coding_cli_async_main_uses_aclose_not_close`、同文件 `test_kernel_*` | delete | 改内部组织即变红，且 Kernel 自身行为不属于 M5；CLI clean exit 继续由 `run_cli` 入口的可观察 close 结果保护 | scoped pytest |
| CLI release observability 的当前公开 helper | `tests/unit/test_cli_refactor_boundaries.py::test_cli_release_observability_is_thin_compat_shim` | rewrite-merge | README 仍公开该 helper；去掉自指“compat shim”断言，仅保留输入到诊断输出的行为 | focused pytest |
| 已退役 managed-mode release playbook | `tests/unit/test_cli_refactor_boundaries.py::test_cli_release_playbook_*` | delete | 断言已不存在的 `--mode managed`、`--base-url` 和历史 gate 文件，不对应 current CLI 风险 | focused pytest |
| 自动权限状态提示 | `tests/unit/test_repl_auto_mode_banner.py`、`tests/unit/test_cli_mode.py::test_run_cli_auto_mode_banner_shown_at_startup` | rewrite-merge | 风险是用户是否从真实 REPL 看到权限状态；把私有 loader/banner 单测合并成 `run_cli` 入口测试 | focused pytest |
| context budget 与 70/85/95 hint | `tests/unit/test_cli_repl_commands.py::test_run_cli_repl_context_budget_shows_threshold_hint`、`tests/unit/test_cli_context_budget.py`、`tests/unit/test_repl_summary.py::test_print_turn_summary_*budget*` | delete | 现有测试只断言 echo/私有 helper，无法保护 current spec；真实入口已复现产品未传 kernel。无既有 issue，按 orchestrator 裁决不新增无 issue xfail，本 milestone 不声称风险已关闭 | progress 直接证据 + scoped pytest |
| REPL 输入编辑、历史、CJK 与非 TTY | `tests/unit/test_cli_repl_input.py::test_*` | rewrite-merge | 保留按键到提交文本及 `run_cli` 历史回放；删除未使用 HTTP client stub、私有 state/redraw 次数断言 | focused pytest |
| 异步工具流、去重、错误和摘要 | `tests/unit/test_cli_repl_async.py::test_*`、`tests/unit/test_repl_summary.py::test_*`、`tests/unit/test_repl_tool_lines.py::test_*` | rewrite-merge | 风险仍在；保留用户可见输出，合并同一 event fixture 的重复断言，删除私有 phase/调用断言 | focused pytest |
| 无产品调用者的 Rich renderer | `tests/unit/test_repl_live.py` | delete | `ReplLiveRenderer` / `ReplBlockRenderer` 在产品代码中无调用者，测试只 mock Rich 并断言私有字段 | scope search + scoped pytest |
| HTTP client 时代的未使用 async stubs | `tests/unit/_cli_async_stubs.py` | delete | scoped/full tests 仅使用其中一个终端行模拟 helper；把该 helper移到唯一消费者后，整文件无调用者 | `rg` usage + scoped pytest |
| 当前 Kernel test fixture | `tests/unit/_cli_kernel_stubs.py` | rewrite-merge | 多个入口/contract 仍复用；只删除无调用者或随假绿一起退役的 stub，保留最小共享 fixture | `rg` usage + scoped/contract pytest |

## Roadpoints

### R1 — 完成切片审计与处置计划

- 状态: DONE
- 步骤: 对照 current CLI/spec、M1 判据、源码调用者与 contract seam，完成受影响测试处置表和 scoped 基线。
- 验证: `163 passed`；定位退役 HTTP/布局/private/重复覆盖与 context-budget 假绿的直接证据。

### R2 — 删除退役架构与私有实现保护

- 状态: TODO
- 步骤: 删除历史文件终态、模块位置、bridge/internal Kernel、managed release playbook、无调用者 renderer 与 HTTP async stubs；保留 observability 当前行为测试。
- 验证: focused tests、usage search、CLI contract。

### R3 — 将剩余覆盖收敛到当前行为 seam

- 状态: TODO
- 步骤: 合并重复 CLI entry/render/input tests，改写 auto-mode 为真实 REPL 入口，删除 context-budget 假绿并记录未决产品风险，精简共享 stubs。
- 验证: focused tests、scoped 全量、真实 CLI entry 复现。

### R4 — 最终门禁与范围证据

- 状态: TODO
- 步骤: 核对处置表与最终测试树，运行 scoped tests、相关 contract、ruff、diff/scope 检查，补齐 progress。
- 验证: 全部门禁绿；changed paths 仅 M5 范围。
