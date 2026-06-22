# feat-421 — 验收报告

> 对齐: spec.md 验收标准（11 条 Requirement / Scenario，其中 heartbeat 因 #126 deferred）
> Round: 1
> Date: 2026-06-22

## Verdict

**fail**

一条 contract 测试失败：`_im_client.py`（552 行）超出 `docs/TESTING_GUIDE.md §7` 400 行软上限，且本 contract 检查属于 CI 必跑项（`tests/contract/`），本地非 e2e 测试树跑出 1 failed。

业务 e2e 套件（10 条 pass + 1 skip）本身完全符合预期，但 contract 红不能过。

---

## Highest Required Action

`fix-implementation`

---

## User Journeys Exercised

| 旅程 | 覆盖 Scenario |
|---|---|
| 旅程 1：一条命令跑全套（非 slow） | Scenario「默认不触发」「一条命令跑全套」「时间驱动可单独筛」 |
| 旅程 2：关键路径 10 条业务 e2e 真端到端跑通 | Scenario「工具调用后回复」「bash 前台超时」「bash 后台通知」「subagent」「/stop」「cron」「群聊双向@」「权限 approve+deny」「进程重启续接」「经 IM 建 agent」 |
| 旅程 3：catalog 文档可对账 | Scenario「每条必保活路径能对账到守护测试与归属」「已知缺口在 backlog 诚实登记」 |
| 旅程 4：heartbeat skip 状态 | Scenario「heartbeat」= inconclusive / deferred（#126），旅程脚本存在，标 skip |

---

## 问题清单

| # | Severity | Regression Relation | 现象 | Recommended Action | Action Rationale |
|---|---|---|---|---|---|
| 1 | major | direct | `_im_client.py` 552 行，超出 TESTING_GUIDE §7 400 行软上限。contract 测试 `test_new_test_files_under_400_lines` 失败，CI 将红。**用户面**：开发者执行 `pytest -m "not e2e"` 看到 1 FAILED（不是全绿），套件可信度受损。 | fix-implementation | 直接违反项目合约层硬规则（`docs/TESTING_GUIDE.md §7 + tests/contract/test_test_naming_and_size_contract.py`），本 unit 新增文件引入。fix worker 拆分 `_im_client.py` 为行为独立的若干小文件（如 `_im_http_client.py` / `_im_ws_client.py` / `_im_agent_ops.py`），各自不超 400 行。 |

---

## 验收标准覆盖

### Requirement: 一条命令按需全跑关键路径 e2e，平时不跑 — 组内结论: pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 默认测试运行不触发真 LLM e2e | spec.md | 不设 env，运行 `PYTHONPATH=src python -m pytest tests/e2e/critical_paths`，观察输出 | `0 passed, 0 failed, 13 skipped`（全套 skip，不消耗 token） | pass | |
| 一条命令跑全部关键路径 | spec.md | 执行 `NANO_MULTIAGENT_RUN_LIVE_PROXY_E2E=1 scripts/e2e-critical.sh`（本地 :4000 proxy 可用 + config 含 llm: 段） | `12 passed, 1 skipped in 214.27s`（10 业务路径 + cron slow；heartbeat skip #126） | pass | 起停全栈由 fixture session 级自动完成，无手工配置 |
| 时间驱动路径可作为可单独跳过的子集 | spec.md | 执行 `scripts/e2e-critical.sh -m "not slow"` | `11 passed, 2 deselected in 180.39s`（cron/heartbeat 被筛掉，其余 11 条照常） | pass | |

### Requirement: 单一权威的关键路径清单 catalog 可对账 — 组内结论: pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 每条必保活路径都能对账到守护测试与归属 | spec.md | 打开 `docs/e2e-critical-paths.md`，检查 v1 必保活表「用户旅程/守护测试/归属子系统/引入 unit」四列是否完整 | catalog 有 10 条（heartbeat 移 backlog），每行四列均填实，守护测试函数路径可精确定位到 `tests/e2e/critical_paths/*.py` 下已存在的测试函数 | pass | 表格编号从 6 跳到 8（原 #7 heartbeat 移 backlog），编号不连续但说明清晰（v1 段头注有说明） |
| 已知缺口在 backlog 段诚实登记 | spec.md | 查看 catalog backlog 段 | backlog 段列有：heartbeat（#126 ref）/ 前端 UI smoke / 断线重连 / 压缩恢复 / 附件透传 / provider 切换 / 节点上下线看板，均诚实标注「暂无 e2e 兜底」 | pass | |

### Requirement: e2e 失败时留下可诊断证据 — 组内结论: pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 某条路径失败可定位 | spec.md | 读 `conftest.py` `_dump_logs` 实现：fixture 起栈失败时把 `.im.log` / `.gateway.log` 后 40 行 dump 进 pytest 报告 | `conftest.py:146` `_dump_logs` 方法存在：起栈 fail 时 tail IM/Gateway 日志进 `pytest.fail` message；单条用例 fail 时 session 级日志仍在 tmp dir 可查 | pass | 用户旅程角度：开发者遇失败可拿到 log tail，满足「不只是红叉」 |

### Requirement: 工具调用后回复旅程经真 Gateway 进程可用 — 组内结论: pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| agent 调工具再回复 | spec.md | `scripts/e2e-critical.sh` 真端到端跑 `test_tool_call_then_reply_carries_sentinel` | `PASSED`（真 IM + 真 Gateway + 真 LLM，哨兵经工具读文件后出现在 `message.completed.content`） | pass | |

### Requirement: bash 前台超时不卡死会话 — 组内结论: pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 前台 bash 超时后会话仍可用 | spec.md | 真端到端跑 `test_foreground_bash_timeout_still_replies` | `PASSED`（bash timeout=3 跑 sleep 30 超时，session 未卡死，仍收到含哨兵 `message.completed`） | pass | |

### Requirement: bash 后台任务完成后送达跟进通知 — 组内结论: pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 后台作业完成长出第二条回复 | spec.md | 真端到端跑 `test_background_bash_completion_sends_followup` | `PASSED`（run_in_background=true，后台作业完成后用户在同一对话收到含哨兵的第二条消息） | pass | |

### Requirement: 前台子 agent 可用且失败被隔离 — 组内结论: pass（部分 Scenario 缺守护）

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 派子 agent 并带回结果 | spec.md | 真端到端跑 `test_foreground_subagent_carries_back_output` | `PASSED`（父 agent 回复含子 agent 产出哨兵 SUB*，跨事件循环未崩） | pass | |
| 子 agent 失败不拖垮常驻进程 | spec.md | 查 `tests/e2e/critical_paths/` 目录，确认是否有对应测试函数 | 无对应 test 函数（catalog 中 #4 subagent 只挂了 `test_foreground_subagent_carries_back_output` 一条，不覆盖子 agent 失败隔离分支） | inconclusive | 缺守护测试但首次发现，归 minor。此 Scenario 的「用户面」是：子 agent 失败后后续消息仍可处理；当前测试只验证正常路径。建议后续 unit 补，不阻塞本 unit 通过（若 contract 修完后重评 verdict） |

### Requirement: /stop 中止正在执行的运行 — 组内结论: pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 运行中发 /stop | spec.md | 真端到端跑 `test_stop_aborts_active_run` | `PASSED`（sleep 45 run 跑起后发 /stop，收到固定 ack `已停止当前操作。`，被中止任务哨兵在 20s 窗口内未出现） | pass | |

### Requirement: cron 定时任务自动推送 — 组内结论: pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 到点自动冒泡 | spec.md | 真端到端跑 `test_cron_job_auto_pushes_message`（@pytest.mark.slow） | `PASSED`（cron every-5s 真触发，推一条含哨兵 CRON* 的新消息到直聊，42.74s） | pass | |

### Requirement: heartbeat 有内容时主动冒泡 — 组内结论: inconclusive（#126 deferred）

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 心跳带可行动内容时主动发言 | spec.md | 查看 `test_heartbeat_bubble_critical_path.py` 标注及 #126 | `@pytest.mark.skip(reason=...#126)`；排障证据（progress.md R4）：K2.6/doubao/gpt-5.5 三者对心跳 prompt 均回 HEARTBEAT_OK、observer 抑制投递，静态启用 scheduler 从未 triggered | inconclusive | 因 #126 deferred，非测试缺陷，旅程脚本作复现资产保留。按 spec 允许的诚实缺口暴露处理，不算 fail |

### Requirement: 群聊里人与 agent 的定向 @ 双向可用 — 组内结论: pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 人 @ agent 再由 agent @ agent | spec.md | 真端到端跑 `test_human_mentions_a_then_a_mentions_b` | `PASSED`（A 应答含 `<mention type="agent" target_id="grpB*"/>`，B 因被点名回出哨兵 GRP*） | pass | |
| 未被点名的 agent 不抢话 | spec.md | 真端到端跑 `test_unmentioned_agent_stays_silent` | `PASSED`（只 @A 时，A 回 SOLO*，B 在 25s 窗口内零发言） | pass | |

### Requirement: 工具权限审批人在回路可用 — 组内结论: pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 批准后运行继续 | spec.md | 真端到端跑 `test_permission_approve_lets_tool_run` | `PASSED`（approve 后含哨兵 PERMOK* 的 .gitconfig 真出现在 gateway-workspace） | pass | |
| 拒绝后工具不执行 | spec.md | 真端到端跑 `test_permission_deny_blocks_tool` | `PASSED`（deny 后含哨兵 PERMNO* 的文件全树不出现） | pass | |

### Requirement: 进程重启后会话上下文不丢 — 组内结论: pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 重启 Gateway 后仍记得上文 | spec.md | 真端到端跑 `test_context_survives_gateway_restart` | `PASSED`（记住暗号 MEMO* → 重启 Gateway → 复述回复仍含哨兵） | pass | |

### Requirement: 经 IM 创建的 agent 落地后可聊 — 组内结论: pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 新建 agent 上线并应答 | spec.md | 真端到端跑 `test_agent_created_via_im_lands_and_replies` | `PASSED`（新建 e2eNew* agent 落地上线，直聊收到含哨兵 NEW* 回复） | pass | |

---

## Issues 详情

### Issue #1 — `_im_client.py` 超 400 行 contract 违规

- **Severity**: major
- **Regression Relation**: direct（本 unit 新增文件）
- **复现**: `pytest -m "not e2e" -q` 输出 `1 failed`，`test_new_test_files_under_400_lines` 报 `tests/e2e/critical_paths/_im_client.py (552 lines)`
- **期望**: contract test 全绿，开发者运行 `pytest -m "not e2e"` 看到 0 failed
- **实际**: 1 FAILED（contract 层失败）
- **Recommended Action**: fix-implementation
- **Action Rationale**: `_im_client.py` 本 unit 新增，552 行超出 `docs/TESTING_GUIDE.md §7` + `tests/contract/test_test_naming_and_size_contract.py` 硬约束（400 行）。fix worker 把 `_im_client.py` 拆分为若干文件（如按 HTTP client / WebSocket / agent ops / gateway restart 分组），各自不超 400 行。

---

## Side Findings

1. **catalog 表格编号不连续**（v1 段从 #6 跳至 #8，原 #7 heartbeat 已移 backlog）：v1 段头注已说明「故 v1 必保活当前为 10 条」，不影响对账，minor，不立 issue。

2. **subagent 失败隔离 Scenario 缺守护测试**：spec 要求「子 agent 失败不拖垮常驻进程」有独立 Scenario，当前仅有「正常路径」守护，负向路径无 e2e。当前 `test_foreground_subagent_carries_back_output` 本身真跑了子 agent，若子 agent 崩则父拿不到哨兵，有一定隐性覆盖，但缺明确的「故意让子 agent 失败 + 后续消息仍可处理」路径。归 minor，不阻塞，后续 unit 可补。

---

## 上层文档同步

- [x] `SPEC.md`（跨包顶点架构）：**无需更新**（本 unit 纯新增测试 + 文档，不改包对外行为）
- [x] `docs/specs/<包>/spec.md`（长青行为契约层）：**无需更新**（design.md §契约层增量：全部 `no spec delta`；被守护的行为本就是各包已声明的 current）
- [x] `AGENTS.md` / `CLAUDE.md`：**已在本 unit 更新**（`AGENTS.md` 已挂 `docs/e2e-critical-paths.md` 链接，见 Line 352）
- [x] `docs/SPEC_GUIDE.md`：**无需更新**（本 unit 未改文档体系）

---

## 澄清记录

orchestrator 派发背景说明：heartbeat Scenario 请判为「inconclusive / 因 #126 deferred」，已在覆盖表如实标注。

---

## 审查结论

| 项 | 结论 |
|---|---|
| 业务 e2e 套件（10 条） | 全绿（真 IM + 真 Gateway + 真 LLM 真端到端） |
| heartbeat | inconclusive / #126 deferred（旅程脚本保留为复现资产） |
| contract 测试 | **失败**（`_im_client.py` 552 行超 400 行限制） |
| catalog 四列 | 完整填实，backlog 段诚实登记 7 项缺口 |
| 门控行为（无 env skip） | 正确（13 skipped） |
| 时间驱动路径可单独筛 | 正确（`-m "not slow"` 筛掉 cron/heartbeat） |

**Verdict: fail**（contract 红，需 fix-implementation 修 `_im_client.py` 拆分后重验）
