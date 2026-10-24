# refactor-655 — 验收报告

> 对齐：motivation.md 用户侧验收标准及追加确认；design.md 原型与 runbook。
> Validation snapshot：`0d3a762fed52fe14a93fcb03ba4de72532a5887a → 0d3a762fed52fe14a93fcb03ba4de72532a5887a`。
> Round 1，2026-10-25，独立 product reviewer。隔离真实 Node / DSH / IM，确定性 fake provider；Web `http://127.0.0.1:59749`，测试身份 nano，Global e2e-global。caller 确认 Vite 从冻结树启动，未修改源码。没有生产操作或重启 caller 服务。

## Verdict

**最终：pass（Round 2）。产品问题 0；报告未提交。**

### Round 1 初始裁决（以下保留，已由 Round 2 关闭）

**fail（待补验，尚未观察到本次实现缺陷）**。保存记录、主子统计、工具失败/成功详情和同步状态展示已经通过；原生详情的隔离静态资源前置缺失，实时开始和多页历史仍待追加证据。不得以 API 成功代替这些用户入口。

## 用户旅程体验

从真实聊天的 `View Work →` 进入 Work。桌面主区按执行顺序显示 inbox、read、subagent、send_message，最近已报告主上下文位于轮次上方；展开 read 可看到 parent.txt 参数路径和 `parent fixture input` 正文。关联子执行在桌面右栏展示自己的轮次，390×844 窄屏切为可返回主轨迹的子视图。失败 read 以红色 Call failed 和完整 not found 原因呈现，随后 child.txt 成功正文可展开；失败不会把整个已完成子执行伪造为失败，也未被成功项掩盖。

主轮 Context 40 / 262144、output 18、cache 60 (25%)；子轮 Context 40、output 9、cache 30 (25%)，与真实 Work 响应及 caller 重启证据一致。主子用量说明明确分别计数、非账单总量。刷新后展开状态、工具内容和关联执行仍可回看。

实际看过 1440×900 桌面、390×844 窄屏截图。长路径自然换行；内容可以纵向阅读，底部移动导航没有阻止查看。新增说明在查看方式与统计之间，不遮挡或替换已有内容。catching_up、unknown、offline 通过浏览器响应拦截演示，只证明 UI 映射与布局；current 来自真实 API。已移除全部拦截。

本机原始证据（不提交缓存）：`/tmp/review655-desktop.png`、`/tmp/review655-unknown-desktop.png`、`/tmp/review655-unknown-narrow.png`、`/tmp/review655-catching-narrow.png`、`/tmp/review655-offline-desktop.png`、`/tmp/review655-offline-narrow.png`。子失败/成功窄屏截图：主仓 `.playwright-cli/page-2026-10-24T18-07-43-038Z.png`。详细 UI snapshots 同目录 18:06:54、18:07:33、18:07:42 UTC。

## Reference Artifacts Reviewed

实际通过临时 localhost 服务渲染并查看 `prototype.html`（`/tmp/review655-prototype.png`），临时服务已停止。原型限定新增状态说明，既有布局并非像素复刻要求。

| Reference | Required contract | Actual product evidence | Viewport / state | Comparison conclusion |
|---|---|---|---|---|
| prototype.html 状态行 | catching_up / unknown 可辨、current 隐藏、offline 不叠加 | 上述 catching/unknown/offline 截图；真实 current snapshot | 1440×900、390×844；异常状态为浏览器注入 | match：提示在原有工具栏下、统计上方，语义准确，窄屏换行，offline 只有离线说明 |
| prototype.html 最近主上下文 | 最近已报告语义、数值保持 | 18:06:54 snapshot；Work response 402；重启证据 | 桌面真实已完成轮次 | match：40 / output18 / cache60，与子执行分开 |
| 主子过程、分页、原生轨迹 | may-adapt，既有阅读能力保持 | 工具/子执行截图；原生入口存在但资源未就绪 | 桌面、窄屏 | 主子工具 match；分页、原生详情待补验 |

## 问题清单

| # | 严重度 | 现象 | 处置 |
|---|---|---|---|
| E1 | 验收前置阻塞 | 子执行“查看原生轨迹”停留连接中；/trajectory/ 被 Vite 回退主页面，sandbox null origin 下 main.tsx / @vite/client CORS 失败 | caller 修复隔离静态服务后 targeted 复验；不归因为本次源码回归 |
| E2 | 证据缺口 | 当前主子仅各一轮；尚未在浏览器观察工具开始到结束及更早分页 | caller 追加真实轮次；继续独立查看 |

## 验收标准覆盖

### Requirement: Work 页保留真实主子执行统计 — 组内结论：fail（待补）

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 查看主任务和子任务完成轮次 | motivation.md / 当前 agent-work 契约 | 走既有入口，展开主子工具及统计，对照 provider 确定计数和重启前快照 | UI snapshots；restart-evidence.json | pass | 主40/18/cache60，子40/9/cache30；没有伪造未知值 |
| 节点重启后继续查看及执行 | motivation.md | caller 已重启，reviewer 独立查看旧内容；新轮次待补 | `/tmp/nano-refactor655-browser/restart-evidence.json` revision35保持 | inconclusive | 历史可读已通过，重启后的新执行尚待观察 |

### Requirement: 聊天与 Workflow 的原生用量语义保持 — 组内结论：pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 查看聊天 Token 气泡和 Workflow 消耗 | motivation.md | 复用同冻结版本真实 Node/DSH/IM 定向测试；独立 Work 计数辅助 | `/tmp/refactor655-token-e2e.log` 1 passed；`/tmp/refactor655-native.log` 4 passed | pass | caller 说明前者 bubble/Work31001/1/cache1000，后者预算spent15；日志只记录通过，数值来源明确为 caller。未声称本轮手动执行 Workflow |

### Requirement: 已保存工作记录可以立即读取，恢复只处理缺口 — 组内结论：fail（待补）

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 完成的历史增长后重启 | motivation.md | 重启后独立展开已保存主子工具/统计；多页历史待补 | restart-evidence.json；本轮 UI | inconclusive | 首次补建副本 root43/child29 events，二次启动正文0，见 bootstrap-copy-2/evidence.json；底层计数由 worker 负责 |
| 崩溃发生在原生持久化与产品记录提交之间 | motivation.md | 实现层崩溃窗口与处理位置，由 worker/verifier 定向测试核查 | M1 verification.md | not-applicable | 疑似实现层 Scenario，应属 design.md；不以浏览器回看代替崩溃测试 |
| 断线补传时继续工作 | motivation.md / prototype | 已观察三种提示与已保存内容；真实补传期间新输入和持续更新待补 | 状态注入截图 | inconclusive | UI注入不证明真实断线恢复；状态文案/窄屏布局 pass |
| 检查具体执行原始详情 | motivation.md | 点击关联子执行原生入口 | 18:07:47 snapshot / console | inconclusive | 环境E1阻塞；未声称原生分页或继承历史通过 |

## 上层文档同步

- [x] `SPEC.md`：无需更新；现有责任边界不变。
- [x] `docs/specs/im/agent-work.md`、IM auth-tenancy、Gateway service-lifecycle：需要 orchestrator final sync 归并 unit delta；已检查目标增量。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新。
- [x] `docs/specs/CONTRIBUTING.md`：无需更新。

## Remaining / 复验条件

E1 修复后复验真实原生主/子详情、原生历史查询；E2 准备后观察真实实时变化和多页 Work。保留本轮已验统计、工具、状态与视觉结论，只有数据/实现变化影响这些结论时扩大复验。iOS 按 runbook 采用定向编译/契约测试，不声称模拟器体验已验。

## Round 2 — 环境补齐与 targeted 复验（同一冻结 HEAD）

**Verdict：pass。问题数：0 个产品 blocking/major/minor；Round 1 的 E1、E2 已关闭。** Round 1 保留作为实际验收过程与前置缺口记录，最终结论以本轮为准。

### 补验旅程与决定性证据

1. caller 补齐本 worktree 已构建 viewer/dist 的静态托管及临时 Vite `/trajectory` 代理，没有源码变更。重新从既有子执行进入原生轨迹后显示“已连接 · 实时更新 · 只读”；点击失败 read，能检查 file_path、FS_NOT_FOUND、错误正文、Schema、计时，桌面检查器右侧显示，390px 窄屏浮层完整换行。切到 Main Agent 显示两轮共 12 次模型请求及各自工具/发起子执行，旧历史仍可检查。截图 `/tmp/review655-native-desktop.png`、`/tmp/review655-native-narrow.png`、`/tmp/review655-native-main.png`，snapshot 18:10:47 UTC。E1 关闭。
2. caller 暂停隔离 fake provider（非产品状态伪造）并发第二条真实消息。reviewer 看到新轮 Running、0 tools，旧轮与子执行仍可读；最近主上下文仍40并出现“Showing the latest reported turn until new statistics arrive”。通知 caller 恢复后保持当前页面，自动观察到 Idle、新轮5次工具完成、聊天 WORK_DELIVERED 通知。截图 `/tmp/review655-running.png` 与 `/tmp/review655-completed-live.png`。
3. **自动完成截图同时捕获真实 catching_up**：此时 Round 1 的状态响应拦截已全部移除，最新轮已完成、旧工具可读、聊天送达通知同时出现；随后真实 current 隐藏说明。证明真实补齐期间已保存内容和消息递送持续可用。此轮没有另外制造网络断线；断线/重试机制复用 worker 的 WorkSync 定向验证，不能把浏览器注入称为断线实验。
4. 为在两轮数据中操作实际分页，reviewer 仅把浏览器首个 Work 请求转发为同一真实 API `?limit=1`，原样返回服务端响应，未伪造记录或 cursor。窄屏显示第二轮与 Earlier turns 按钮，点击后发起真实下一页查询，第一轮完整恢复，旧 read 内容与主子关系一致；截图 `/tmp/review655-pagination.png`、snapshot 18:11:12 UTC。caller 的 `/tmp/nano-refactor655-browser/pagination-evidence.json` 也保存两页与默认列表相等的比对。随后移除此请求转发。E2 关闭。

### 继承与关闭矩阵

| Round 1 项目 / Scenario | 新证据 | 最终结果 |
|---|---|---|
| 节点重启后继续查看及执行 | 旧轮重启revision35不变；本轮真实第二轮Running→完成自动更新、聊天送达 | pass |
| 完成的历史增长后重启 | 重启后真实历史工具/统计读取 + 真实API两页UI操作；bootstrap副本第一次root43/child29正文、二次重启0正文 | pass |
| 断线补传时继续工作 | 真实catching_up与聊天送达同时出现、旧记录持续可读，随后current；UI异常状态单独映射已验 | pass（用户可观察结果）；网络重试由worker定向验证，不宣称本轮手动断网 |
| 检查具体执行原始详情 | 真实主两轮/子轨迹、工具参数结果Schema计时、桌面和窄屏检查器 | pass |
| 主子完成统计、聊天/Workflow原生用量 | Round 1 对应证据仍有效，无源码变化 | pass |
| native持久化→journal→ACK崩溃窗口 | 仍归 worker/verifier；不是独立UI实验 | not-applicable（reviewer实施层范围） |

### Reference 最终对照与限制

状态行、最近已报告主上下文两项 must-match 通过。真实 catching_up 截图补强 Round 1 注入演示，current 隐藏、unknown 与offline单条说明的窄屏布局结论继续有效；分页及原生 may-adapt 项的前置缺口已关闭。原生查询保持公开按需入口，不声称范围数组等于范围磁盘 I/O，也不把本次普通子执行试用扩大为大型 fork 继承前缀专项压力验收。

没有剩余产品阻塞。首次升级/回滚和读取放大限制见 worker verification 及 deployment-prompt；生产未部署。iOS 本轮仍按 runbook 复用定向编译/契约测试，未做模拟器视觉旅程。报告未提交，由 orchestrator 纳入交付。清理 reviewer 自建浏览器与原型静态服务；未停止 caller 的 Node/IM/provider。

复用测试证据精确归属：`global-work-recovery.test.ts` 覆盖 root 原生接收先于产品提交的崩溃窗口及开放轮次 checkpoint；`inbox.test.ts` 覆盖文件库 close/reopen 与事务回滚；WorkSync 测试覆盖 HTTP 上传失败、ACK 丢失重试、pending 无新 event 清零。测试结果与真实接口证据汇总见同目录 `acceptance.md` / `verification.md`，本 reviewer 没有重复执行这些实施层实验。
