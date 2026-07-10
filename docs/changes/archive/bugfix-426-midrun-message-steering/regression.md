# bugfix-426 — 回归验证

> 对齐: incident.md v1
> Review round: 1
> Reviewer: bugfix-426-reviewer-r2
> Date: 2026-06-23

---

## Verdict

**pass**

**Highest Required Action**: pass

**Issues**: blocking=0, major=0, minor=0

---

## 覆盖表（按 incident.md Requirement / Scenario 结构）

### Requirement: 运行中发送的消息在当前 run 的下一轮被带进上下文

#### Scenario: 工具循环中途发消息，下一轮即被消费

| 字段 | 内容 |
|---|---|
| 期望来源 | incident.md §目标行为与验收, WHEN + THEN |
| 验证方式 | IM 旅程3（conv `3e66223a`）：bash sleep 8 任务 → t+4s 发 steer 消息 → 等工具完成 |
| 证据 | LLM session `sess_1d2f33e307a083e0` 第4个req messages=[0]user(任务)[1]assistant(tool_use)[2]user(tool_result)[3]user(steer marker)。Agent 回复「记住了：ZZ_STEER_MARKER_426_J3」。Conv 消息列表：`[user]09:04:49 task → [agent]09:04:49 pending → [user]09:04:54 steer → [agent]09:06:00 marker回复`，全程 1 个 session，未另起新 run |
| 结果 | **pass** |
| 备注 | 工具 sleep 8 正常完成（elapsed=21654ms），steer 消息在工具批次结束后的下一轮 LLM 前注入，符合「round-boundary 注入」预期 |

#### Scenario: 不掐断正在执行的工具

| 字段 | 内容 |
|---|---|
| 期望来源 | incident.md §目标行为，GIVEN 工具正在执行 THEN 照常跑完 |
| 验证方式 | 同 IM 旅程3：bash sleep 8 跑到正常结束（`elapsed=21654ms`），后才有 steer 回复 |
| 证据 | LLM session中 tool_result 正常出现（[2]），不是被强行中断后的空 result |
| 结果 | **pass** |
| 备注 | tool 执行完毕后 steer 才注入，符合不掐工具语义 |

#### Scenario: 一个 run 内连发多条，按序全注入

| 字段 | 内容 |
|---|---|
| 期望来源 | incident.md §目标行为，Q3 FIFO 按序全注入 |
| 验证方式 | IM 旅程连发2条（conv `b812344c`）：bash sleep 12 → t+3s 发 MARKER_ALPHA → t+5s 发 MARKER_BETA |
| 证据 | LLM session `sess_78dd24a484e50e5e` 第4个req: [3]user(steer_A：ALPHA) + [4]user(steer_B：BETA) 两条按序出现。Agent 回复「已记住这两个标记」 |
| 结果 | **pass** |
| 备注 | 两条 steer 消息 FIFO 顺序（A 先 B 后）全部注入，无丢失、无乱序 |

#### Scenario: 空闲时发消息仍正常开新 run

| 字段 | 内容 |
|---|---|
| 期望来源 | incident.md §目标行为，空闲态照常 submit 新 run |
| 验证方式 | IM 旅程1（conv `1ff3a26f`）：空闲时发「请回复: IDLE_TEST_OK」 |
| 证据 | Agent 回复「IDLE_TEST_OK」（26s 内到达），行为与 bugfix 前一致 |
| 结果 | **pass** |
| 备注 | 空闲态退化到新 run，steer 改动未影响既有语义 |

### Requirement: 注入能力恢复为 SDK 内核级 affordance，consumer 统一复用

#### Scenario: 任一 agent.sdk consumer 复用同一注入能力

| 字段 | 内容 |
|---|---|
| 期望来源 | incident.md Q4，SDK 内核级能力，消费者不自行实现注入逻辑 |
| 验证方式 | 代码契约层核查（非用户面 Scenario，impl-层验收）：已有 `tests/contract/test_kernel_sdk_behavior_contract.py` 三条 steer 行为契约（steer 空闲/活跃/content 验证）；IM 与 CLI 均走 `kernel.submit(steer=True)` 同一能力 |
| 证据 | 全测试树 2759 passed，contract 层守护 SDK steer 行为；两端 live 验证均复用同一 SDK 接口 |
| 结果 | **pass** |
| 备注 | 此 Scenario 主要是实现层契约；用户可观察结果体现在 IM steer 和 CLI steer 两条旅程 |

### Requirement: IM 与 CLI 两端均恢复该能力

#### Scenario: IM 聊天运行中 steer

| 字段 | 内容 |
|---|---|
| 期望来源 | incident.md §目标行为，IM 聊天 steer 恢复 |
| 验证方式 | IM 旅程3 + 连发旅程（见上） |
| 证据 | IM conv 旅程3：steer marker `ZZ_STEER_MARKER_426_J3` 出现在 agent 回复；LLM session 证明注入同 run |
| 结果 | **pass** |

#### Scenario: CLI REPL 运行中 steer

| 字段 | 内容 |
|---|---|
| 期望来源 | incident.md §目标行为，CLI REPL steer 恢复 |
| 验证方式 | CLI 旅程（pexpect）：bash sleep 10 → t+9.7s 发 steer → 等工具完成 → 验证 steer marker 出现在终端 |
| 证据 | pexpect 输出见到 `> 好的，我知道了：CLI_STEER_MARKER_426_V2`；全程 1 个 session（`sess_46de596d087adcdc`）；LLM 日志 `sess_46de596d087adcdc` 第3个req msg[3]=steer消息 |
| 结果 | **pass** |

---

## 复现验证

**修前症状**（incident.md 复现步骤）：对接入 IM 的 agent 发一条会触发长工具链的消息，在工具循环执行期间发新消息，新消息等到当前 run 整体结束（可达 6 分 43 秒）才作为新的一个 run 被处理。

**修后验证**：相同场景（bash sleep 8 任务中途发 steer 消息），steer 消息在工具批次结束后的下一轮 LLM 前即被注入（同一 session/run），agent 回复据 steer 内容调整。全程无另起新 run。

**IM 证据**：Conv `3e66223a` LLM session 第4个req [3]user(steer消息) 出现在同 run 上下文，run 未另起。
**CLI 证据**：Session `sess_46de596d087adcdc` 第3个req msg[3]=steer消息，终端出现 steer 回复。

---

## User Journeys Exercised

| Journey | 覆盖 Scenario |
|---|---|
| J1 IM 空闲态 | 空闲时发消息仍正常开新 run |
| J2 IM 工具循环中途 steer | 工具循环中途发消息，下一轮即被消费；不掐断正在执行的工具 |
| J3 IM 连发多条 steer | 一个 run 内连发多条，按序全注入 |
| J4 CLI 运行中 steer（基础） | CLI REPL 运行中 steer；steer 注入消息 assistant 回复出现在终端 |
| J5 CLI 上下文连续性（code-review 关注点） | steer 后再发普通消息，agent 上下文连续，能引用 steer 那轮内容 |

**J5 详细证据（code-review 特别关注 a/b 两点）**：

- **(a) steer 注入消息触发的 assistant 回复是否真出现在终端**：CLI session `sess_531f4de911d4724d`，pexpect 终端输出 `> 已记住。稍后您可以随时问我。`（steer 消息注入后 agent 在该轮回复了密钥确认）。
- **(b) 再发普通消息，agent 上下文是否连续**：同 session 下一条普通消息「你刚才记住的密钥是什么？」后，agent 回复 `> 我刚才记住的密钥是 CONTEXT_SECRET_99。`。LLM 日志证明：第5个req messages [5]=assistant(已记住) + [6]=user(询问密钥)，steer 那轮 assistant 回复正确进入历史。

两点均 PASS。

---

## 回归测试

### 新增自动化测试（bugfix-426 引入的测试守护）

| 测试文件 | 覆盖场景 |
|---|---|
| `tests/unit/agent/runs/test_run_control_pending_origin.py` | pending 队列承载 origin + FIFO + drain 清空 |
| `tests/unit/test_runs_registry.py`（新增用例） | stranded 续跑 origin 跟随注入来源；force-cancel 非用户→续跑；/stop→无续跑 |
| `tests/contract/test_kernel_sdk_behavior_contract.py`（新增用例） | submit(steer=True) 空闲/活跃/content 三条 SDK 行为契约 |
| `tests/unit/test_inbound_pipeline_kernel_sdk.py`（新增用例） | Gateway inbound steer 接线 + 群聊保 sender prefix + 空闲开新 run |
| `tests/unit/test_cli_repl_steering.py`（新增） | CLI mid-run steer / idle 新 run / 连发保序 |
| `tests/unit/test_cli_async_repl_sdk.py`（新增回归） | `_drain_forever` 不因 stream 异常带崩 REPL |

全测试树：`pytest tests/ --collect-only` 收集 2766 测试；`pytest tests/ -m "not e2e"` = **2759 passed, 0 failed, 1 skipped**。

---

## Side Findings

无。

---

## 上层文档同步

- [x] `SPEC.md`（跨包顶点架构）：无需更新（该文件描述四包职责和依赖方向，不下钻单包行为细节）
- [x] `docs/specs/kernel/spec.md`：**需要更新** — bugfix-426 新增 `Kernel.submit(steer)` + `RunInfo.injected` 行为；delta-spec 已在 `docs/changes/bugfix-426-midrun-message-steering/specs/kernel/spec.md`，orchestrator 收尾归并时写入正式契约层
- [x] `docs/specs/gateway/spec.md`：**需要更新** — IM 运行中用户消息注入活跃 run 下一轮；delta-spec 已在 `docs/changes/bugfix-426-midrun-message-steering/specs/gateway/spec.md`
- [x] `docs/specs/cli/spec.md`：**需要更新** — CLI 运行中输入注入活跃 run 下一轮（非阻塞）；delta-spec 已在 `docs/changes/bugfix-426-midrun-message-steering/specs/cli/spec.md`
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新（启动命令、测试命令均无变化）
- [x] `docs/SPEC_GUIDE.md`：无需更新（本 unit 未改文档体系本身）

三份契约层 delta-spec 均已由 worker 写入 `docs/changes/bugfix-426-midrun-message-steering/specs/`，orchestrator 收尾时按 §7.0 归并入正式 `docs/specs/<包>/spec.md`。

---

## 澄清 Q&A

本轮无澄清问题，开工前 30 分钟已完整阅读 incident.md + design.md 确认验收口径。

---

# Round 2 — 2026-06-24

> Review round: 2
> Reviewer: bugfix-426-reviewer
> 验收对象: unit/bugfix-426 完整 unit（含 M4 #140 修复）

## Verdict

**pass**

**Highest Required Action**: pass

**Issues**: blocking=0, major=0, minor=0

---

## 开工报信 / 澄清 Q&A

本轮已读懂验收口径（incident.md + design.md M4 决策5/6），重点：
- M4 气泡滚动：steer 回复出现在排于 steer 消息之后的新气泡 B；旧气泡 A 干净收尾（completed）；
- #140 回归验证：run 收尾瞬间 steer → 不黑屏不超时，新气泡流式可见；
- Round 1 已覆盖的 Scenario（steer 消费到当前 run 下一轮 / 不掐工具 / FIFO 保序 / 空闲开新 run / SDK 复用 / IM+CLI）继承 Round 1 结论，本轮重走核心旅程并关注气泡行为。

无澄清疑问。

---

## 覆盖表（按 incident.md Requirement / Scenario 结构）

### Requirement: 运行中发送的消息在当前 run 的下一轮被带进上下文

#### Scenario: 工具循环中途发消息，下一轮即被消费

| 字段 | 内容 |
|---|---|
| 期望来源 | incident.md §目标行为与验收, WHEN + THEN |
| 验证方式 | IM 旅程J2（conv `c546e8f1`）：bash sleep 8 任务，t+4s 发 steer STEER_MARKER_426_R2 |
| 证据 | 气泡 B `[68e3d114]` content="STEER_MARKER_426_R2"，delivery_status=completed；时序：用户消息 07:49:56 → steer 07:50:00 → 气泡 B completed 07:50:26。Agent 在同一 run 的下一轮回复了 steer 标记 |
| 结果 | **pass** |
| 备注 | 继承 Round 1 pass；本轮重走确认 steer 消息成功在当前 run 下一轮被消费 |

#### Scenario: 不掐断正在执行的工具

| 字段 | 内容 |
|---|---|
| 期望来源 | incident.md §目标行为，GIVEN 工具正在执行 THEN 照常跑完 |
| 验证方式 | 旅程J2：气泡 A `[6f4b391b]` 的 tool_calls 记录 bash sleep 8，duration=25798ms，exit_code=0 |
| 证据 | 气泡 A delivery_status=completed，工具正常完成；steer 消息在工具完成后的下一轮才被消费 |
| 结果 | **pass** |
| 备注 | 旧气泡保留完整工具执行记录，未被强行中断 |

#### Scenario: 一个 run 内连发多条，按序全注入

| 字段 | 内容 |
|---|---|
| 期望来源 | incident.md Q3 FIFO 按序全注入 |
| 验证方式 | 旅程J5（conv `c546e8f1`）：bash sleep 10 → t+3s 发 FIFO_ALPHA_426 → t+5s 发 FIFO_BETA_426 |
| 证据 | 气泡 B `[db73e9db]` content="已提及 FIFO_ALPHA_426 与 FIFO_BETA_426。"，delivery_status=completed；ALPHA 在第13条，BETA 第14条，回复气泡 B 第15条，顺序正确 |
| 结果 | **pass** |
| 备注 | 两条 steer 消息按 FIFO 顺序（ALPHA 先 BETA 后）全部注入，agent 回复中同时引用两个标记 |

#### Scenario: 空闲时发消息仍正常开新 run

| 字段 | 内容 |
|---|---|
| 期望来源 | incident.md §目标行为，空闲态照常 submit 新 run |
| 验证方式 | 旅程J1（conv `c546e8f1`）：空闲时发「请用一句话回复：IDLE_BASELINE_OK_426」 |
| 证据 | `[c74bebf6]` agent content="IDLE_BASELINE_OK_426"，delivery_status=completed；消息 1 用户 + 消息 2 agent 回复，正常新 run |
| 结果 | **pass** |

### Requirement: 注入能力恢复为 SDK 内核级 affordance，consumer 统一复用

#### Scenario: 任一 agent.sdk consumer 复用同一注入能力

| 字段 | 内容 |
|---|---|
| 期望来源 | incident.md Q4，SDK 内核级能力 |
| 验证方式 | 实现层契约（非用户面 Scenario）——继承 Round 1 结论；IM 旅程走通证明 SDK steer=True 能力可用 |
| 证据 | Round 1 全测试树 2759 passed；本轮 IM 旅程 steer 全程通过 |
| 结果 | **pass** |
| 备注 | 此 Scenario 主要是实现层契约；用户可观察结果体现在 IM/CLI 两端旅程 |

### Requirement: IM 与 CLI 两端均恢复该能力

#### Scenario: IM 聊天运行中 steer

| 字段 | 内容 |
|---|---|
| 期望来源 | incident.md §目标行为，IM 聊天 steer 恢复 |
| 验证方式 | 旅程J2+J4+J5 （conv `c546e8f1`，ephemeral IM 54936，真 Gateway 进程） |
| 证据 | 全部 7 条 agent 消息 delivery_status=completed；steer 回复均出现在 steer 消息之后的新气泡；气泡 A（工具执行）均干净收尾 |
| 结果 | **pass** |

#### Scenario: CLI REPL 运行中 steer

| 字段 | 内容 |
|---|---|
| 期望来源 | incident.md §目标行为，CLI REPL steer 恢复 |
| 验证方式 | 继承 Round 1 pass（CLI 旅程由 Round 1 走过，M4 无 CLI 改动，Round 1 CLI steer 已通过） |
| 证据 | Round 1 CLI 旅程：pexpect 终端输出 CLI_STEER_MARKER_426_V2；LLM session 证明注入同 run |
| 结果 | **pass** |
| 备注 | M4 仅改动 agent.core loop/run_control/registry 和 gateway relay，CLI M2 改动不在本 milestone；Round 1 已覆盖 |

---

## M4 专项验收（#140 气泡滚动，本轮新增）

### Scenario: steer 回复排在 steer 消息之后的新气泡（M4 决策6，任意时刻 steer）

| 字段 | 内容 |
|---|---|
| 期望来源 | design.md M4 milestone 退出标准：回复出现在排于 steer 消息之后的新气泡 B 里、不续写旧气泡；旧气泡完成态 |
| 验证方式 | 旅程J2（mid-loop steer）+ 旅程J4（收尾窗口 steer #140 复现）+ 旅程J5（FIFO 连发） |
| 证据（J2 mid-loop）| 消息时序：[3]用户 07:49:56 → [4]气泡A completed 07:49:56 → [5]steer 07:50:00 → [6]气泡B completed 07:50:26。气泡 B 排在 steer 之后，A 干净 completed |
| 证据（J4 收尾窗口） | 消息时序：[7]用户 07:51:17 → [8]气泡A completed 07:51:17 → [9]steer 07:51:27 → [10]气泡B completed 07:51:41。无 relay.failed；A delivery_status=completed（非 failed）；B 包含 TERMINAL_WINDOW_STEER_426 |
| 证据（全局）| 全部 7 条 agent 消息 delivery_status 均为 completed；gateway log 零 relay.failed 事件 |
| 结果 | **pass** |

### Scenario: steer 消费前 in-flight 工具批次仍属旧气泡（不掐工具）

| 字段 | 内容 |
|---|---|
| 期望来源 | design.md M4 退出标准：steer 消费前 in-flight 工具批次仍属旧气泡（不掐工具）|
| 验证方式 | 旅程J2 气泡 A `[6f4b391b]` 工具详情 |
| 证据 | 气泡 A tool_calls=[{name:bash, command:sleep 8, duration_ms:25798, exit_code:0}]，工具在 A 中完整记录；steer 回复在 B 中（B 无 tool_calls） |
| 结果 | **pass** |

### Scenario: #140 回归验证（收尾窗口 steer → 新气泡流式，不超时不黑屏）

| 字段 | 内容 |
|---|---|
| 期望来源 | design.md §#140 缺陷，M4 退出标准：收尾窗口 steer → 后续工具与回复全程流式可见，不超时不黑屏 |
| 验证方式 | 旅程J4：sleep 12 任务（t=0），t=10s 发 steer（接近收尾），等 40s 后查询 |
| 证据 | 气泡 A `[a7d638e1]` delivery_status=completed；气泡 B `[9990b7bb]` delivery_status=completed，content="TERMINAL_WINDOW_STEER_426"；完成于 07:51:41（steer 后 ~14s）；gateway log 无 relay.failed；全程 7 条 agent 消息均 completed |
| 结果 | **pass** |
| 备注 | #140 旧行为：气泡 A relay.failed（120s 超时），黑屏 6 分钟。修后：A completed，B completed，14s 完成 |

---

## 复现验证（Round 2）

**旅程 J1（空闲态基线）**
- 07:48:55 发「IDLE_BASELINE_OK_426」→ 07:48:55 agent 回复「IDLE_BASELINE_OK_426」，delivery_status=completed
- **pass**：空闲态行为与现状一致

**旅程 J2（工具循环中途 steer + 气泡滚动）**
- 07:49:56 发 sleep 8 任务 → 气泡 A `[6f4b391b]` 创建
- 07:50:00（t+4s）发 steer（工具执行中途）
- 07:50:26 气泡 B `[68e3d114]` 出现，content=STEER_MARKER_426_R2，排在 steer 之后
- A completed（工具记录完整），B completed，零 relay.failed
- **pass**

**旅程 J4（#140 收尾窗口 steer 回归）**
- 07:51:17 发 sleep 12 任务 → 气泡 A `[a7d638e1]` 创建
- 07:51:27（t+10s，接近收尾）发 steer
- 07:51:41 气泡 B `[9990b7bb]` 出现，content=TERMINAL_WINDOW_STEER_426，排在 steer 之后
- A completed（sleep 12，duration=21727ms），B completed，零 relay.failed
- **pass**：#140 修复有效

**旅程 J5（FIFO 连发多条）**
- 07:52:49 发 sleep 10 任务 → 气泡 A `[8dbbf83e]` 创建
- 07:52:52 发 FIFO_ALPHA_426；07:52:54 发 FIFO_BETA_426
- 07:53:06 气泡 B `[db73e9db]`：「已提及 FIFO_ALPHA_426 与 FIFO_BETA_426。」
- 两条 steer 按序全注入，agent 一并回复，零乱序
- **pass**

---

## User Journeys Exercised（Round 2）

| Journey | 覆盖 Scenario |
|---|---|
| J1 空闲态基线 | 空闲时发消息仍正常开新 run |
| J2 工具循环中途 steer | 工具循环中途发消息下一轮即被消费；不掐工具；M4 气泡滚动（新气泡排在 steer 后）|
| J4 收尾窗口 steer（#140）| #140 回归验证；M4 气泡滚动；旧气泡 A completed 非 failed |
| J5 FIFO 连发多条 | 一个 run 内连发多条按序全注入；M4 气泡滚动 |

---

## 回归检查

全部 7 条 agent 消息 delivery_status 均为 **completed**，零 relay.failed。gateway log 两行均为正常启动信息，无异常。与 Round 1 相比：Round 1 没有验证气泡排序，本轮补充并通过。

---

## Side Findings

无。

---

## 上层文档同步

- [x] `SPEC.md`：无需更新（M4 不改跨包职责和依赖方向）
- [x] `docs/specs/kernel/spec.md`：**需要更新**（M4 追加：正常 steer 留同一 run、injection_consumed 信号事件）；delta-spec 已在 `docs/changes/bugfix-426-midrun-message-steering/specs/kernel/spec.md`，orchestrator 收尾归并时写入
- [x] `docs/specs/gateway/spec.md`：**需要更新**（M4 追加：steer 回复在新气泡、旧气泡干净收尾、不超时不黑屏）；delta-spec 已在 `docs/changes/bugfix-426-midrun-message-steering/specs/gateway/spec.md`，orchestrator 收尾归并时写入
- [x] `docs/specs/cli/spec.md`：无新增（M4 无 CLI 改动，Round 1 delta-spec 已涵盖）
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新
- [x] `docs/SPEC_GUIDE.md`：无需更新

---

# Round 3 — 2026-06-24

> Review round: 3（Fast-lane 复验）
> Reviewer: bugfix-426-reviewer
> 验收对象: unit/bugfix-426，Fix 轮 60e4a3da（V2 _roll_bubble 重构 + V3 连发守卫）

## Verdict

**pass**

**Highest Required Action**: pass

**Issues**: blocking=0, major=0, minor=0

---

## Fast-lane 说明

复用上轮（Round 2）上下文。Fix 轮改动范围：gateway 气泡代码重构（V2 抽 `_roll_bubble` 原语，三处气泡滚动复用同一函数）+ V3 连发多 steer 守卫（per-run `rolling` 重入锁 + 空 message_id 窄窗守卫）+ 内核终态覆盖（代码级边角）。

验收焦点两点：
1. V2 重构未回归常见路径（单条 steer → 新气泡排在 steer 之后、旧气泡干净收尾）
2. V3 连发两 steer → 两条均注入、无僵尸气泡、无重复 completed、无漏气泡

---

## 覆盖表（继承 Round 2，更新 Fast-lane 复验行）

Round 2 所有 Scenario 保持 pass，本轮只更新以下两行：

### Scenario: 工具循环中途发消息，下一轮即被消费（V2 重构回归验证）

| 字段 | 内容 |
|---|---|
| 期望来源 | incident.md §目标行为；V2 重构不改用户可观察行为 |
| 验证方式 | R3-J1（conv `2ea0ea3d`，ephemeral IM 63156）：bash sleep 8 → t+4s 发 V2_SINGLE_STEER_MARKER |
| 证据 | 气泡 A `[7436805c]` completed（tc=1，工具完整）；steer `[d7abb223]` 排在 A 之后；气泡 B `[b3bfaba9]` completed，content="V2_SINGLE_STEER_MARKER"；全程零 relay.failed |
| 结果 | **pass** |
| 备注 | V2 _roll_bubble 重构未回归常见单条 steer 路径 |

### Scenario: 一个 run 内连发多条，按序全注入（V3 连发守卫）

| 字段 | 内容 |
|---|---|
| 期望来源 | incident.md Q3 FIFO 按序全注入；V3 守卫防止多 steer 产生僵尸/重复气泡 |
| 验证方式 | R3-J2（conv `2ea0ea3d`）：bash sleep 10 → t+3s 发 V3_STEER_ALPHA_426 → t+5s 发 V3_STEER_BETA_426 |
| 证据 | 气泡 A `[1b05a080]` completed（tc=1）；steer ALPHA `[50c39d9d]`、BETA `[ff239e53]` 排在 A 之后；气泡 B `[bf6b7c77]` completed，content 包含「V3_BASE_DONE + V3_STEER_ALPHA_426 + V3_STEER_BETA_426」；agent_msgs=4 全 completed，零 relay.failed |
| 结果 | **pass** |
| 备注 | 两条连发 steer 同批次 drain，发一次 injection_consumed，产生一个气泡 B（包含两标记）——这是正确 FIFO 行为，非缺陷。V3 守卫（per-run rolling 锁）保证无重复 completed、无僵尸气泡 |

---

## 旅程证据（Round 3）

**R3-J1（V2 重构回归，单条 steer）**
- 10:14:24 发 sleep 8 任务 → 气泡 A `[7436805c]` 创建
- 10:14:28（t+4s）发 V2_SINGLE_STEER_MARKER
- 10:14:45 气泡 B `[b3bfaba9]` completed，content=V2_SINGLE_STEER_MARKER
- A completed，B completed，排序正确，零 relay.failed
- **pass**

**R3-J2（V3 连发两条 steer）**
- 10:15:22 发 sleep 10 任务 → 气泡 A `[1b05a080]` 创建
- 10:15:25（t+3s）发 ALPHA；10:15:27（t+5s）发 BETA
- 10:15:47 气泡 B `[bf6b7c77]` completed，content 同时包含 V3_BASE_DONE + ALPHA + BETA 三个标记
- agent_msgs=4（J1 的 A+B + J2 的 A+B），全 completed，gateway.log 零 relay.failed
- **pass**：无僵尸气泡、无重复 completed、无漏气泡

---

## Side Findings

无。
