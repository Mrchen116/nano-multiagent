# feat-392-M1 — Progress

> 本 milestone 产物是文档 + skill 文本(meta unit),无运行时代码改动。每个 roadpoint 的"真实入口验证"
> = 拿契约层每条 Requirement/Scenario 对照 `tests/contract/` + `src/agent/sdk/kernel.py` 逐条核对(料源 ①②)。

## R1 — docs/SPEC_GUIDE.md 文档规范

- Context: SDD 长青文档体系的地基。先定"放什么/不放什么 + 骨架",后续 kernel 契约层(R2)
  和 M2-M4 三包才有统一规范可照,否则回填进烂结构=重新 rot(spec.md 澄清 Q3)。
- Decision: 新建 `docs/SPEC_GUIDE.md`,含六块:① 判据两问(稳定 + 不可廉价重建);② 不进 spec
  的分流表(实现→代码/决策→design.md/how-to→AGENTS·runbook/跨包→SPEC.md/瞬态→changes·issue);
  ③ 契约层文件骨架(`# <包> Specification` → `> 对齐:` 行 → `## Purpose` → `## Requirements`
  含 `### Requirement:` + `#### Scenario:` GIVEN/WHEN/THEN);④ 库/内核契约写法纪律
  (照 research §7.5:WHEN/THEN 主语=消费者、每 Req 一份 pre→post 契约或 invariant、CDC 裁剪、
  spec-anchored);⑤ 收尾归并 checklist(orchestrator 提 PR 前直接编辑 canonical + bump 对齐行
  + 软对账,无 delta 工件);⑥ 读侧 grounding checklist(spec 阶段读契约层取词汇、design 阶段
  对代码 grounding 报不一致);⑦ 迁移料源优先级(tests/contract → 代码 → 旧文档仅备忘)。
- Rationale: 严格遵循 design 决策 4——契约层保持纯 `Purpose + Requirement/Scenario`,**无**
  `覆盖:` 行 / `[可执行]`·`[行为]` 标签 / freshness 测试;drift 走软对账(follow OpenSpec)。
  research §10 曾主张 RTM 内联 `覆盖:`+freshness 硬卡,但 design 决策 4 明确否决——以 design 为准,
  GUIDE 里明文写"不写覆盖行、不建 freshness 测试"。
- Evidence:
  - Tests: N/A(纯文档,无可断言行为;决策 4 否决 freshness 测试)。本 unit 收尾复跑全树确认不破坏。
  - Entry: 自审对照 spec.md 验收 Requirement「文档规范 GUIDE 定义放什么/不放什么 + 骨架」的
    Scenario「作者按规范判断内容归属」——GUIDE 给出判据(两问)、契约层骨架、分流表,三要素齐 ✓。
  - Frontend State Matrix: N/A(无界面)
  - Browser QA: N/A
  - E2E/Regression: N/A — 决策 4 走软对账,不做机械绑定/freshness,无回归用例可落。
  - Visual/Interaction: N/A
- Rollback: 纯新增文件,`git rm docs/SPEC_GUIDE.md` 即回退。
- Commits: 见 git log(R1 单 commit,文档规范类无可断言红测试,省独立 C1,理由见 §FL②红测试豁免)。

## R2 — docs/specs/kernel/spec.md 内核契约层

- Context: 最难的一包。内核是**库**(无 UI),消费者 = 经 `agent.sdk` 调它的两个产品 +
  `tests/contract/` 契约测试。要从代码/测试逆向出"当前对外行为契约",不从旧 `内核设计SPEC.md`
  蒸馏(它仍描述 refactor-387 已删的 §12 HTTP API,蒸馏=种旧 drift)。
- Decision: 照 R1 GUIDE 骨架写 `docs/specs/kernel/spec.md`,纯 `Purpose + Requirement/Scenario`,
  12 Requirement / 23 Scenario。每条 Scenario 主语 = 消费者(产品 / contract 测试),按 CDC 只收
  调用方依赖的对外行为。覆盖:边界不变量(only sdk / no upward / core↛platform)、build_kernel
  装配 + 方法集、create_session 绑 workspace、submit 非阻塞 + stream 跨循环、can_use_tool 许可裁决
  + interrupt 解除挂起、cancel 幂等/未知 run、LLM config get/reconfigure 纯配置切换、compaction
  可恢复、5 内置工具 + bash 截断/超时契约、hook 事件集(4 intercept)+ fail-open、skill 自动列表 +
  `/skill:` 改写、会话溯源持久化重启可恢复。
- Rationale: 料源优先级照 design 决策 7——① `tests/contract/`(可执行契约,不 drift)② `src/agent/
  sdk/kernel.py` 实际代码;③ 旧 SPEC 仅作 checklist。逐条 Requirement 拿 contract 测试断言 +
  kernel.py 方法签名重核,核不上即弃。已删 HTTP API(`/v1/*`、`AgentRuntime` 旧 §3、`platform/
  http_api`)一律不写。
- Evidence:
  - Tests: N/A(契约层不带 freshness 测试,决策 4)。但每条 Requirement 已对照现有 contract 测试
    印证其为真(见下 Entry)。
  - Entry(逐条代码/测试对照——这是本 unit 的"真实入口验证",拿契约对 tests/contract + kernel.py 核):
    · 边界不变量 → `test_agent_sdk_boundary_contract.py`(only sdk / no upward / 暴露 build_kernel+Kernel)
      + `test_core_no_platform_imports.py`(core↛platform/products/fastapi/starlette)。
    · build_kernel 装配 + 方法集 → `test_agent_sdk_surface_contract.py::test_build_kernel_returns_kernel_instance`
      + `::test_kernel_exposes_required_methods`(方法名逐一对 `kernel.py` 核:create_session/fork_session/
      compact/submit/stream/interrupt/cancel/get_run/list_session_tools/get_llm_config/reconfigure_llm/close ✓)。
    · create_session 绑 workspace → `kernel.py:247` create_session(workspace_root=...)。
    · submit 非阻塞 + stream → `::test_cross_loop_streaming_receives_run_status_event`(收到 run_status,
      terminal completed)+ `test_kernel_sdk_behavior_contract.py::test_message_sync_completes_and_updates_run`
      (turn_id 非空)。
    · can_use_tool 裁决 + interrupt 解除许可 → `::test_can_use_tool_callback_is_invoked_via_permission_requester`
      (allow→放行)+ `::test_interrupt_while_waiting_for_permission_cancels_turn`(deny,不挂起)。
    · cancel 幂等/未知/interrupt 无活动 → `::test_run_cancel_cancels_running_run_idempotent` +
      `::test_cancel_unknown_run_returns_none`(None 不抛)+ `::test_session_interrupt_returns_run_id`。
    · LLM config get/reconfigure → `::test_llm_config_get_shape`(provider/model/base_url)+
      `::test_llm_config_reconfigure_updates_provider` + `::test_global_capabilities_llm_config_round_trip`。
    · compaction → `kernel.py:297` compact() + `test_compaction_contract.py`(reason threshold/overflow/manual、
      result.first_kept_event_id)。
    · 5 工具 + bash 截断/超时 → `test_tools_bash_contract.py::test_bash_truncation_contract_exposes_full_output_path`
      (truncated=True)+ `::test_bash_timeout_contract_exposes_stable_details`;list_session_tools →
      `::test_list_session_tools_returns_result`。
    · hook 事件集 + fail-open → `test_hooks_contract.py::test_hook_event_contracts_are_stable`
      (INTERCEPT_EVENTS={input,before_agent_start,tool_call,tool_result}、priority 100、timeout 1500)。
    · skill 改写 → `test_skill_commands_contract.py`(`/skill:doc`→`Use the "doc" skill...`、带参追加 User input)。
  - 格式自检(命令): `grep -c 覆盖:` = 0、`grep -cE '\[可执行\]|\[行为\]'` = 0、`grep -cE '/v1/|http_api'` = 0。
  - Frontend State Matrix: N/A(无界面)
  - Browser QA: N/A
  - E2E/Regression: N/A — 决策 4 走软对账。系统级硬卡留给 orchestrator 收尾(reviewer/verifier 对账)。
  - Visual/Interaction: N/A
- Rollback: 纯新增文件,`git rm docs/specs/kernel/spec.md` 即回退。
- Commits: 见 git log(R2 单 commit,契约文档无可断言红测试,省独立 C1,§FL② 豁免)。

## R3 — 顶点 SPEC.md 重定位 + AGENTS.md 索引 + 退役旧内核 SPEC

- Context: SPEC.md 已基本是顶点形态(决策 6),只需轻度重定位:§6 文档索引指向新 `docs/specs/`,
  去掉对旧内核 SPEC 的活索引;AGENTS.md「关键文档索引」同步;`内核设计SPEC.md` git mv 退役。
- Decision:
  · SPEC.md §4 内核「详见」链接 `docs/内核设计SPEC.md` → `docs/specs/kernel/spec.md`。
  · SPEC.md §6 重构为四块:长青行为契约层(kernel current + im/gateway/cli 标注 M2-M4 建立)、
    文档规范与约定(SPEC_GUIDE/TESTING_GUIDE/COMMENTING/runbook/LLM)、内核实现细化(细化目录,
    标注"非契约层")、旧子系统 SPEC(标注迁移退役中,M2-M4 退役其余三份)。顶部版本 bump v1.4 / 对齐 feat-392。
  · AGENTS.md「关键文档索引」表:置顶文档规范 + 长青契约层指向,内核行换 `docs/specs/kernel/spec.md`,
    旧子系统 SPEC 标注迁移中。
  · `git mv docs/内核设计SPEC.md docs/archive/内核设计SPEC.md`。
- Rationale: 决策 6——SPEC.md 收口顶点、去重(同一事实单一 canonical 落点);旧内核 SPEC 是混合高度 +
  已 rot(§12 HTTP API 在 refactor-387 已删),退役而非保留并存。M2-M4 才退役其余三份子系统 SPEC,
  故本 R 只退役内核一份,其余在 §6 标注"待迁移"避免越界(范围列只点名 `docs/内核设计SPEC.md`)。
  内核实现细化目录(工具/Hook/Skill/系统提示词细化)不在 M1 范围,保留索引但归为"实现叙事,非契约层"。
- Evidence:
  - Tests: N/A(纯文档)。收尾复跑全树确认不破坏。
  - Entry(链接完整性):SPEC.md/AGENTS.md 新指向的 6 个文件(specs/kernel/spec.md、SPEC_GUIDE.md、
    TESTING_GUIDE.md、COMMENTING_GUIDE.md、operator-runbook.md、archive/内核设计SPEC.md)均存在(grep -e 全 OK)。
    SPEC.md 仍纯顶点:`grep -cE 'def |class|函数|内部数据结构'` = 0,无下钻单包内部行为。
    `grep 内核设计SPEC SPEC.md AGENTS.md` 仅剩两处"退役说明"文字,无活链接。
  - Frontend State Matrix / Browser QA / E2E / Visual: N/A(纯文档)
  - 衔接发现(已问 leader):`.claude/skills/change-reviewer/` 的 acceptance.md / regression.md / SKILL.md
    含指向 `docs/内核设计SPEC.md` 的"文档更新清单"行,该文档已退役。change-reviewer 不在 M1 范围
    (design 只点名 spec/design/orchestrator 三 skill)→ 见 R3 末「衔接问题」段处置。
    `TASKS/`、`PROGRESS/` 历史归档 + `docs/需求.md` 的引用属冻结历史/M2 退役范畴,不动。
- Rollback: `git mv` 回退 + 还原 SPEC.md/AGENTS.md 两处编辑(单 commit `git revert`)。
- Commits: 见 git log(R3)。

## R4 — change-* skill 接入读写闭环

- Context: 长青层只有被读写闭环接进 change-* 才有价值。design 决策 6 + M1 范围:spec-author/
  design-author 读侧指向 `docs/specs/<包>`(design 阶段对代码 grounding);orchestrator §7 提 PR 前加
  收尾归并步 + reviewer/verifier 软对账。
- Decision:
  · **change-spec-author**:§3.1 澄清"基于项目现状"处加引文——取项目现状读 `docs/specs/<包>/spec.md`
    (current 行为契约单一权威),明确 spec 阶段是读侧、代码 grounding 留给 design 阶段。
  · **change-design-author**:§3.0.1 必读清单表新增「长青行为契约层(current)」行指向 `docs/specs/
    <包>`;架构总图行的 SPEC.md 注"跨包顶点"。§3.0.1 末加「契约层 grounding(design 阶段强制)」段:
    读契约层并与 `src/<包>/` 代码核对,发现 drift 在 §3.0.2 现状摘要显式报出。§3.0.2 摘要模板加
    「契约层 grounding 结论」行 + 把旧的"只能 HTTP 访问 agent"约束例改成"只能 import agent.sdk"
    (refactor-387 后正确口径)。
  · **change-orchestrator**:§0.3 硬规则加第二个例外(收尾归并长青契约层 ≠ 改变更稿 spec);新增
    **§7.0 收尾归并步**(§6.1 pass 后、§7.1 sync gate 前):① 软对账(复用 reviewer/verifier 对每条
    Requirement/Scenario 搜代码+测试,报一致/背离/缺口,advisory 不出红测)② 归并(orchestrator 依据
    design.md + 代码 diff + 对账报告,直接编辑 `docs/specs/<包>`,过两问判据+库契约四纪律,bump 对齐行,
    无对外行为变化记 "no spec delta",**无独立 delta 工件**);§7.2 PR body 加 Spec delta 行。
- Rationale: 严格遵循决策 3(无 delta 工件,orchestrator 收尾直接改 canonical)+ 决策 4(软对账
  follow OpenSpec,不机械绑定/freshness)。§7.0 明文重申契约层格式纪律(无 覆盖: / 标签 / freshness)
  防 worker 收尾时违格式。§0.3 加例外是必须的——否则 §7.0 与"orchestrator 不改 spec"硬规则打架;
  用"长青契约层 ≠ 变更稿 spec"消歧。
- Evidence:
  - Tests: N/A(skill 文本,无可执行断言)。
  - Entry(grep 命中):spec-author 命中 docs/specs ×1、design-author ×3、orchestrator ×8;orchestrator
    收尾纪律关键词(no spec delta / 无独立 delta / 软对账 / 对齐: / 两问判据)命中 8;design-author 必读
    清单表新行渲染正常(7 列对齐)。
  - Frontend State Matrix / Browser QA / E2E / Visual: N/A(skill 文本)
- 衔接残口(reviewer 模板,已问 leader):change-reviewer 的 acceptance.md/regression.md/SKILL.md 还有
  指向退役 `docs/内核设计SPEC.md` 的「长青文档更新清单」行。change-reviewer 不在 M1 范围(design 只点
  名三 skill)→ 等 leader 拍板是否 M1 内顺手更新(选项 a)或留后续(选项 b)。本 R 先提交确定的三 skill。
- Rollback: 三 skill 改动可单独 `git revert`(集成路径不变)。
- Commits: 见 git log(R4)。
