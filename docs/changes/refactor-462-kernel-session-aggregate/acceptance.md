# refactor-462 — 验收报告

> 对齐：`motivation.md` 的用户侧验收标准（不变性）  
> Round: 1  
> Date: 2026-07-13  
> Review mode: full

## Verdict

- **Verdict: fail**
- **Highest Required Action: fix-implementation**
- Issues: blocking 1 / major 3 / minor 0
- 第一轮禁止 `revise-design`；本轮所有问题均有公开产品入口的经验性证据，交回实现层修复。

## User Journeys Exercised

1. **Coding CLI 多轮与进程级恢复**
   - 真实入口：`python -m coding_cli.main --text ...`，本地真实 LLM `kimiCoding:K2.6`。
   - 首轮会话 `sess_7d79c18c134d46d9` 输出 `CLI462-R1`；新 CLI 进程使用 `--resume` 后准确回复 `CLI462-R1`。
2. **隔离 IM + Gateway 多轮、Gateway 重启与 `/stop`**
   - Runbook 栈使用 worktree 隔离配置、高位端口和独立 `tmux`；健康检查通过，未触碰主服务。
   - conversation `e5f1fd6f04044045ab61d2940096327c`：重启前写入 `IM462-RESTART`，只重启 Gateway 后仍准确回复该暗号。
   - conversation `51f207fb455a4b8c8d0b60ad6254313b`：长任务后发送 `/stop`，随后尝试继续，复现阻塞问题 ISSUE-1。
3. **公开 SDK 带外消息与 cold restart**
   - 轮间 append：下一轮准确回复 `OOB462-BETWEEN`。
   - Kernel 重启后首次操作为 append，再次重启恢复：准确回复 `COLD-BASE-462|COLD-OOB-462`。
   - active run append：第一轮真实输出 `8Kj5Np2Qw4Rt`，下一轮只能看到带外暗号，无法复述该 assistant 内容，复现 ISSUE-2。
4. **公开 SDK compact、重启与提示快照**
   - manual compact 后当前进程继续完成；再次构建 Kernel 后仍回复 `REPLAY-COMPACT-462`。
   - 同一窗口保持 `COMPACT-OLD-462` 符合预期；修改 `AGENTS.md` 并 manual compact 后，下一轮仍返回 OLD，复现 ISSUE-3。
   - `PromptSlots` seed 在 Kernel 重启前后均返回 `PROMPT-SEED-462`。
5. **公开 SDK as-of fork、独立演进与路径参数**
   - 源会话由 `FORK-A-462` 演进至 `FORK-B-462`；以 `msg_7d4ecf2708f85cf5` 为 fork 点后，分支看到 A，源会话看到 B；分支改为 C 后源会话仍为 B。
   - `workspace_root` 传公开签名允许的字符串时，`create_session` 成功但 `submit` 立即报错，复现 ISSUE-4。

## Reference Artifacts Reviewed

N/A。本 unit 无前端原型、视觉设计稿或 must-match reference contract；客户端界面也不在本 unit 变更范围。

## Issues

### ISSUE-1 — `/stop` 显示已停止，但原任务仍运行且后续消息长期阻塞

- **Severity:** blocking
- **Regression Relation:** direct
- **Recommended Action:** fix-implementation
- **Action Rationale:** 直接违反“中断或取消后继续会话”；用户收到成功确认后仍不能继续，是主路径不可用。
- **Reproduction:**
  1. 在隔离 IM/Gateway conversation `51f207fb455a4b8c8d0b60ad6254313b` 发送长任务。
  2. 任务进入 running 后发送 `/stop`。
  3. IM 返回 agent 消息 `已停止当前操作。`。
  4. 随后发送 `中断后继续，只回复 STOP-CONTINUE-OK。`，等待约 90 秒。
- **Expected:** 原任务终止，下一条消息正常运行并回复 `STOP-CONTINUE-OK`。
- **Observed:** 原 agent 消息仍为 `delivery_status=running`；后续用户消息停在 `sent`，无 agent 回复。
- **Corroborating public SDK evidence:** `interrupt(session_id)` 返回 active run id，但该 run 最终为 `completed` 且输出完整长回复；相同环境的 `cancel(run_id)` 能立即进入 `cancelled`，后续 turn 能完成。

### ISSUE-2 — active run 期间带外追加后，下一轮丢失刚持久化的 assistant 内容

- **Severity:** major
- **Regression Relation:** direct
- **Recommended Action:** fix-implementation
- **Action Rationale:** 违反带外消息与终止恢复要求中的完整可达历史；会话仍能跑，但上下文已不完整。
- **Reproduction:**
  1. 经公开 SDK 启动一轮，让真实模型随机生成用户输入中不存在的 12 位串。
  2. run 为 running 时调用公开 `append_message` 追加 `ACTIVE-OOB-462`。
  3. 第一轮真实 assistant 输出 `8Kj5Np2Qw4Rt`。
  4. 下一轮要求按 `上一条 assistant 精确输出|active 带外暗号` 回复。
- **Expected:** `8Kj5Np2Qw4Rt|ACTIVE-OOB-462`。
- **Observed:** `xK9mP2vL7nQ4|ACTIVE-OOB-462`；带外消息可见，但上一条 assistant 内容不可见。

### ISSUE-3 — manual compact 后工作区提示没有在压缩边界刷新

- **Severity:** major
- **Regression Relation:** direct
- **Recommended Action:** fix-implementation
- **Action Rationale:** 直接违反“会话内提示稳定且在压缩边界刷新”；用户会持续收到过期项目指令。
- **Reproduction:**
  1. 以 `AGENTS.md` marker `COMPACT-OLD-462` 创建会话，首轮返回 OLD。
  2. 将 marker 改为 `COMPACT-NEW-462`；同一窗口仍返回 OLD，符合冻结语义。
  3. 经公开 `Kernel.compact()` 完成 manual compact，再次询问当前 marker。
- **Expected:** `COMPACT-NEW-462`。
- **Observed:** `COMPACT-OLD-462`。
- **Control evidence:** compact 本身成功，会话能继续；重启后能从 compact 记录恢复既有暗号。问题集中在压缩边界的提示刷新。

### ISSUE-4 — `Kernel.submit` 无法接受公开签名声明的字符串 workspace 路径

- **Severity:** major
- **Regression Relation:** direct
- **Recommended Action:** fix-implementation
- **Action Rationale:** 本 unit 明确承诺 SDK 行为不变；合法公开参数导致同步异常，现有 SDK 消费者会直接中断。
- **Reproduction:** 使用同一个字符串 `workspace_root` 调用公开 `create_session` 和 `submit`。
- **Expected:** 两者都接受 `str | Path`，turn 被正常调度。
- **Observed:** `create_session` 成功；`submit` 抛出 `AttributeError: 'str' object has no attribute 'expanduser'`。

## 验收标准覆盖

### Requirement: 正常会话连续性保持不变 — 组内结论：pass

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| CLI 多轮对话与恢复 | `motivation.md` | Journey 1：真实 CLI `--text`，新进程 `--resume` | `sess_7d79c18c134d46d9`；两轮均输出 `CLI462-R1` | pass | 已验证进程级恢复，不只是在同一 Kernel 内继续。 |
| IM/Gateway 多轮对话与重启恢复 | `motivation.md` + design Runbook | Journey 2：隔离真栈两轮；仅重启 Gateway 后同一 conversation 继续 | conversation `e5f1fd6f04044045ab61d2940096327c`；重启后输出 `IM462-RESTART` | pass | 用户无需重建会话。 |

### Requirement: 带外消息与终止恢复语义保持不变 — 组内结论：fail

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 带外追加进入下一轮上下文 | `motivation.md` | Journey 3：首轮完成后经公开 `append_message`，再提交下一轮 | `between_turn_1='ACK-BASE'`；`between_turn_2='OOB462-BETWEEN'` | pass | 轮间 append 正常；active append 的额外回归见 ISSUE-2。 |
| 重启后首次操作就是带外追加 | `motivation.md` | Journey 3：K1 两轮→close；K2 首操作 append→close；K3 恢复并提交 | `k3_resume='COLD-BASE-462|COLD-OOB-462'` | pass | 从用户可见历史确认旧上下文与新消息都可达。 |
| 中断或取消后继续会话 | `motivation.md` | Journey 2：真栈 `/stop` 后立即继续；公开 SDK interrupt/cancel 对照 | `/stop` 已确认但原消息仍 running，后续消息约 90 秒无回复 | fail | ISSUE-1，主路径阻塞。取消 API 对照可继续，不能抵消 interrupt 与 `/stop` 的失败。 |

### Requirement: 长会话与分支语义保持不变 — 组内结论：pass

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 上下文压缩后透明继续 | `motivation.md` | Journey 4：真实 LLM manual compact，当前进程继续；关闭并重建 Kernel 后恢复 | `compacted=manual`；重启后输出 `REPLAY-COMPACT-462` | pass | compact 与 replay 主路径成立；提示边界刷新单列在下一 Requirement。 |
| 从指定消息 fork 会话 | `motivation.md` | Journey 5：以指定 assistant message fork，分别推进源/分支 | fork 点 `msg_7d4ecf2708f85cf5`；fork=A、source=B；分支改 C 后 source 仍 B | pass | 指定点继承与独立演进均通过。 |

### Requirement: 会话级提示与文件上下文语义保持不变 — 组内结论：fail

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 会话内提示稳定且在压缩边界刷新 | `motivation.md` | Journey 4：同窗修改 `AGENTS.md`、manual compact、下一轮重读；另测 PromptSlots restart | 同窗 OLD（符合预期）；compact 后仍 OLD（期望 NEW）；PromptSlots 重启前后均 `PROMPT-SEED-462` | fail | ISSUE-3。稳定与 seed 恢复通过，但压缩边界刷新失败，因此 Scenario 整体失败。 |

## Side Findings

- N/A。未发现与本 unit 可接受性无关且需要另立 issue 的 blocking/major 问题。

## 上层文档同步

- [x] `SPEC.md`（跨包顶点架构）：**已在本 unit diff 中更新；最终合入前需由 orchestrator 按修复后的真实行为复核**。
- [x] `docs/specs/kernel/`（长青行为契约层）：**`context-persistence.md` 已在本 unit diff 中更新；最终合入前需由 orchestrator 对照修复结果收口**。
- [x] `AGENTS.md` / `CLAUDE.md`：**无需更新**；本 unit 不改变产品启动与协作约定。
- [x] `docs/SPEC_GUIDE.md`：**无需更新**；本 unit 不改变文档体系。

## Recommended Next Step

按 ISSUE-1 → ISSUE-4 进入 `fix-implementation`，其中先修 `/stop` 假成功与 session 阻塞，再修 active append live-history、manual compact prompt refresh、字符串 workspace 参数。修复后进行 targeted re-review，但由于 ISSUE-1 涉及真栈终止恢复，复验必须重新启动隔离 Gateway/IM 并真实走 `/stop` → 下一条消息。
