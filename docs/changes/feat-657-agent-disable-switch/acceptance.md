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
