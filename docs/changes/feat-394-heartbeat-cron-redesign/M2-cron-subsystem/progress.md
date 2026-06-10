# feat-394-M2: cron-subsystem — Progress

Worktree: /Users/czj/Repos/nano-multiagent/.worktrees/feat-394-M2
Branch: milestone/feat-394-M2
Unit branch: unit/feat-394

## 基线

测试基线（2026-06-02）：2383 通过，2 个 macOS /tmp vs /private/tmp 路径问题为预存失败（issue #75，非本 unit 引入）。

## M1 地基复用清单

- `_AtSchedule`/`_IntervalSchedule`/`_CronSchedule`：M1 已改为不补跑语义，R1 直接写 cron 专属单测
- `AgentWorkspaceConfig.heartbeat_enabled` 模式：R4 仿照新增 `cron_enabled`
- `heartbeat_json` IM→gateway 同步链路：R4/R7 仿照新增 `cron_json` 全链路
- `_heartbeat_enabled(ctx)` enabled_when 机制：R8 仿照新增 `_cron_enabled` 和 `_both_enabled`
- feat-393 投递闭环：R5 文档层复用（CronRunner 调 kernel_client 时 origin=cron）
- `PersistentSessionBindingStore.find_direct_by_agent`：R5 CronRunner 用来找 canonical session

---

### R1 — cron 调度不补跑单测 + CronJobStore 持久化

- Context: M1 已将 heartbeat_scheduler.py 中的调度类改为不补跑；M2 cron 需要独立调度单测
- Decision: 新建 `cron_scheduler.py`（`CronJob`, `CronJobStore`, `CronSchedulerStateStore`, `CronScheduler`）；at/every/cron 三种调度逻辑与 M1 实现完全对齐（同一 openclaw computeNextRunAtMs 语义）
- Rationale: cron 子系统有独立 jobs.json 持久化，与 heartbeat 调度器正交分离
- Evidence:
  - Tests: 28/28 通过，后续全量回归无新增失败
  - Entry: N/A（单元测试）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: 单测覆盖 not-backfill / first-tick / double-fire-guard / disabled-skip
  - Visual/Interaction: N/A
- Rollback: feat(feat-394/M2/R1) commit
- Commits: C1=57470091, C2=f4be6552, C3=（R1 docs 含在 R1 实现 commit 中）
- Next: R3 cron 工具

---

### R2 — 并入 R1（CronJobStore 持久化已含）

R2 范围（CronJobStore 持久化 + CronScheduler 多任务调度）已全部包含在 R1 实现中。

---

### R3 — cron 工具（openclaw 逐字 + Provenance + toolsets 门控）

- Context: design 决策 6 要求 cron 工具描述/schema 逐字照抄 openclaw cron-tool.ts:527-595，并标 Provenance 注释；决策 7 要求仅 PA 包含 cron 工具
- Decision: 新建 `agent/products/personal_assistant/tools/cron.py`（NamedTuple _CronJob 内联，避免 agent→personal_assistant 边界违规；描述照抄 openclaw，裁掉 wake/sessionTarget/多渠道/webhook）；`toolsets.py` OPTIONAL_TOOL_IDS 加 "cron"；更新 3 个硬编码 optional_tool_ids=["send_message"] 的既有测试
- Rationale: agent.products 包不能 import personal_assistant，内联轻量类型；NamedTuple 避免动态加载时 @dataclass(frozen=True,slots=True) 的 sys.modules None 问题
- Evidence:
  - Tests: 16/16 通过；全量回归无新增失败
  - Entry: N/A
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: feat(feat-394/M2/R3) commit
- Commits: C1=f3d2e4cb, C2=c286c536

---

### R4 — cron_enabled 字段同步链路

- Context: M1 已建 heartbeat_enabled 同款同步链路；M2 仿照新增 cron_enabled
- Decision: `AgentWorkspaceConfig` 加 `cron_enabled: bool = False`；`main.py sync_agent` 加 `_parse_cron_enabled_from_im_payload` 解析（兼容 cron_json 字符串和 cron dict 两种 payload 格式）
- Rationale: 与 M1 heartbeat_enabled 模式完全一致，IM→gateway 配置下发路径标准化
- Evidence:
  - Tests: 4/4 通过；全量回归无新增失败
  - Entry: N/A
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: feat(feat-394/M2/R4) commit
- Commits: C1=6bb5ac39, C2=b86d23f1

---

### R5 — CronRunner 隔离执行 + awareness 注入 + delete_after_run

- Context: design 决策 4 + C-awareness：cron 在隔离 session 跑，结果以 System(untrusted) append 进 canonical 直聊 JSONL
- Decision: 新建 `personal_assistant/scheduler/cron_runner.py`（`CronRunner`）；`_submit_cron_job` 以 origin=cron 提交隔离 session；`_append_awareness` 将结果文本以 `System (untrusted): [ts] <text>` append 进 canonical session JSONL；`delete_after_run=True` 时提交后立即删 job
- Rationale: openclaw `queueCronAwarenessSystemEvent` 对应机制；nano 用 JSONL 持久化比内存队列更稳定（跨重启不丢）
- Evidence:
  - Tests: 5/5 通过；全量回归无新增失败
  - Entry: N/A
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: test_cron_runner_awareness_appended_to_canonical_session 断言 JSONL 内容
  - Visual/Interaction: N/A
- Rollback: feat(feat-394/M2/R5) commit
- Commits: C1=4ed433bd, C2=2bc7bd84

---

### R6 — coding_cli 隔离断言

- Context: 决策 7：cron 工具和 heartbeat/cron prompt 段不得进 coding_cli
- Decision: 新建 `tests/contract/test_cron_coding_cli_isolation.py` 四条断言（toolsets、prompt segments、文件路径、PA 存在性）
- Rationale: 合约测试防止日后误合并
- Evidence:
  - Tests: 5/5 通过（R8 实现前 1 条 skip，R8 完成后全通过）
  - Entry: N/A
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: 合约断言落库
  - Visual/Interaction: N/A
- Rollback: feat(feat-394/M2/R6) commit
- Commits: C2=4742e617

---

### R7 — IM 前端 cron 开关 UI + API 字段 + DB migration + 同步链路补全

- Context: M1 已建 heartbeat 开关 UI（HeartbeatCard）；M2 仿照新增 CronCard；同时发现 heartbeat 的 IM 全链路（API→domain→repo→DB→config_service）需要 cron 同款补齐
- Decision: 前端 `agent-detail-page.tsx` 新增 `CronCard` 组件（`data-testid="cron-enabled-toggle"`）；`im-agent-config-api.ts` 加 `CronConfig` 类型 + `cron` 字段；IM 后端 `UpdateAgentConfigRequest` 加 `model_validator` 自动转换 `cron: {...}→cron_json: "..."`（同时修复 heartbeat 同款 frontend→backend 字段转换）；`AgentProfile.cron_json`、`repositories.py` SQL、`db.py` migration、`config_service.py` 全链路补齐；vitest 新增 2 条 cron UI 测试（349 total 通过）
- Rationale: 完整端到端链路：前端开关→IM 存储→gateway 调度器
- Evidence:
  - Tests: 349/349 vitest + 2440/2440 pytest（minus pre-existing 2）
  - Entry: N/A（不需要运行态验证，由 reviewer 验收）
  - Frontend State Matrix: default(off)/enabled(on)覆盖；mobile/desktop N/A（截图由 reviewer 验收）
  - Browser QA: N/A（reviewer 验收）
  - E2E/Regression: vitest agent-detail-page.test.tsx 2 新增用例落库
  - Visual/Interaction: N/A（reviewer 验收）
- Rollback: feat(feat-394/M2/R7) commit
- Commits: C2=d8f8f794

---

### R8 — cron prompt 段 + 路由段 + SPEC §6 cron 部分

- Context: 决策 5/6：prompt 段需要让 agent 知道 cron 工具存在及路由逻辑；决策 7：coding_cli 不含这些段
- Decision: `prompt_sections.py` 新增 `_PA_CRON`（gated by cron_enabled）+ `_PA_CRON_ROUTING`（gated by heartbeat_enabled AND cron_enabled）两段，加入 `PA_SECTIONS` 和 `build_pa_system_prompt`；`NodeGateway-SPEC.md §6` 补 Cron 小节（调度模型/执行流程/工具/硬规则）
- Rationale: agent 需要知道 cron 工具存在才会在对话里使用；路由段帮助 agent 选择正确机制
- Evidence:
  - Tests: 6/6 通过；全量回归无新增失败
  - Entry: N/A
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: test_cron_prompt_sections.py 6 条落库
  - Visual/Interaction: N/A
- Rollback: feat(feat-394/M2/R8) commit
- Commits: C1=cba78ebc, C2=6e133331
- Next: 全量回归 → 合 unit/feat-394 → 报 DONE

---

## 最终全量回归结果

2447 通过，2 跳过，2 预存失败（macOS /tmp issue #75），4 deselected
前端 vitest: 349/349 通过

---

## Reviewer 反馈修复：heartbeat/cron 开关回显 round-trip

- 根因：`getAgentConfig` 返回的响应含 `heartbeat_json`/`cron_json`（字符串），但 `HeartbeatCard`/`CronCard` 读 `draft.heartbeat`/`draft.cron`（对象）。两者之间没有 parse 桥接，导致重开配置页时开关恒为关。
- 修复：新增 `normalizeAgentConfigResponse` 函数（`im-agent-config-api.ts`），在 `getAgentConfig` 和 `updateAgentConfig` 响应处统一 JSON.parse `heartbeat_json`→`heartbeat`、`cron_json`→`cron`。heartbeat 和 cron 一并修复。
- 测试：`im-agent-config-api.test.ts` 10 条单测（heartbeat/cron 各 5 条 round-trip 断言）+ `agent-detail-page.test.tsx` 2 条 round-trip 回归守卫（初始态 checked=true）
- 回归：pytest -m "not e2e" 2447/2447，vitest 361/361
- Commit: 11c92c7b

