# feat-657 — 验收报告

## Round 1 · 2026-10-25

Validation snapshot: `935510058d338866e2310f54c1804d6120eac51c`（701b6caa6 实现及最新 main 的 feat-658 文档）。独立 reviewer 使用 change-reviewer FULL；未修改实现或配置。caller 提供该源码构建的独立 daily 栈，`/tmp/nano-feat-657-final/.e2e-daily.json`，IM `http://127.0.0.1:58236`、Node `wt-nano-feat-657-final-43993`。模型与审核未降格：P/E/Q 为 gpt-6.1-sol/high/Codex，PA 为 gpt-6-astra/medium/Codex；E 配置页独立核实模型、effort、审批。UI 构建日志 `/tmp/nano-feat-657-web-build.log`；所用隔离身份为本轮测试 owner。

### Verdict

**fail**。重新启用后的新请求没有进入正常执行，阻塞“明确重新启用”。其余未完成结果明确记 inconclusive，不能用构建或 runtime 测试替代真实旅程。后续修复需另追加 Round，保留本轮记录。

### 用户旅程体验

真实 Web 从 Agents 列表进入 E 配置页：身份、设备标识、生命周期操作、状态、配置依次可读。修改名称为未保存草稿后点击页头 Disable，无确认弹窗，立即显示 Stopping 及尚未确认说明，随后 Disabled；名称草稿仍显示 Unsaved changes，侧栏仍为已保存名称，Discard changes 后原名称恢复。因此停用与配置保存独立，状态没有把设备在线等同于可工作。截图 `/tmp/nano-feat-657-review/disabled-draft.png`。

从 Work 页 Enable again 后显示 Enabled 和“Ready for new work; old tasks remain paused.”。由 Open chat 进入 E 私聊发出新请求，并在“研发日常”通过成员选择器明确提及 E；两条消息均真实进入历史，但截至 18:01 未收到回复，Work 仍 Idle / No work records。运行日志同期连续 `RpcError: Session binding conflict`；caller 已确认实际缺陷，交实现方修复。消息 ID 分别为 `b252333095b44b77abde21cfa404a536`（`c_gagnwnci`）及 `bcca180919d149548f3da8dc51ed255c`（`c_k5060q7l`）。失败证据 `/tmp/nano-feat-657-review/enable-new-message-no-reply.png`；此处只报告观察，不推断代码根因。

1440×1000、390×844、320×740 实际观察 Work：窄屏身份与操作自然分行，Disable 首屏可达，状态说明换行完整，工作记录/原生轨迹仍可切换，底部导航不遮挡主入口。桌面保持原紧凑身份页头与正文关系。截图 `work-1440-enabled.png`、`work-390-enabled.png`、`work-320-enabled.png` 均在 `/tmp/nano-feat-657-review/`。这证明所观察 enabled 状态的布局，不替代未观察的 offline/failed 状态。

### Reference Artifacts Reviewed

读取 spec.md、design.md（前端原型、Runbook、M1 退出标准）、prototype.html、current IM agents-nodes.md、worktree-runtime.md 及共同体验标准。

| Reference | Required contract | Actual evidence | Viewport / state | Conclusion |
|---|---|---|---|---|
| prototype.html / 身份→设备→开关 | 停用不等配置保存，首屏可达 | disabled-draft.png；work-*-enabled.png | 1440、390、320；enabled/disabled | match（已观察状态） |
| lifecycle 状态区 | stopping/disabled/offline pending/stop_unconfirmed；未确认不可启用 | 真正点击即 Stopping，随后 Disabled | desktop；正常停用 | inconclusive：offline/failed 尚待补证 |
| enable 后旧任务仍暂停、历史可读 | 新工作资格恢复且旧工作不自动运行 | enable-new-message-no-reply.png；E 私聊/群消息 | desktop/320 | deviation：新工作不能运行；旧任务/冷历史未完成 |
| iOS 三个独立页面 | 单一生命周期入口、短文案、动态字体、44pt | caller 集中验证原生客户端；待最终证据引用 | 原生三页 | inconclusive：待合并明确证据 |

### 问题清单

| # | 严重度 | 现象 | 处置 |
|---|---|---|---|
| R1-1 | major / blocking | E 空闲停用再启用后显示 Enabled，但新私聊与真实群提及均不执行；Work 无记录，runtime log 连续 Session binding conflict | caller 已接手修复；需新版本复验 |

### 验收标准覆盖

每行来源均为 spec.md 中同名 Scenario；必要平台约束来自 design.md 原型对齐契约。inconclusive 表示尚未取得该必验结果，不是失败根因推断。

| Requirement / Scenario | 验证方式与证据 | 结果 |
|---|---|---|
| 明确入口 / 从工作视图紧急停用 | 页头跨 Config/Work 保留；配置草稿场景已真实操作通过；有活动 Work 紧急停用尚待执行 | inconclusive |
| 明确入口 / 空闲 Agent 也能停用 | E idle：Disable→Stopping→Disabled；刷新/跨页状态保持；disabled-draft.png | pass |
| 全部受管执行 / 跨聊天、后代及后台工作一起停止 | 复用真实 OS/native tests：`/Users/czj/.codex/reports/feat-657-runtime-stop/evidence.md` §Validation 5，root/child/grandchild/continuable/Bash/PTY 进度停止；`/tmp/nano-feat657-stop-fix-test.log` 15 tests pass；产品跨聊天活动停止实证待补 | inconclusive |
| 全部受管执行 / 其他 Agent 不受连带中断 | 上述 native 证据含独立 host 持续写入；真实 daily 并行工作结果待 caller 补齐 | inconclusive |
| 自动机制 / 消息与自动任务触发 | 停用准入与旧代次 native 测试可复用；真实私聊/群聊停用态体验待执行 | inconclusive |
| 自动机制 / 重连、重启和重复操作 | caller 集中负责节点重启/重连，尚待证据 | inconclusive |
| 未确认 / 节点离线 | caller 集中负责，尚待证据 | inconclusive |
| 未确认 / 清理超时或失败 | native 测试证明 deadline 及清理失败不虚报成功；真实页面失败/重试尚待证据 | inconclusive |
| 重新启用 / 明确重新启用 | E Enable 后真实私聊、群提及均未执行，消息 ID 与截图见旅程 | fail |
| 重新启用 / 用户明确恢复旧任务 | 待 caller 实际指定恢复及其他任务保持暂停结果 | inconclusive |
| 权限与在线 / 非管理者与 Agent 自身不能改开关 | 待 caller nonowner API 与既有真实 HTTP/WS identity 契约证据 | inconclusive |
| 权限与在线 / 设备在线但 Agent 停用 | 页面设备在线圆点同时明确 Disabled，单独 Enable again；disabled-draft.png | pass |

### 范围补充

single-thread `feat657-single` 已由 caller 创建，真实 Web 私聊 `c_0a5458x0` 发送基线请求 `900567143f2943a1afbc9bc7a682347e`，未将请求受理或空白消息视为模型成功。global/PA/single-thread 完整停用和新工作恢复、全部停用后的控制与历史访问，均待补齐。

macOS DSH 不承诺 OS containment；原生证据中的 top-level PTY 不断生成后代导致 stop_unconfirmed 是用户接受的平台边界，未列为需求缺陷，也不允许据此虚报已停止或强制 Enable。

### 上层文档同步

- [x] SPEC.md：需要更新为每产品 Agent 独立 host；由 orchestrator 收尾核实。
- [x] docs/specs/gateway 与 docs/specs/im：需要归并本 unit delta；由 orchestrator 在最终修复验收后执行。
- [x] AGENTS.md / CLAUDE.md：无需更新。
- [x] docs/specs/CONTRIBUTING.md：无需更新。

### Round 1 追加观察（18:03）

single-thread S 的真实模型基线已收到公开回复 `0d6547c45509425d898a8b9fe10d2728`：“单会话运行基线 657”；截图 `/tmp/nano-feat-657-review/single-baseline.png`。从配置页 Disable 后立即收敛 Disabled，进入原私聊仍能读到基线历史。停用期间发送消息 `0071d52bc4274a218bc21114823c9b58` 保存成功，未产生模型回复。

**R1-2 · major / blocking**：停用 S 的私聊页仍只有绿色在线点与 Agent 标签，没有 Disabled、不会处理或等待管理者启用的说明；发送后也没有状态提示。用户必须离开聊天进入设置才能理解不回复原因。截图 `/tmp/nano-feat-657-review/single-disabled-chat.png`。这违反 spec“消息与自动任务触发”的“系统明确表达停用，不假装 Agent 已接手处理”，也使“设备在线但 Agent 停用”在聊天入口未兑现；不能用设置页已正确显示来覆盖当前聊天的缺失。此前该两项中仅设置页观察成立，**整体结果分别更新为 fail、fail**。已向 caller 报告，待修复与复验。

### Round 1 追加冷历史实证（18:04）

独立 reviewer 只读打开仍为 Disabled 的 P Work，看到已完成基线轮次、3 tool calls 与 12,267 context；切入“原生轨迹”成功加载 `7fc885fd-b79e-4266-bf25-1d6b1ffa7a7f`，显示“已连接 · 实时更新 · 只读”，能读 inbox check/read、send_message 及实际 sent 回执 `2aad59e43c29471eba94a643898cbd54`、最终回复。截图 `/tmp/nano-feat-657-review/p-disabled-native-history.png`。**停用后 Work 与原生历史可读的 UI 子结论 pass**；产品 host 没有被拉起的系统侧证据待 caller 补充，不从 UI 自行推断。

## Round 2 · 2026-10-25 · targeted（完成）

### Validation snapshot 与继承范围

执行 Web/后端源码 `e55e5285a2ee2ab9193ebdb94680585726441ce5`；caller 最终冻结 `a97c96f65`，额外变更为 iOS 首次空态通知挂载修复及其他 unit 文档，Web 与本轮后端源码未变。iOS 使用最终修复构建的真实截图与模拟器验证。独立全新 daily `/tmp/nano-feat-657-release-check/.e2e-daily.json`，IM `http://127.0.0.1:64018`，Node `wt-nano-feat-657-release-check-52895`；同一模板模型与 Codex 审批，未降格。追加 S `feat657-single`，模型 gpt-6.1-sol/high/Codex、single-thread；在真实配置页核实。

保留 Round 1 未失效的草稿独立保存语义、1440/390/320 Work 布局及真实 OS 后代/Bash/PTY 证据；本轮重新观察决定性修复结果、离线→重连与真实活动停止。原 iAB 本轮不可用，改用独立 Chrome 测试标签页；旧标签出现点击不产生请求的驱动问题，新专用标签正常，未据此给产品定缺陷。

### 新增真实旅程

1. **离线待确认→重连**：reviewer 看到 Q 设备 offline，页头 Stopping、“Disable requested; waiting for the node to confirm.”，主按钮禁用，Work 另有“活动状态未知”的只读说明。caller 重启该隔离 Node 后，reviewer 在 320×740 看到 Q Disabled、Enable again，未误报离线时已经停止。证据 `r2/q-offline-pending.png`、`r2/q-reconnected-disabled-320.png`。
2. **单会话完整周期**：S 历史中真实基线 `FEAT657-S-BASELINE` 保留；列表独立停用后聊天出现“Not processing new messages / Messages are kept, but this Agent will not process them.”。停用消息 `c684c26f788247fc93768ab8d5f34846` 保存；320 宽提示完整，位于输入区前，不阻挡历史和发送。重新启用后新请求 `c7885a1c33a744d483b3c7fadc10f5c1` 得到公开 `R2-S-NEW-OK`，未补回停用消息。证据 `r2/s-disabled-chat.png`、`r2/s-disabled-chat-320.png`、`r2/s-enabled-reply.png`。
3. **活动中 E 的 Work 停用与 P 连续性**：真实请求 `e663d14ce6454292819811356ff84a9e` 让 E 用 Bash 在自己的隔离 workspace 每秒追加计时 120 秒；reviewer 在 Work 看到 Main Agent Running、Bash Running，现场文件从 7 行增长。点击 Work 页 Disable，无确认弹窗，立即收敛 Disabled、整轮 Interrupted、Bash Call failed。请求时间 `10:27:42.131Z`，确认 `10:27:42.331Z`（200ms；这是本次现场观测，非一般 SLA）。文件停于 12 行、末行 `18:27:41+08:00`；18:28、重新启用及 18:29 再查仍相同。P 同时运行 sleep 25，在 E 停止确认后 2.023 秒公开回复 `R2-P-CONTINUES`，message `dfc9bedecc2a48498079c43d60725145`，created `10:27:44.354Z`；没有连带中断。证据 `r2/e-running.png`、`r2/e-disabled-interrupted.png`、`r2/p-continues.png`；计时文件 `/tmp/nano-feat-657-release-check/.gateway-workspace/wt-nano-feat-657-release-check-52895/daily-engineering/lifecycle-e-progress.txt`。
4. **群停用消息与新工作恢复**：研发日常明确标出 E/Q 不处理消息，停用 E 的真实成员提及 `4c6386d2c32b4013963660c65799e6a3` 保存而不回复。E Enable 后，新的成员提及 `d59f9f300371484290bf44da4f1867aa` 得到公开 `R2-E-GROUP-NEW-OK`，message `4468b137d0a04241b605052442547c85`。旧计时 Bash 没有恢复，停用群消息没有补回复；Q 的停用通知保持，E 的通知移除。证据 `r2/group-disabled.png`、`r2/group-new-reply.png`。

上述截图共同目录 `/tmp/nano-feat-657-review/`。本轮真实页面显示身份→设备→生命周期状态/操作，正常、离线、停用、重新启用的阅读顺序成立。聊天新增说明直接解释“可保存消息但不执行”，解决了 R1 的用户判断缺口。

### R1 问题闭环（本轮已观察部分）

| 问题 | 本轮结论 | 证据 |
|---|---|---|
| R1-1 新工作重新启用失败 | closed：S 私聊与 global E 群提及均真实回复；E 旧 Bash 未恢复 | 旅程 2、4 |
| R1-2 聊天不表达停用 | closed：单聊/群聊按具体 Agent 明确提示不处理；停用期间消息仍保存；320 宽可读 | 旅程 2、4 |

### 复用 caller 的真实系统与原生证据

- `offline.json` 记录 Q 离线 desired=disabled/revision2、applied1/stopping；`offline-verified.json` 记录旧 PID 不再存在、Enable 后两 Task 都 paused、真人只恢复 `tg_cb22adf1`（doing）且 `tg_05961780` 仍 paused，再次停用成功。与 reviewer 独立页面观察对账，不能把 `stateAfterExplicitResume` 当离线快照。
- `pa-cycle.json` 与 `messages-c_*.json`：PA disable2→enable3，停用消息 `7ee85ac0479747ad83f0e2f408f198ae` 未补回，新请求得到 `FEAT657-PA-FRESH`，created `10:27:12.727Z`。global/single-thread/PA 的完整周期都有真实模型结果。
- `nonowner.json`：非 owner 操作返回 404 agent_not_found，未改生命周期；更细的 Agent/node 不能凭工具改变生命周期、旧审批/代次/自动入口由已保留真实 HTTP/WS 及 native 契约测试验证。
- reviewer 已查看 `/tmp/nano-feat-657-release-check/ios-profile-disabled.png`、`ios-config-disabled.png`、`ios-work-disabled-large-type.png`、`ios-disabled-chat.png`：详情为单一 Enable again 行；配置为单一原生 Toggle；Work 最大字体下操作/状态自然纵向排列，caller 实际滚动确认后文可读；聊天首次进入真实显示不处理消息。原生没有 Toggle 与同义按钮共存，设备 Online 与 Disabled 分开表达。触控/动态字体实际操作及 25 tests / 5 suites 由 caller 集中验证，reviewer 不冒称自己操作模拟器。


### 最后两项决定性观察

5. **全部停用仍可管理与冷读**：P/E/Q/PA/S 全部 confirmed disabled，`alloff.json` 的 before/after/afterManagementReads/afterNativeHistory 均仅 control PID 54587。模型设置读取、Q 配置 GET/PATCH、P Work GET 实际成功。reviewer 独立打开 P 原生轨迹 `771c39ae-3344-4a6e-b263-2d0a549adaa1`，完整读取此前 sleep25 及公开 send_message 回执；截图 `r2/alloff-p-native-history.png`。此后进程检查仍没有产品 Agent host，闭合“历史可读且不拉起执行”的两侧证据。
6. **真实截止失败与重试**：caller 仅对隔离 S host PID57481 注入 SIGSTOP；reviewer 从真实列表 Disable，先看到 Stopping，随后 Stop unconfirmed，正文“New work remains blocked. Retry stopping.”及“Managed cleanup did not finish within the stop deadline.”。点击 Retry stop 后仍保持未确认，只有 Retry stop、没有 S 的 Enable。1440×1000、390×844、320×740 实际截图分别为 `r2/unconfirmed-1440.png`、`r2/unconfirmed-retry-390.png`、`r2/unconfirmed-retry-320.png`；窄屏状态、原因自然分行，操作首屏可达，不遮挡导航。系统证据 `unresponsive-host.json` 为 desired disabled revision6/applied5/stop_unconfirmed；原 PID 已消失仍不虚报资源清理成功。`unconfirmed-enable-denied.json` 记录真人直接 Enable 被 409 拒绝。这是受控真实进程故障，未使用模拟响应或改写生命周期数据库。

### 最终 must-match 对照

| Reference | Required contract | Actual evidence / state | Conclusion |
|---|---|---|---|
| design.md 身份→设备→开关 | 列表、详情、Work 独立入口；不等于配置保存；1440/390/320 | R1 草稿与三个宽度证据仍有效；R2 活动 E Work Disable、S 列表 Disable | match |
| design.md lifecycle 状态区 | stopping/disabled/offline pending/failed/retry；未确认不可启用 | Q 离线→重连、S 真故障/重试与三宽度截图、409 Enable 拒绝；nonowner 测试身份无 Agent 可见范围，真实404，未虚构其详情页 | match；权限按钮的不可见范围由权限契约与真实拒绝补证 |
| design.md 重新启用与历史 | 旧任务保持暂停，新工作可执行，历史可读 | S/E/PA 新请求真实回复；旧 Bash 不续跑；Q 仅明确恢复一个图；P 全停用冷历史不启动产品host | match |
| design.md iOS 独立页面 | 每页一个入口、配置无重复按钮；正常/停用/失败、动态字体、44pt | 已独立查看最终三页/聊天截图；复用 `/tmp/nano-feat-657-acceptance/ios-work-unconfirmed.png` 真实失败图及 caller 原生操作；最大字体 Work 可滚动，25 tests/5 suites 与最终 archive 成功 | match；原生由 caller 操作，reviewer 图像核验 |

### 最终十二项 Scenario 覆盖

以下来源均为 spec.md 同名 Scenario；本轮 targeted 补齐 R1 必验缺口并保留未失效证据，合起来形成完整 FULL 验收覆盖。

| Scenario | 决定性证据 | 结果 |
|---|---|---|
| 从工作视图紧急停用 | 旅程3：真实 E Running/Bash Running，点击 Work Disable，200ms 确认，计时停止；R1 草稿独立 | pass |
| 空闲 Agent 也能停用 | R1 E idle、R2 S 真实列表停用，刷新与跨页状态保持 | pass |
| 跨聊天、后代及后台工作一起停止 | 真实 E Bash 进度停止；native root/child/grandchild/continuable/Bash/PTY 多后代 owner 停止证据，既有后台/跨绑定准入契约 | pass |
| 其他 Agent 不受连带中断 | 真实 P 在 E 确认停用后仍公开完成；native 独立 host 持续写入 | pass |
| 消息与自动任务触发 | 单聊/群聊停用通知、held 消息不处理不补回；定时/heartbeat/旧代次/审批准入由保留 native/HTTP/WS 测试覆盖 | pass |
| 重连、重启和重复操作 | Q 真离线→停用→重启权威先应用，旧PID消失；两任务 paused；重复停用与 S Retry 不恢复工作；保留代次/重复更新测试 | pass |
| 节点离线 | Q 明确 Stopping/等待节点确认，主操作禁用，重连后才 Disabled | pass |
| 清理超时或失败 | S SIGSTOP→真实 deadline 未确认，原因可读、Retry 保持安全状态，Enable409；三个宽度截图 | pass |
| 明确重新启用 | S 私聊/E 群聊/PA 新请求均真实回复；停用消息与旧 E Bash 不补跑 | pass |
| 用户明确恢复旧任务 | offline-verified.json：两图暂停，明确恢复 tg_cb22adf1 后只有该图 doing，另一图仍 paused | pass |
| 非管理者与 Agent 自身不能改开关 | 真实 nonowner404；同空间403、Agent/node 身份拒绝使用既有真实HTTP/WS identity测试；没有扩大Agent工具权限 | pass |
| 设备在线但 Agent 停用 | Web 配置/Work/单聊/群聊与iOS三页分开表达 Online 和 Disabled；聊天明确不处理消息 | pass |

### 最终 Verdict

**pass**。R1 两个 blocking 问题均已在修复版本闭环；本轮新增问题 **0 blocking / 0 major / 0 minor**，十二项必验结果均 pass。真实 Web 完成决定性用户旅程，原生采用最终构建的实际页面证据与 caller 集中验证；自动机制和复杂 OS 后代场景明确引用自动化实证，不冒称全部通过真人 UI 重演。

macOS DSH 受管资源范围仍按已接受的平台边界处理；失败时真实保持 stop_unconfirmed，不把进程退出等同于资源清理成功。此次未部署生产、未发布安装包。当前 spec 归并、提交/PR/CI 属 orchestrator 收尾门禁，不由本报告代替。reviewer 仅修改此报告，未启动额外服务；已恢复浏览器 viewport，隔离栈与故障进程由 caller 统一清理。
