# bugfix-660 — 回归验证

> 对齐: [incident.md](incident.md)
> Round 1 · 2026-10-25 · 独立 full 产品验收
> Validation snapshot: `5b09dbe82 → 60514ca8fbade2d58f11d10d50cf8f1d7772b65f`

## Verdict

**fail**。实际隔离 Node 离线期间收到 P 停用意图，重启后无法完成生命周期确认，P 一直 Stopping，Agent 详情持续 Loading，E 新消息未得到回复。本轮没有修改实现。主控已接收阻塞现场；后续修复需追加 Round，不能覆盖本轮。

## 环境与入口

独立浏览器会话 `review660`，实际 Web `http://127.0.0.1:64960`，专用 nano 测试主人，1200×732 viewport。核实 `/tmp/nano-bugfix-660/.e2e-daily.json` 的 P/E/Q+PA 阵容、E 配置页的 gpt-6.1-sol/high/Codex 及 Task/Cron 功能。普通 Node PID 14735，DSH PID 14777。最初 frontend dist 陈旧，caller 重建为 `index-BlzeBvd6.js` 后重新加载，以下决定性生命周期结论均来自正确 bundle；旧 bundle 缺按钮不作为产品缺陷。

证据目录：`/Users/czj/.codex/reports/bugfix-660/product/`。本轮读取 incident/design/runbook、共同体验标准及 feat-657 acceptance。原生 UI 未改，沿用 feat-657 已有 iOS 证据，不把本轮 Web 结论写成 iOS 实测。

## 复现与回归旅程

1. Web E 私聊 `c_8231uioz` 发出 10 分钟每 2 秒采样请求；P 私聊 `c_leyuwvzw` 发出主采样+子 Agent 请求。真实模型创建 E Task `tg_de1ac579`、P Task `tg_69be940e`，并实际写入项目下 `review660-E.log`、`review660-P.log`、`review660-P-child.log`。P Work 可展开真实工具输入、结果和子执行；模型最初因 `/tmp` 与 `/private/tmp` 字面校验失败，随后自行纠正，不将失败的首次 Job 当成功。
2. **15:31:31 UTC 从 P Work 页 Disable**。UI 收敛 Disabled、Main Agent Idle、执行轮次 Interrupted，Enable again 可用。P 主日志停于 27 行（末行 15:31:31）；E 从 30 行继续到 53 行，DSH PID 14777 未变。证据 `p-disabled.png`、`p-sampling.log`、`e-sampling.log`、`disabled-snapshot.txt`。子日志在点击前已停于 10 行，不能用它证明这次 disable 清理了活跃子执行。
3. P Task 详情显示 **Paused**，提供 Resume progress。15:32:14 Web Enable again 后仍 Paused / Assignee execution Idle，P 主日志仍 27 行，E 持续增长。15:32:29 明确点击 Resume progress 后 Task 变 Advancing，P Work 新增 Execution turn 23:32:29 / Running，观察到 task_graph、read、bash 等 6 个真实工具调用。这证明旧任务没有随 enable 自动恢复，而真人恢复能触发执行；未将日志重新增长冒充已观察事实。证据 `task-paused.png`、`task-after-enable.txt`、`task-explicit-resume-running.png`、`resume-work.txt`。
4. 使用交接命令停止本隔离 Node；Web显示 offline / read-only / activity unknown。离线时点击 P Disable，显示 **Stopping / Disable requested; waiting for the node to confirm**，按钮禁用，没有虚报 Disabled。证据 `offline-stop-pending.png`、`offline-pending.txt`。
5. **15:34:06 重启同配置 Node**，新 PID 20460 / ordinary host 20466，按 runbook 从 state 更新 `.gateway.pid`。超过一分钟后 P 仍 Stopping，detail 为 Loading agent；`.gateway-state.json` 是 ready:true / connected:false，gateway log 反复 `RelayDeliveryError: IM rejected the request: lifecycle_process_stale`。15:34:43 向 E 发独立新消息要求 `E-RECONNECT-660`，截至现场交接没有回复。证据 `restart-stuck.png`、`restart-gateway-state.json`、`restart-gateway-errors.log`、`reconnected-final.txt`。保留现场供 caller 修复，未读实现定位根因。

## 场景覆盖

| 来源 / 必验结果 | 本轮实际证据 | 结果 |
|---|---|---|
| incident 共享运行时并行工作：A停用，B执行及host不变 | P主采样停止、E日志持续增长、PID14777不变 | pass（主执行及B隔离） |
| 同场景：A全部受管子Agent/Bash/terminal清理 | 主Bash已证；子Job在操作前已结束，terminal未实测 | inconclusive（不可用原生fixture替代产品观察） |
| 现有停用体验：状态、任务暂停、enable不恢复旧Task | Disabled/Interrupted、Paused、enable后仍Paused | pass |
| 同场景：真人明确恢复旧Task | Resume progress→Advancing→新真实执行轮次 | pass |
| 同场景：清理超时/失败未确认与重试 | 纯离线只产生pending，尚未完成隔离超时注入 | inconclusive |
| 重连与重启：离线停用意图先应用、B正常恢复 | 重启后P长期Stopping，详情Loading，E无新回复 | fail |
| 所有Agent停用：历史、Work、配置、模型管理可用 | 单P停用Work历史可读；all-disabled尚未执行，受重启阻塞 | inconclusive |
| 多个普通Agent：共享host、PA既有隔离 | 操作前后ordinary PID14777不变；布局边界原生证据由caller补充 | pass（本次可观察PID部分） |

## 体验判断与问题

正确 bundle 的页面把身份/设备置于标题，独立 Disabled 状态与 Enable again 紧邻主操作；绿色设备在线点没有替代生命周期文字。停用后历史工具记录保持可读，Interrupted 标签能解释执行结束。任务详情的 Paused 与 Resume progress 将重新启用和旧任务恢复分开。离线画面同时说明“等待确认”和“活动未知”，没有让用户误以为清理已完成。上述体验证据仅覆盖实际观察状态，不替代未观察的 retry 和 all-disabled 管理。

| ID | 严重度 | 事实与用户影响 |
|---|---|---|
| R1-1 | major / blocking | 节点离线时停用 P，重启后生命周期无法收敛、详情不能加载、E不能完成新请求；用户无法完成停用后安全恢复，其他Agent正常恢复要求也未达成。 |

## 自动化与上层文档

本角色未新增测试；可信 native/契约测试由 caller 汇总，不能覆盖 R1-1 的实际失败。

- [x] SPEC.md：需归并 shared ordinary + scoped PA，取消逐普通Agent/control host旧架构；caller负责。
- [x] docs/specs/gateway/service-lifecycle.md：需归并本unit delta；caller负责。
- [x] AGENTS.md / CLAUDE.md：无需更新。
- [x] docs/specs/CONTRIBUTING.md：无需更新。

## Round 2 · 2026-10-25 · targeted

Validation snapshot: `5b09dbe82 → f10168318bf578e48c0bcea09463a7a2613ed568`。独立 Web `review660r2`，同一 daily 身份、IM、模型和审核；前端保留正确 bundle。R1 主 Bash 停用/B 连续性/同 PID、enable 不恢复旧 Task、明确 Resume 开始真实轮次的证据未被本轮 identity 修复失效，直接保留。

**Verdict: fail**。R1-1 已修复；本轮发现 **R2-1 major / blocking：停用状态与恢复后的 Work Running 冲突**，caller 已接手。其余新增必验结果如下。

### 重连阻塞复验

15:37:35 启用 P 后停止隔离 Node；15:37:47 在 Web 离线状态停用 P，显示 Stopping/等待确认。15:37:51 用同配置启动 Node21393/ordinary host21399，state ready:true/connected:true；Web P 收敛 Disabled/Enable again，详情可正常加载，P 采样仍27行。E 新消息（15:38:34）实际收到公开 `E-R2-RESTART-OK`（15:39）。因此 R1-1 closed；没有把 API ready 当作模型成功。证据 `r2-offline-intent.png`、`r2-reconnected.txt`、`r2-e-reply.txt`。

但 P Work 仍显示 Main Agent Running，旧 Execution turn 23:32:29 / 6 tool calls / Running；重新导航刷新仍然如此，顶部同时明确 Disabled。这使用户无法判断停用是否真的停止，属于本功能直接涉及的状态反馈缺陷。P 日志未增加不能替代修复界面。证据 `r2-reconnected-disabled.png`、`r2-reloaded-disabled.txt`。caller 已确认需修复 cold Work 停止投影；本角色未查实现。

### 未确认与真实重试

15:38:52 对**本隔离 ordinary host21399**执行 SIGSTOP，随后 Web 停用 Q。页面显示 Stop unconfirmed、Retry stop、New work remains blocked，以及“Managed cleanup did not finish within the stop deadline.”；没有 Enabled 入口或假 Disabled。15:39:23 SIGCONT 同 PID，然后实际点击 Web Retry stop，Q 收敛 Disabled/Enable again，PID仍21399。证据 `r2-stop-unconfirmed.png`、`r2-timeout.txt`、`r2-retry-result.txt`、`r2-retry-disabled.png`。这是有意冻结共享进程的超时注入，**不**用它证明注入期间 B 连续性。

### 全部停用的管理与历史

15:40:19 停用 E，15:40:23 停用 PA，此时 P/E/Q/PA 全部 Disabled。真实 Web 完成：

- P Work 切换原生轨迹，成功读取历史 `a943501a-fbf1-4434-960f-53d6b082e7bd` 的 inbox/read/bash/subagent 等工具输入和结果；证据 `r2-all-disabled-native.png`、`r2-all-disabled-native.txt`。
- E Config 将 Description 保存为“660 全停用状态配置保存验证”，保存后 No changes，四个角色仍 Disabled；证据 `r2-config-saved.txt`。这是隔离环境普通配置测试增量。
- 主人菜单打开 Model services，显示 Online、既有 anthropic 服务及模型列表，Edit/Remove/Add service 可用；本轮没有修改凭据；证据 `r2-all-disabled-model-services.png`。
- P 聊天保留蓝杉660历史，输入区前明确 Not processing new messages / Messages are kept, but this Agent will not process them。发送停用态记录 `R2-P-DISABLED-MESSAGE` 后历史保存，未声称接手；证据 `r2-disabled-chat.png`、`r2-disabled-chat.txt`。

ordinary host21399 在超时恢复及全停用管理过程中保持。历史可读、配置可保存、模型设置可访问的功能结果 pass；Work 的准确活动状态仍被 R2-1 阻塞。

### 原生边界证据的范围澄清

caller 按 design M1 明确：真实 native child/grandchild/Bash/PTY owner 边界由 worker 的实际 DSH 进程夹具证明，reviewer 必验为 Web 停用/重试/启用/历史/旧任务/离线重启。R1 的 Web 主 Bash+Task+A/B 旅程证明真实用户入口；子日志先于点击停止的事实保留，不能宣称它证明活跃子树清理。实际 native 夹具只作为该边界补充，未冒充 Web 操作；最终验证汇总须引用 caller 的具体原生证据。

| 场景 | R2裁决 |
|---|---|
| 离线意图→重连/重启，B正常新工作 | pass，R1-1 closed |
| 未确认不虚报、重试、共享PID不变 | pass |
| 全停用后历史/配置/模型管理 | pass（活动状态准确性另列R2-1） |
| 停用后的Work状态一致性 | fail，R2-1 |
| R1已通过的主执行隔离与Task恢复规则 | retained pass |

## Round 3 · 2026-10-25 · final targeted

Validation snapshot: `5b09dbe82 → 6769c89cb5fc9e693b45b6a8d87f2d7a7b02e127`。本轮只新增 cold stop-history 投影修复；独立复验其失效范围，保留 R1/R2 已通过且未失效的入口、隔离、Task、重连、重试及管理证据。

### Verdict

**pass**。R1-1、R2-1 均 closed，0 个未解决 blocking/major。此结论按 design M1 的 reviewer Web 用户旅程范围，并结合明确分工的 native owner 边界测试；不声称每个原生 Job/PTY 类型都通过真实模型重跑。

15:42:53 在 P/E/Q/PA 四角色全部 Disabled 的状态下重启同一隔离 Node，得到 Node23117/ordinary host23122，ready:true/connected:true。真实 Web P Work 显示 Disabled + Main Agent Idle；原 23:32:29 的执行轮次变为 **23:32:29—23:33:29 / 6 tool calls / Interrupted**，原 23:28 轮次仍 Interrupted，早先 Completed 轮次保留。页面不再同时声称停用和正在执行，R2-1 closed。截图 `r3-disabled-interrupted.png` 已实际阅读，记录与状态层级清楚。

同一页面切入原生轨迹，历史 `a943501a-fbf1-4434-960f-53d6b082e7bd` 成功显示“已连接 · 实时更新 · 只读”与历史工具调用。四角色一直 Disabled，P/E/child 采样分别保持27/90/10行，host23122未因读取更换；证据 `r3-work.txt`、`r3-native-history.txt`、`r3-disabled-native.png`。这些产品观察证明历史可用与无可观察采样恢复；cold owner 未被创建的内部保证补充引用 `shared-cold-stop-green.log`（3 files / 16 tests pass），不单凭 UI 推断内部 handle 数量。

### 最终证据分工

- Web 产品入口与真实模型执行：本报告 R1 主 Bash A/B、Task暂停/显式恢复；R2 离线意图/重启/B新回复、实际Stop unconfirmed与Retry、全停用历史/配置/模型服务；R3 cold Work 投影与只读历史。
- Native owner 边界：`packages/dsh-integration/tests/agent-disable-native.test.ts` 对应 shared A/B child/grandchild/continuable/Bash/PTY 夹具，caller 汇总于 implementation.md §Shared A/B owner cleanup；实测日志 `/Users/czj/.codex/reports/bugfix-660/shared-native-isolation.log` 为1 pass /4 skipped的定向运行，完整后端覆盖另由caller汇总。它补充实现边界，不冒充独立Web观察。
- iOS：没有原生UI增量，依设计保留 feat-657 acceptance 的既有界面证据；本轮未声称新iOS体验实测。

| incident 必验目标 | 最终结果 |
|---|---|
| 共享运行时停用只影响目标，B继续，host不重启 | pass：R1真实Web/Bash/PID，native边界补充 |
| 清理未确认不虚报，重试可收敛 | pass：R2真实超时注入/重试/同PID |
| 现有入口、Task暂停、enable仅新工作、显式恢复旧Task | pass：R1真实Task与执行轮次 |
| 离线意图和重启持续生效，B正常恢复 | pass：R2复验R1-1，R3全停用重启 |
| 全停用历史、Work、配置、模型设置可用且状态准确 | pass：R2管理+R3状态修复 |
| 普通共享host与PA原边界 | pass：Web观察普通PID不变；原生边界证据补充 |

### 收尾状态

浏览器由reviewer关闭；隔离Node保留给caller收尾。最终为Node23117/ordinary host23122，四角色Disabled，E Description保留隔离配置保存验证文字；未修改生产、未外发、未提交代码。report_commit：无（按派发仅写regression.md，由caller统一提交）。

Native 最终补充：caller 确认最终 `6769c89cb` 的 `shared-cold-stop-green.log` 16项包含 `agent-disable-native.test.ts` 全7项及 PA lifecycle/trajectory。关键夹具名为 `drains A descendants, Bash and PTY while B continues in the same host, then enables A without restarting`（该文件第32行）：DSH root/child/grandchild/continuable、Bash真实进程树及PTY均为实际对象，断言A采样停止/B继续及enable后同PID；只有LLM stream hold为mock，不能称为真实模型子Agent验收。此最终运行覆盖最新cold-history修复后的边界。
