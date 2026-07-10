# Verification Report: feat-392

> 验证对象：`unit/feat-392` @ `6cddeed3`（M1-M4 全部合并态）
> mode: full · review_round: 1 · verdict: **pass**

## Round 1

### Summary

| 维度          | 结果                          |
|---------------|-------------------------------|
| Completeness  | Tasks 全 DONE · Spec 8/8 Requirement 有落点 |
| Correctness   | 四包契约层逐包对账：无 CRITICAL 偏差 |
| Coherence     | Followed（8 条决策全遵守，四包形态一致） |
| 测试基线      | `pytest -m "not e2e"` **2342 passed, 4 deselected**（= 基线 2342） |
| 问题计数      | CRITICAL 0 · WARNING 0 · SUGGESTION 2 |

---

## §1 Completeness

### Task 完成检查
- `M1-foundation-kernel/tasks.md`：退出标准 9/9 全 `[x]`，R1-R5 全 DONE。
- `M2-im-spec/tasks.md`：退出标准 7/7 全 `[x]`，R1-R3 全 DONE。
- M3 / M4 为单 commit milestone（无独立 tasks.md 目录，worker 直接合并）：
  - M3 commit `71900921`（Merge `18007f75`）：`docs/specs/gateway/spec.md` + git mv `NodeGateway-SPEC` → archive + SPEC.md/AGENTS.md 同步。
  - M4 commit `5e918bc4`（Merge `76cad528`）：`docs/specs/cli/spec.md` + git mv `CodingCLI-SPEC` → archive + 架构测试 `CODING_CLI_SPEC` retarget。
  - 二者均在 design.md Milestones 表里属"单文件 milestone"，产物齐全，无遗留 task。

**结论：Tasks 全完成。**

### Spec 8 条 Requirement 落点（验收标准 §77-144）

| # | spec Requirement | 落点 | 状态 |
|---|---|---|---|
| 1 | 长青行为契约层存在且按包组织 | `docs/specs/{kernel,im,gateway,cli}/spec.md` 四份全在，均 `Purpose + Requirement/Scenario`；契约层不含实现走查（抽查 kernel/cli 均为消费者主语） | ✅ |
| 2 | 单元收尾把行为增量归并进契约层（无 delta 工件） | orchestrator `SKILL.md` §7.0「收尾归并」步存在（行 536-570），含 no-spec-delta 分支 + bump 对齐行 + 无 delta 工件 | ✅ |
| 3 | 不维护 living 全量 design | SPEC_GUIDE 行 21-22 明确"不维护 living 全量 design / 不建 ADR 层"；仓内无 `docs/decisions/`、无 design 大全文件 | ✅ |
| 4 | 顶点 SPEC.md 与契约层分工不重复 | SPEC.md §4 写包职责/分层/依赖方向（跨包架构），末尾链接指向 `docs/specs/kernel/spec.md`，不下钻单包行为契约 | ✅ |
| 5 | SPEC_GUIDE 定义放什么/不放什么 + 骨架 | `docs/SPEC_GUIDE.md` 含判据两问、分流表、契约层骨架、库契约四纪律、收尾归并 checklist、读侧 grounding checklist | ✅ |
| 6 | change-* 读侧接入契约层 + grounding | spec-author（行 108）、design-author（行 93 读侧 + 行 104 强制 grounding）均指向 `docs/specs/<包>` | ✅ |
| 7 | 契约层与代码背离在收尾对账暴露 | orchestrator §7.0 ①软对账复用 reviewer/verifier；reviewer 模板（SKILL.md 行 361 + assets）文档清单改指 docs/specs | ✅ |
| 8 | 既有陈旧文档迁移到新结构 | 四份旧 SPEC 全在 `docs/archive/`；SPEC.md §6 归档表 + AGENTS.md 尾注标退役并链对应契约层 | ✅ |

**结论：8/8 Requirement 均有可观察落点。**

---

## §2 Correctness — 四包契约层逐包对账

> 按 SPEC_GUIDE：契约层只写对外可观察行为，不下钻内部实现。逐条 Requirement/Scenario 对 `src/<包>` + `tests/` 核其是否属实、有无与代码矛盾。

### kernel（`docs/specs/kernel/spec.md`，12 Req / 23 Scenario）
- **Kernel 方法集**（spec 行 54-58）：逐字匹配 `src/agent/sdk/kernel.py` —— `create_session`/`fork_session`/`compact`/`submit`/`stream`/`interrupt`/`cancel`/`get_run`/`list_session_tools`/`get_llm_config`/`reconfigure_llm`/`close` 全部存在。
- **build_kernel 签名**（行 46-52）：`kernel.py:67` `product_profile / llm_config / can_use_tool / repo_root` 匹配。
- **Hook 契约**（行 163-166）：`INTERCEPT_EVENTS == {input, before_agent_start, tool_call, tool_result}`（`hooks/types.py:53`），`DEFAULT_HOOK_PRIORITY=100` / `DEFAULT_HOOK_TIMEOUT_MS=1500` 逐字印证。
- **5 工具**（行 141-148）：`read/write/edit/bash/task` 在 `platform/tools/builtins/` + presentation 注册。
- **边界不变量**（行 24-42）：契约测试 `test_agent_sdk_boundary_contract.py` / `test_core_no_platform_imports.py` 把守，文件均存在。
- 偏差：**无**。

### im（`docs/specs/im/spec.md`，14 Req / 33 Scenario）
- **跨租 404 / 401 无 user_id 捷径**（行 47-72）：`test_routes_require_auth.py` 注释逐字"404, not 403 to avoid existence oracles"+ `test_get_conversation_cross_tenant_returns_404` 印证。
- **gateway 错误信封**（行 222-228）：`test_gateway_protocol_contract.py` 断言 `invalid_message` / `message must be valid JSON` / `unsupported_message_type` 与契约逐字一致；`src/IM/ws/gateway_handler.py` 源端印证。
- **policies 字段集**（行 153-156）：`test_settings_policies_contract.py` 含 `max_turn_per_run`/`audit_level`/`rate_limit_per_min`。
- **relay 幂等**（行 248-261）：`idempotency_key` 在多个 im_service 测试中被测。
- 偏差：**无**。

### gateway（`docs/specs/gateway/spec.md`，11 Req / 30 Scenario）
- **未知 agent 拒路由**（行 46-49）：`inbound_pipeline.py:636` `raise LookupError(f"unknown agent_id: {agent_id}")` 精确印证。
- **/stop 提示语**（行 75-89）：`inbound_pipeline.py:519/540`「当前没有正在执行的操作。」/「已停止当前操作。」逐字匹配。
- **PID 锁提示**（行 119-123）：`main.py:1102` `gateway is already running (pid=...)` 印证。
- **NO_REPLY / group_reply_policy MENTION/ALWAYS**（行 51-73）：`inbound_pipeline.py` + `group_context_store.py` 印证。
- **/internal/dispatch**（行 223-243）：`gateway/internal_dispatch.py` 存在并实现该端点。
- **heartbeat 三模式 at/interval/cron + 补跑**（行 200-221）：`scheduler/heartbeat_scheduler.py:313-341` 三模式齐全。
- 偏差：**无**。

### cli（`docs/specs/cli/spec.md`，10 Req / 20 Scenario）
- **斜杠命令集**（行 63）：`input/repl_commands.py:11` `REPL_COMMANDS = ("/help","/new","/use","/session","/tools","/compact","/history","/exit")` 逐字匹配。
- **错误三层 input/network/runtime**（行 99-110）：`render/error_presenter.py:3` `_ERROR_LAYERS = {"input","network","runtime"}` + `error_layer_for_exception` 返回三层。
- **无 managed/remote 参数与 HTTP 子命令**（行 36-39）：CLI 解析无 `--mode`/`--base-url`、无 `health`/`create-session`/`send-message`。
- **local_coding / nanocode**（行 159-166）：`commands.py:265` `LOCAL_CODING_PROFILE`、`commands.py:1070` `~/.nanocode/config.yaml`。
- **--text NDJSON / --resume**（行 125-138）：`text_runner.py` + `commands.py:112 --resume`。
- **边界**（行 149-157）：`test_cli_http_only_contract.py` 把守。
- 偏差：**无**（关于 error_presenter 残留陈旧文案见 SUGGESTION-2，属 out-of-unit）。

**§2 结论：四包契约层准确描述当前代码行为，无 CRITICAL/WARNING 级偏差。**

---

## §3 Coherence — design 决策遵守

| 决策 | 遵守证据 |
|---|---|
| 1 长青层只装行为契约，不维护 design 大全 | 四包 spec 纯 Purpose+Req/Scenario；无 design 大全文件 |
| 2 契约层按 4 包，kernel 单文件多节 | `docs/specs/{kernel,im,gateway,cli}/spec.md` 四份；kernel 未拆 core/platform/products |
| 3 无 delta 工件，orchestrator §7.0 收尾直改 canonical | §7.0 步存在，明确"无 delta 工件、直接编辑 canonical" |
| 4 软对账，无机械绑定 | 契约层无 `覆盖:` 行 / 无 `[可执行]`/`[行为]` 标签 / 无 freshness 测试（grep 全空）；唯一引用 docs/specs 的 `test_multi_product_architecture_acceptance.py` 是 CODING_CLI_SPEC 文件可读断言，非契约层 freshness 硬卡 |
| 5 砍 ADR 层 | 无 `docs/decisions/` |
| 6 SPEC.md 顶点 + 旧 4 份退役 | SPEC.md §6 指向 docs/specs；四份旧 SPEC 全在 `docs/archive/` |
| 7 迁移 code/tests 第一 | 旧 SPEC 仅作 checklist，commit message 记录"核不上即弃"；契约与代码对账全部成立 |
| 8 命名 SPEC_GUIDE + docs/specs/<包>/spec.md | 落地一致 |

**四包 spec 形态一致**：四份均 `# <包> Specification` + `> 对齐: feat-392` + 写法纪律链 + Purpose（含显式不负责）+ Requirements，照 kernel 样板。

**退役完整性**：`grep` src/ + tests/ + 活文档（排除 docs/archive 与 docs/changes 冻结历史），无指向四份旧 SPEC 路径的悬空活引用；架构测试 `KERNEL_SPEC` 锚回 SPEC.md、`CODING_CLI_SPEC` retarget `docs/specs/cli/spec.md`。SPEC.md §6 全部索引文档（含 `docs/内核设计细化/` 四份）均存在，无悬空索引。

**§3 结论：Followed。**

---

## 问题清单

### CRITICAL
无。

### WARNING
无。

### SUGGESTION

**SUGGESTION-1（契约层 grounding 习惯，非缺陷）**
四包契约层头部均 `> 对齐: feat-392`。这是建立基线的正确写法。提示后续 unit 收尾归并时务必按 SPEC_GUIDE「收尾归并 checklist」bump 此行，否则软对账失去"最后对齐于哪个 unit"的锚。无需本 unit 改动。

**SUGGESTION-2（out-of-unit，pre-existing，非本 unit 范围）**
`src/coding_cli/render/error_presenter.py:13/15/17/19/30/36/38` 的 suggestion 文案仍引用 refactor-387 已删的 `--base-url` / `--mode remote` / `--mode managed`。cli 契约层（行 38-39）已正确声明这些参数"不存在"，故**契约层无偏差**；偏差在 src 死文案，属 refactor-387 遗留，不在 feat-392（纯文档/skill unit）范围。建议另立 bugfix-lite 清理该文案，与本 unit 验收无关。

---

## 结尾

All checks passed. Ready for PR.

四包契约层准确反映当前代码行为，8 条 spec Requirement 全有落点，8 条 design 决策全遵守，契约层纪律干净（无机械绑定标签/freshness 测试），退役完整无悬空活引用，全测试树 2342 passed（= 基线）。无 CRITICAL、无 WARNING；2 条 SUGGESTION 均为 out-of-unit / 习惯性提示，不阻塞提 PR。
