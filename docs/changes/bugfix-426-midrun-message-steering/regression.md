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
