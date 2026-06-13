# bugfix-404: PA 后台任务完成通知丢失 + worktree gateway workspace 隔离失效

## Relations

- Closes: #8
- Closes: #79
- Related: bugfix-348（per-workspace session scoping 的来源）、#64（同家族：scoping 后链路漏传 workspace_root，已闭）、feat-337（后台任务通知功能的引入 unit）

## 原始报告

> 修#8

> 顺带把#79也一个unit中修了，在不同milestone

### 缺陷一：GitHub issue #8（2026-05-14 立项，原话关键句）

> 用户让 agent 执行 `sleep 60`（带 `run_in_background: true`），agent 第一轮正常回复"已在后台启动"。60 秒后 kernel 生成了第二条回复"Ja，完成了"，但前端始终收不到。
>
> 根因：Gateway 与 Kernel 之间的 SSE 订阅是**一次性**的：Gateway 订阅 Kernel 的 `GET /sessions/{id}/stream`，消费完 user run（R1）的所有事件后，在见到 `run_status: completed` 时执行 `break`，关闭 SSE 连接。

2026-06-11 在 main (fbebec3f) 复验（见 issue #8 评论）：

> 复现：IM 直聊让 Arch 用 bash `run_in_background=true` 执行 `sleep 60 && echo BG_DONE_ISSUE8`。
> - 第一轮正常：agent 回复「后台任务已启动」，task b5247ec5c574ffd99 启动
> - 后台任务 16:22 实际完成（output 文件含 BG_DONE_ISSUE8）
> - **完成 5 分钟后**：session JSONL（sess_a7f3ecb1eb6ee545）里没有 task-notification turn、没有第二个 run，IM 也没有第二条回复
>
> 与原 issue 不同的是：refactor-387 后 Gateway 进程内持有内核、且有 background_session_events.py 订阅器，原「SSE 订阅关闭」根因已不存在；现在是**完成通知根本没注入 kernel session**（background_tasks 通知链路在进程内架构下断了），需重新定位。

### 缺陷二：GitHub issue #79（2026-06-08 立项，原话关键句）

> `scripts/e2e-up.sh` 在 worktree 内起的 gateway,实际读写**主仓** workspace,而非 worktree 隔离副本——违反 AGENTS.md「worktree 内服务必须隔离、不污染主仓」的约定。
>
> - `.gateway-config.yaml` 里 Arch 的 `workspace_root` **已正确**改写为 `.../.worktrees/unit-feat-394/.gateway-workspace/Arch`
> - 但 IM `GET /im/v1/agents` 广播该 agent 的 `workspace_root = /Users/czj/nano-assistant/workspace/Arch`(**主仓**),且 `workspace_is_default: true`
> - heartbeat run 的 system prompt 里 workspace 也是主仓 `workspace/Arch` → 读到主仓那份 `HEARTBEAT.md`(含一条 `every: 15s` 测试配置),worktree gateway 因此持续打 heartbeat 并烧 token

2026-06-11 在 main (fbebec3f) 复验（见 issue #79 评论）：

> - 新建 worktree `.worktrees/verify-79` 跑 `scripts/e2e-up.sh`（含 feat-393 的清旧 DB / 同步 node.user_id 改动）
> - `.gateway-config.yaml` 三个 agent 的 workspace_root 均已正确改写为 `.worktrees/verify-79/.gateway-workspace/<agent_id>`
> - 但 worktree IM `GET /im/v1/agents` 广播仍为主仓路径 `/Users/czj/nano-assistant/workspace/<agent_id>`，且 `workspace_is_default: true`
> - e2e IM 是全新 DB，排除旧 profile 复用

## 澄清记录

- Q1: 修复范围——只验 bash 后台任务的完成通知，还是把后台 subagent（`agent` 工具 `run_in_background=true`）的完成通知一并纳入验收？
  A(原话): 一并
  Agent 解读: bash 与后台 subagent 走同一条 `_deliver_notification` 链路，修复与验证两者都覆盖。

- Q2: （#79 并入）unit 组织方式
  A(原话): 顺带把#79也一个unit中修了，在不同milestone
  Agent 解读: 两个缺陷在同一 unit（bugfix-404）内修，各占独立 milestone；跨多 milestone 触发 lite→full 升档（本文档由 fix.md 升为 incident.md）。

- Q3: workspace_root 的两个数据源（本地 config YAML vs IM 配置中心）冲突时，谁是权威？（Agent 推荐：首次注册以本地 config 为种子写入 IM，之后 IM 为权威、UI 可编辑下发）
  A(原话): 那IM中如果改了某个agent的workspace_root，gateway把里面的东西搬迁过去？
  Agent 解读: 用户没有直接接受推荐，而是追问"UI 改路径后旧数据怎么办"。Agent 答复现状无搬迁逻辑（改路径=指向新目录、旧数据原地留下），并建议搬迁不进本 unit。

- Q4: （承接 Q3）是否保留"UI 编辑 workspace_root"能力？
  A(原话): 我觉得要不就不支持在UI改目录了吧，新建好了就定好了
  Agent 解读: 产品决策——workspace_root 在 agent 创建时一次性确定，此后不可经 IM UI 修改（UI 只读展示）。两数据源优先级冲突随之消解：本地 config / 创建时输入是唯一来源，IM 仅展示。数据搬迁能力不做（也不再需要）。

## 现象与复现

### 缺陷一：后台任务完成通知丢失（#8）

**现象**：PA 产品下，agent 启动的后台任务（bash `run_in_background=true`）完成后，agent 永远不会回发结果。用户只看到第一条"已启动"回复，之后无下文。无任何错误提示、无日志——通知静默消失。

**复现**（2026-06-11 在 main fbebec3f 实测，必现）：

1. 起主仓 IM + Gateway（多 agent，各自独立 workspace_root，如 `~/nano-assistant/workspace/Arch`）
2. IM 直聊让 Arch 执行：bash `run_in_background=true` 跑 `sleep 60 && echo BG_DONE_ISSUE8`
3. 第一轮正常：agent 回复「后台任务已启动」（task `b5247ec5c574ffd99`）
4. 任务实际完成（output 文件 `.nano/background-tasks/<sess>/<task>.output` 含 `BG_DONE_ISSUE8`）
5. 完成 5 分钟后：session JSONL（`sess_a7f3ecb1eb6ee545`）里**没有 task-notification turn、没有第二个 run**，IM 没有第二条回复

### 缺陷二：worktree gateway workspace 隔离失效（#79）

**现象**：worktree 内经 `scripts/e2e-up.sh` 起的 gateway，尽管 config 副本的 `workspace_root` 已正确指向 worktree，实际 runtime（session、heartbeat、agent 工作区读写）全部落在**主仓** workspace；IM 广播的 agent `workspace_root` 也是主仓路径。后果：worktree e2e 读写主仓数据（如主仓 `HEARTBEAT.md` 的测试配置导致 worktree gateway 持续烧 token），分支行为污染用户主实例。

**复现**（2026-06-11 在 main fbebec3f 实测，必现）：

1. 新建 worktree，跑 `scripts/e2e-up.sh`（它会正确改写 `.gateway-config.yaml` 的 workspace_root 为 worktree 路径，并 pre-mkdir）
2. 登录 worktree 的 ephemeral IM，`GET /im/v1/agents`
3. 期望：`workspace_root = <worktree>/.gateway-workspace/<agent_id>`；实际：`/Users/czj/nano-assistant/workspace/<agent_id>`（主仓），`workspace_is_default: true`
4. e2e IM 为全新 DB，排除旧 profile 复用

## 影响范围

- **缺陷一**：PA 全部后台任务（bash 与后台 subagent 同链路）的完成结果永远到不了用户。Coding CLI 不受影响——其 workspace_root 恰好命中 session store 默认定位。无数据损坏。
- **缺陷二**：所有 worktree e2e 场景的隔离承诺失效：worktree gateway 读写主仓 agent 工作区（HEARTBEAT.md、memory、session 数据），可能把分支行为/测试数据施加到用户主实例；反向也成立（主仓数据干扰 worktree 验收结果，feat-394 验收期间即因此误烧 token）。主仓正常使用场景下不可见（持久化 config 的路径恰好等于 managed default）。
- 两缺陷同属"workspace_root 在某条链路上丢失/被覆盖"家族，但断点互不相同、互不依赖，可独立修复验证。

## 根因分析（RCA）

### 缺陷一：通知投递断在"parent 空闲起新 run"路径

**直接根因链**（完成检测本身是好的，断在投递最后一步）：

1. bash 监控线程正常检测到进程退出 → `registry.complete` → `_NotifyingStore.update` → `_deliver_notification`（`src/agent/platform/background_tasks/wiring.py:126-157`）触发
2. parent session 空闲（后台任务的典型情形），走 `runs_registry.submit(session_id=parent, parts=[notification], origin=BACKGROUND_TASK)` —— **没传 `workspace_root`**
3. `RunsRegistry.submit` 用裸 `SessionManager.get_session(session_id, workspace_root=None)` 校验 session 存在（`src/agent/core/runs/registry.py:322-326`）。bugfix-348 起 session 为 per-workspace scoped，PA 下 agent 的 session JSONL 在各自 workspace 内，`workspace_root=None` 定位不到 → `ValueError("session does not exist")`
4. 该 ValueError 被 `except ValueError: pass` 静默吞掉——这个兜底的本意是跳过"未注册到顶层 runs_registry 的 subagent session"，结果把真实投递失败也一并吞了，故全程无日志无症状
5. 信息丢失源头：`BackgroundTaskRecord`（`src/agent/core/background_tasks/models.py`）**没有 workspace_root 字段**——任务注册时就没把 parent session 的 workspace_root 存下来，投递时无从取

注：parent 忙时的 `inject_pending_message` 路径是纯内存操作、不需定位 JSONL，不受影响；只有"parent 空闲 → 起新 run"路径断了。

**为什么这种错能进来**：

- bugfix-348 把 session 改为 per-workspace scoped 时，未排查所有 `runs_registry.submit` 调用方是否都补传了 workspace_root（#64 是同一家族：stream 链路漏传，已修）。后台通知这条链路因 `except ValueError: pass`（refactor-360/M4 43f0a120 引入）静默失败，无症状可暴露。
- 测试盲区：现有后台任务测试都在默认 workspace 下跑（CLI 视角），没有"PA 多 agent / 非默认 workspace_root 下后台完成通知送达"的回归测试。
- 原 issue #8（2026-05-14）记录的是旧架构（Gateway↔Kernel SSE 订阅一次性关闭）的根因；refactor-387 进程内化顺带消灭了旧根因，但本缺陷（bugfix-348 引入）在其下层潜伏，旧根因消失后才暴露为"当前的"断点。

**原始设计意图追溯**（feat-337-cc-background-subagents）：

- 意图：后台任务完成后**系统主动通知主会话**，不要求主 agent 盲查；通知以 `<task-notification>` XML 包裹的 user-role message 进入主会话；主 agent 把新信息综合后告诉用户。
- 修复必须保住的不变量：
  - parent 忙时 inject（不中断当前 turn）、闲时起新 run（`origin=BACKGROUND_TASK`）的双路径语义
  - 前台 budget 内完成不发通知（#19 的修复，`notified=is_foreground`）
  - 未注册的 subagent session 跳过通知**仍需保留**——但不能再用静默吞 ValueError 的方式把真实失败一起藏掉
  - 用户新输入优先于后台完成通知的优先级语义

**回归引入点**：bugfix-348（per-workspace session scoping）使 `_deliver_notification` 的无-workspace_root submit 从"能工作"变为"必失败"；`except ValueError: pass` 兜底（refactor-360/M4，43f0a120）使失败不可观察。两处叠加 = 静默丢通知。

### 缺陷二：注册时丢 workspace_root + 回拉时 IM mirror 覆盖本地 config

**直接根因链**（两步叠加）：

1. **注册时丢失**：Gateway 向 IM 发 `node.register` 帧时只带 agent id 列表——`"agents": [agent.agent_id for agent in self._agents]`（`src/personal_assistant/reporter/upstream_reporter.py:300`），**不带 workspace_root**。IM 第一次见到该 agent 时按空值建 profile，`normalize_workspace_root` 把空值落库为 managed default `~/nano-assistant/workspace/<agent_id>`（`src/IM/application/config_service.py:228-244`），`workspace_is_default=true`
2. **回拉时覆盖**：Gateway 的 `sync_agent` 从 IM 拉 config mirror（`GET /im/v1/agents/{id}/config?source=mirror`），**IM 值非空就赢过本地 YAML**（`src/personal_assistant/main.py:322-326`：`payload.get("workspace_root")` 非空 → 直接用，仅空值才回落本地 factory）。于是 e2e-up.sh 正确改写的 worktree 路径在 runtime 被 IM 的 managed default 覆盖

**为什么主仓用户没察觉**：主仓持久化 config 的 workspace_root 恰好就是 managed default 路径，"被覆盖成 default"与"用 config 值"结果相同，缺陷不可见；只有 config 指向非默认路径（worktree e2e）时才暴露。

**为什么这种错能进来**：

- "IM 是配置中心、Gateway 是 mirror 消费者"的模型本身成立（UI 改配置要能下发），但**首次注册的种子链路**没把本地 config 的 workspace_root 传上去——IM 凭空发明了一个 default，且 mirror-wins 规则没有区分"IM 里是用户设置的值"还是"IM 自己填充的占位 default"
- `main.py:2313-2314` 的注释已意识到 "workspace_root has two data sources (local YAML vs IM-synced value)"，但两源的优先级语义从未被明确定义和测试
- 测试盲区：没有"config workspace_root 指向非默认路径时，IM 广播/runtime 实际 workspace 与 config 一致"的回归测试；e2e 验收都在默认路径下跑

**原始设计意图追溯**：

- IM 配置中心模型（agent 配置 UI 可编辑、Gateway 同步消费）要求 IM 侧 profile 是 agent 配置的权威展示；`workspace_is_default` 字段的存在说明设计上**预期区分**"用户显式设置"与"managed default"
- 修复必须保住的不变量：
  - IM UI 编辑 agent 其余配置（system prompt、skills、tool_allowlist、features 等）后 Gateway 仍能同步到——配置中心模型对**非 workspace_root 字段**不变
  - Gateway 新建 agent 写回本地 config 的持久化行为
  - 主仓默认路径用户的现有行为完全不变
  - （Q4 产品决策使"UI 编辑 workspace_root 下发"不再是需保住的能力——该编辑入口本期移除）

## 修复方向

行级方案在 milestone 内定，此处只定高层方向。两缺陷独立，各占一个 milestone（Q2 用户要求）。

### M-notify（缺陷一，Closes #8）

- 让 workspace_root 随后台任务全程携带：任务注册时把 parent session 的 workspace_root 存进任务记录，`_deliver_notification` 起新 run 时透传给 `runs_registry.submit`
- 投递失败不再静默：保留"未注册 subagent session 跳过"的语义，但真实投递失败必须可观察（日志），不能再用裸 `except ValueError: pass` 一刀切吞掉
- 回归测试补盲区：非默认 workspace_root 下，bash 与后台 subagent（Q1：一并）完成通知必须送达 parent session、回发 IM，**并实时到达在线用户浏览器（不刷新即可见）**——验收终点是用户在前端真的看到，不是消息进了 IM 存储（这条终点口径在初版被写短了，见文末「后续发现」）

### M-workspace（缺陷二，Closes #79）

按 Q4 产品决策"workspace_root 创建时定死，UI 不可改"收敛：

- 创建即权威：agent 创建时（本地 config 启动注册 / IM 前端新建流程）确定 workspace_root，作为种子写入 IM profile——IM 不得再为已有真实值的 agent 凭空填 managed default
- 封死 workspace_root 的全部变更面（design 调研更正：前端输入框已是只读、HTTP update schema 本就不含该字段；真窟窿在 service 层 update 把 None 归一化为 managed default，任何一次配置编辑都会重置它——一并修复）
- Gateway `sync_agent` 回拉时 workspace_root 不再被 IM mirror 覆盖（来源唯一后两者必然一致，冲突路径删除）
- e2e 回归：worktree 内 `e2e-up.sh` 起的 gateway，IM 广播与 runtime 实际 workspace 均为 worktree 路径，主仓 workspace 零读写

## 后续发现：实时下发缺口（fix-realtime，2026-06-12）

M-notify 修好「通知送达 parent session 并回发 IM」后，PR 提交、round-1 验收判 pass。但人肉 reviewer 复测发现：后台通知虽已进入 IM 会话存储（刷新可见），**在线前端不刷新就不显示**。

根因：M3 让通知走 `agent.message → _handle_agent_message → create_message` 入口，只写 `message.sent/.delivered` 事件，没产生前端「新建气泡」所依赖的 `message.created` 实时事件；而前台回复经 EventBridge 产生该事件。两条入口的实时下发语义不一致。

复盘——为什么没早发现：**验收终点被悄悄降级了一格**。退出标准止于「回发 IM」（服务端消息可达），而非「用户不刷新就看到」（端到端可达）；unit 标题虽叫「端到端可达」，可操作的退出标准却退到了服务端那一步。round-1 reviewer 走旅程时刷新了页面，恰好跨过缺口。契约层当时也没有「消息实时下发」这条 requirement，verifier 无据可核。

修复（fix-realtime）：`_handle_agent_message` 的 user-target 消息改经 IM 内部统一的实时下发入口，一次性产生 `message.created`（带完整内容、`delivery_status=completed`，无空泡中间态）+ `message.completed`，经用户流 WebSocket 实时推送；幂等去重保留。对外行为契约见 `docs/specs/im/spec.md`「后台 agent 通知实时到达在线用户，无需刷新」。教训：凡「端到端 / 用户可达」类验收，退出标准必须落到用户可观察的最终态，禁止停在中间的服务端步骤。
