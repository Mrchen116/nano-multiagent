# bugfix-404 复盘：实现视角泄漏进 spec 与 test

> 视角：把 SDD 全链路（spec → design → orchestrate → impl → review → verify）当审计对象，
> 从用户每条反馈倒推到真正引入问题的节点。
> 方法：每条结论用一手证据核实（session/subagent jsonl + 沉淀文档 + 代码），不采信二手。
> 范围：本文聚焦 PR #91 评审阶段挖出的一组**同源**问题——长青契约层混入实现层、新增测试从实现投影。
> 不是 bugfix-404 的全单复盘（功能侧 #8/#79 的反复另见 design.md Changelog）。
> 作者：PR 评审阶段的复盘会话（既是发现者也已落地部分修复，相关处显式标注，不掩饰利益相关）。

## 0. 用户的核心期望 vs 实际

用户期望：契约层 `docs/specs/<包>/spec.md` 是**对外行为契约**（消费者可观察），测试有**长期回归价值**。
实际：bugfix-404 把一批**单测断言**（`runs_registry.submit 被调用`、`log_error("...")`）写进了长青
契约层；新增测试里有一批 mock-assert-called 的实现锁，还有一个**测一条生产 no-op 路径**的测试。
两者被用户在 PR 评审时逐一发现。

## 时间线与 jsonl 索引

### A. 关键 session

| session（前8位） | 角色 | 说明 |
|---|---|---|
| `5fa2cac1` | 主驱动会话（spec→design→orchestrate→验收） | 2138 行，0 sidechain；写 fix/incident/design/delta，归并 gateway+im canonical |
| `5fa2cac1/subagents/agent-a00409e2…`、`agent-a100da64…` | 实施 worker（M1/M3） | 写 deliver_notification / passes_workspace_root / relay 测试，写 kernel canonical |
| `1ea0e22e`（本会话） | PR 评审 + 收敛 + 本复盘 | 发现两问题、收敛 spec、收敛测试、改 skill |

### B. 关键 commit

| commit | 内容 | 归属 |
|---|---|---|
| `3c085d10` | `docs(bugfix-404/M1/R3)`：spec.md 补后台通知契约 | **M1 worker C3**——实现层内容进 kernel canonical 的源头 |
| `2cb68255` | 收敛契约层——删实现层泄漏 | 本会话修复 |
| `a3bb75ef` | 收敛测试——删 no-op/实现锁，补真集成 | 本会话修复 |

---

## P0 — 长青契约层混入单测断言

### 用户反馈 / 症状
> 「你这个pr在spec中插入了很多实现层的东西，而不是真正的spec」
> 「会导致长青spec膨胀」

### 一手证据
canonical `docs/specs/kernel/spec.md` 收敛前那段（commit 前）的 Scenario THEN：
- `runs_registry.submit 以 origin=BACKGROUND_TASK、workspace_root=... 被调用`（内部函数调用断言）
- `runs_registry.submit 不被调用；记录一条 debug 日志`
- `异常被捕获并以 log_error("background_task_notify_delivery_failed", ...) 记录`

对照 design-author 产的 **delta**（`5fa2cac1` 写入，`docs/changes/.../specs/kernel/spec.md`）：
THEN 是「内核对该 session 发起 `origin=BACKGROUND_TASK` 的新 run，session JSONL 可见该 turn」——
**消费者可观察、干净**（脚本检测 `impl_leak=False`）。

偏离 commit：`3c085d10`，scope `bugfix-404/M1/R3`，即 **M1 worker 的 C3 文档阶段**。引入了
`background_task_notify_delivery_failed` 等实现符号。

orchestrator §7.0 归并（`5fa2cac1` 后段）：只 `Edit` 了 `gateway` + `im` 两个 canonical，
**没有碰 kernel**——因为 kernel canonical 已被 worker 在 C3 写过，归并者看到「已有内容」就跳过了。

### 根因落点
**早期推断（已撤回）**：本会话先从产物反推，判定「§7.0 归并把 delta 改写成了实现层」。
被证据证伪——`5fa2cac1` 的 §7.0 段根本没写 kernel canonical（只 gateway+im），delta 本身也是干净的。
撤回该判断。

**真根因（两段叠加）**：
1. **M1 worker 在 C3 越界写 kernel canonical**（`3c085d10`），且凭**实现视角**投影——它脑子里是
   `submit`/`_session_manager`/`log_error`，写出来的契约就带这些。`change-impl-worker` 当时**没有
   「worker 不碰 canonical/delta」的硬规则**，范围边界（§0.7）也没明确拦住 spec 文件。
2. **orchestrator §7.0 漏复核**：「据 delta 机械合并」遇到「canonical 那节已被 worker 写过」时，
   没有重新据 delta 覆盖，而是默认接受了 worker 的实现层版本。

### 这一步本该怎样（已落地）
- `change-impl-worker` §0.13（新增，commit 待提）：契约层 canonical+delta **永不由 worker 写**，
  C3 只补 progress.md/tasks.md。
- `change-orchestrator` §7.0③（已改）：对每个有 delta 的包**无条件据 delta 重新归并**，
  「canonical 已有内容不是跳过的理由」；并加**实现层红线**（THEN 禁内部函数名/类名/日志字符串/
  `X 被调用` 断言）。
- `change-design-author` §4.8（已改）：同一条红线落在源头。

---

## P1 — 新增测试从「实现」投影，而非从「可观察行为」

### 用户反馈 / 症状
> 「你再到worktree检查下，新增的那些测试是不是真正有长期价值的」

审查结果：一批 mock-assert-called 实现锁（`deliver_notification_submits` 断言 `submit.assert_called_once`、
`passes_workspace_root_to_registry` 断言注册传参），以及 `test_bg_subscriber_relay_reaches_outbound_channel`
——**测一条生产 no-op 路径**。

### 一手证据（worker 写测试时的原话，subagent transcript）
**`passes_workspace_root_to_registry`**（`agent-a00409e2…`）：
> 「R2 的测试需要测试 BashTool 在调用 `register_bash` 时已经透传了 `ctx.repo_root`。我需要写一个对
> BashTool 的集成级别测试，**使用 mock 验证注册调用携带了 workspace_root**」

→ 测试目标被定成「验证某个调用携带了某参数」（实现细节），自称「集成级别」却用 mock。

**`deliver_notification_submits`**（同 worker）：写测试前的 reasoning 全是实现纠结——
> 「`session_manager` 是私有属性 `_session_manager`。`_deliver_notification` 只接受 `runs_registry`
> 参数……**根据 design.md Decision 2，我们需要通过 `runs_registry._session_manager` 访问**」

→ 脑子里全是「`_deliver_notification` 怎么调 `_session_manager`/`submit`」，测试就 mock 这些内部件
断言调用。**测试是它刚设计的实现机制的镜像。**

**`relay_reaches_outbound_channel`**（同 worker）：
> 「现在把**完整的端到端** subscriber→outbound relay 测试放到 `test_background_session_events.py`
> 里，**不依赖 InboundPipeline**」

→ worker **自以为**写端到端，但为「不依赖 InboundPipeline」mock 了上游 kernel、用 fake channel
自搭链路，测的是它当时以为通、实际是 no-op 的 `outbound_router→channel.sent`。

**no-op 时序**：relay 测试在 M3/R1 写（当时以为 channel.sent 是真路径）；M3/R5 才发现
`outbound_router.send_text` 对 web_relay 是 no-op、把生产改走 `send_agent_message`——**改了生产，
却留下了测 no-op 路径的旧测试**。

### 根因落点
**worker 在 C1 红测阶段，从「我刚写/将写的实现」投影测试，而不是从「消费者可观察行为」投影。**
实现里有什么内部件（`submit`/`_session_manager`/`outbound_router`），测试就断言什么内部件。
两个助推：
1. **design 决策下沉到实现机制**：worker 明说「根据 design.md Decision 2，需要通过
   `runs_registry._session_manager` 访问」。design 把内部访问路径写进决策，worker 照着测，自然测出实现锁。
2. **实现修正后没回溯审视测试**：R5 改了生产路径，没有「实现路径变了，旧测试还测得对吗」这一步，
   留下测 no-op 的死测试。

`change-impl-worker` 当时**没有 C1「从可观察行为投影测试」的纪律**，也**没有「后续 roadpoint 改了
实现路径要回头审视旧测试」的约束**。

### 这一步本该怎样
- **（已落地）** 本会话已删 `relay`（no-op）+ 两个 mock 实现锁，补
  `test_background_bash_carries_non_default_workspace_root_to_submit`——真 shell 端到端断言非默认
  workspace_root 透传到投递（commit `a3bb75ef`）。
- **（待补 skill）** `change-impl-worker` C1 纪律：测试 THEN 从消费者/系统可观察结果投影
  （真入口/真链路），mock 只用于隔离不可控外部，不得把「内部函数被调用/参数被传递」当测试目标。
- **（待补 skill）** `change-impl-worker`：roadpoint 改动了某条实现路径（如 R5 发现 no-op 改路径）时，
  必须回头审视测旧路径的测试是否已失真。

---

## 综述：实现视角把一切产物拉向实现细节

P0 与 P1 不是两个问题，是**同一个根因的两种表现**：

> **worker 的工作视角是实现视角；无论让它投影成 spec 还是投影成 test，出来的都带实现印记。**
> 写契约 → `submit 被调用`；写测试 → `assert submit.assert_called_once`。两者同形、同源。

design 还在两端都补了一刀：把内部访问机制（`_session_manager`）写进 Decision，spec 和 test 都照着
这个机制走。

这条根因之所以能成立、能漏到 PR，是因为 SDD 流程在**两个关口都缺一道「实现层红线」机械检查**：
契约层归并时没拦（§7.0），C1 测试投影时没拦（impl-worker）。原则（「主语=消费者」）一直在，但太抽象，
拦不住「`submit 被调用` 看起来也像个行为」。

### 一句话
把「实现视角」挡在 spec 和 test 之外，需要两件事：**禁 worker 碰契约层**（产物分工）+ **在契约归并
和 C1 测试两个关口都装可机械自查的实现层红线**（禁函数名/类名/日志字符串/`X 被调用`）。前者已落地，
后者 spec 侧已落地、测试侧待补。

---

## 附：按 skill 的改进清单

> 标注 ✅ 已落地（本会话已改 SKILL.md，commit 待提）/ ⬜ 待补。

### change-design-author（来源 P0、P1）
- ✅ §4.8 加**实现层红线**：delta 的 Scenario THEN 只写消费者可观察结果，禁内部函数名/类名/日志字符串/
  `X 被调用` 断言。
- ⬜ Decision 措辞约束：design 决策描述「对外契约 + 选哪条路」，避免把内部访问机制（如
  `_session_manager` 访问）写成决策正文——它会同时污染 worker 的 spec 与 test 投影（P1 助推 1）。

### change-orchestrator（来源 P0）
- ✅ §7.0③：对每个有 delta 的包**无条件据 delta 重新归并** canonical，「已有内容不是跳过的理由」。
- ✅ §7.0③：合并时守**实现层红线**，delta 若混入也在此滤掉。
- ✅ §7.0：fix 路径（lite/post-PR）无 delta 时由 orchestrator 据代码自己补 delta 再归并。

### change-impl-worker（来源 P0、P1）
- ✅ §0.13：契约层 canonical+delta **永不由 worker 写**，C3 只补 progress.md/tasks.md。
- ⬜ **C1 测试投影纪律**：测试 THEN 从消费者/系统可观察结果投影（真入口/真链路）；mock 只隔离不可控
  外部，**不得把「内部函数被调用/参数被传递」当测试目标**（P1 直接根因）。
- ⬜ **实现路径变更回溯**：某 roadpoint 改了一条实现路径时，回头审视测旧路径的测试是否失真
  （P1 的 relay no-op 死测试）。

### 跨 skill（结构性）
- 「实现层红线」现已落在 design-author（源头）+ orchestrator（归并关口）。若再补 impl-worker 的 C1，
  红线就覆盖了 spec 与 test 的全部生成点——这是把「实现视角泄漏」根治的最小完备集。

### 两个最高杠杆项
1. **change-impl-worker §0.13（禁 worker 碰契约层）** ✅——直接掐断 P0 主因。
2. **change-impl-worker C1 测试投影纪律** ⬜——直接掐断 P1 主因，且与 §0.13 同源，是本复盘唯一还没落地的核心改动。
