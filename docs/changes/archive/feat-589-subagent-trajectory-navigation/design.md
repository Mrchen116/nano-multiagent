# feat-589：在原生轨迹内检查一次委派

## 状态与已确认决定

首文档：[spec.md](spec.md)。2026-10-13 用户否决双视图，要求保留原生界面；在核实公开插件缺口后，授权将官方轨迹 UI 单包复制到本仓独立维护，随后明确要求继续实现、提 PR 并保留测试服务。

**最终方案：只有一个由原版 DSH 组件派生的轨迹视图。** 本仓 `@nano/trajectory-ui` 保留原版表格、时间线、搜索、折叠、详情与请求检查器，只增加发起入口和受控执行范围。之前的 `nano-execution` 重写视图及“轨迹导航 / 原生明细”开关删除。原方案与旧验收只作历史，不作为新 UI 的通过证据。

分叉基线、MIT 许可、来源 commit 及已完成的等价构建见 [fork-baseline.md](fork-baseline.md) 和 [包说明](../../../../packages/trajectory-ui/README.md)。这是唯一 UI 源码例外，DSH 执行运行时、其他官方插件与安装包保持未修改。

## 体验与信息层级

主入口仍是 Agent → Work → 原生轨迹。正常阅读继续看到原有紧凑表格、三行时间概览和点击记录后的原生详情。新增内容遵循现有字号、颜色 token 和密度，不重新组织原有检查能力。

- 工具委派：对应工具行下方增加一条紧凑入口，优先显示用途，再显示普通/fork、前台/后台和真实状态，最后是“查看本次执行”。点击入口不会误选另一条记录或执行工具。
- 后台维护：没有对应工具行时，在真实 `launchSeq` 位置插入明确标作“发起”的呈现记录。该行由 Nano 持久运行事实生成，不伪装成 DSH 用户消息或工具结果；详情保留事实身份与来源。未知坐标明确标记，不能猜测成精确发起位置。
- 子执行：宿主原有返回与来源链位于视图上方；视图内增加紧凑范围条，显示用途、状态、fork、起止及“定位起点 / 定位终点”。不再增加模式页签或第二个检查器。
- 默认完整轨迹：加载整个子会话，保留继承前缀和其他执行；自动设置本次范围的原生时间轴选区，区间外沿用原生手动拖选的淡化效果，不过滤记录。
- 起止未知：没有明确起点时展示已知会话历史；没有明确终点时显示“最后已知”，禁用终点定位。运行中的自动范围延伸只更新数据，不夺取已在阅读旧记录的滚动位置。
- 非管理者仍能只读检查；图片继续使用原 Conversation 授权加载。业务原文、工具参数结果、请求 prompt/schema、usage/timing、图片、原文/来源检查继续在原生详情中完成。

宽屏沿用原生表格与检查器分栏。820 和 390 宽沿用原版响应式结构；新范围条和发起入口允许换行，按钮不得挤出屏幕或覆盖原生内容。若原版检查器本身在嵌入窄屏存在实际不可用问题，只作必要的布局修正，不创建第三种 renderer。

## 模块边界与小接口

| 模块 | 职责 |
| --- | --- |
| `packages/dsh-integration` | 已有真实 run 捕获、持久化与授权读取；本轮不改变执行语义 |
| `packages/product-contracts` | 已有 `TrajectoryRun` 和只读 carrier DTO |
| `packages/trajectory-ui` | 原生派生组件、运行事实呈现、执行显示范围与本地交互状态 |
| `packages/dsh-trajectory-viewer` | 官方模块组装、只读 MessagePort、提供当前 Session 的 navigation face |
| `src/IM/frontend` | 原有身份与授权、保留父 iframe 的导航栈、来源链与返回 |

本地插件提供 `apply(ctx, { navigation? })`；`navigation(sessionId)` 返回此会话的 `initialRunId`、期望父 Session、`readRuns(signal)`、`firstSeq()`、`hasMore()`、`lastSeq()`、`loadThrough(seq)`、`isActive()` 和 `navigate(run)`。实际传输留在 viewer，UI 只消费固定 observer 读回的产品事实。类型从公开包入口导出，不跨包 import 私有路径。

这是 Nano 自有 UI 的直接接口，不额外修改通用 Conversation 或 Slots，也不为了未来假想插件体系新增公共服务。原有图片插槽继续保留。分叉包由自己的 public apply/inject 注册一次 `trajectory`，不能同时安装官方同名 trajectory 插件。

构建器以 `@nano/trajectory-ui` 的模块身份加载本地注册 bundle，复制其产物与依赖清单；官方 Session、Conversation、Renderer、Attachment 等注册 bundle 仍原样复制。React、Cordis、Store 与服务 registry 从宿主模块表共享，防止双实例。运行时 DSH 版本继续固定为 `0.2.1-alpha.1`。

## 运行事实与本地呈现

已通过真实 DSH 测试的生命周期事实继续沿用：[M1 运行事实记录](M1-navigation/run-facts.md)。`startSeq` / `endSeq` 是包含式边界；启动调用返回不代表子任务结束；持续驻留收信不是新 epoch；进程重启且无结束记录时为 unknown。

UI 以两秒、单个在途请求刷新小型 run DTO；父 frame 隐藏时跳过轮询，卸载时 abort。子 frame 用自己的 observer 重读 `runId + sessionId + parentSessionId`，不把父 frame 传入的对象直接当作事实。读取失败保留已知内容，但显示中断和上次状态。

本次范围仅设置原生时间轴选区，不过滤显示投影，不修改官方全局 Conversation target 或 Session 事件。完整请求事实仍来自原投影，不能用当前配置补历史 prompt 或 schema。原生稳定记录身份保留；新增发起记录以 runId 为稳定身份。

有 callId 的发起事实优先装饰对应工具记录；没有可呈现工具记录且有 launchSeq 的事实以独立发起行出现在对应坐标。历史窗口之前的已知发起点不会提前混入当前尾页。新增行进入原有分组、搜索与虚拟表格，不另外实现列表。

运行中工具和 partial 保留在完整会话，以请求坐标判断是否在选区内；新 epoch 的输出不能高亮为旧执行。原生时间线支持不同投影模式，自动范围由本次记录在当前投影中的 span 推导，记录是否属于 run 则以 seq 判断，避免时间戳重叠或等宽边界将继承行误算进来。

## 历史、选区与返回

通过公开 `loadThrough(0)` 补齐完整会话，并用 Session `hasMore` 核对覆盖；软失败显示可重试错误。连接 generation 更新后 Session 窗口被替换时重复这一核对，不能因为第一次加载成功就停止补齐。

完整轨迹在关系核对及全部历史加载后展示；起点未知时不推测选区。进入子执行不截断内部 50-record 窗口，仍使用原生虚拟化与尾随规则。

自动选区与用户手动选区分开：初次进入和显式“本次范围”操作恢复自动聚焦；手动拖选、清除或在范围外选择记录后尊重用户选择，轮询不得周期性夺回。切换原生时间/时长模式时，从同一组执行记录推导对应区间。起止定位通过原生记录选择/滚动机制展开必要折叠并选中目标，不通过跨 iframe DOM 控制。

父 frame 隐藏而不卸载，返回时保留原生组件内部的滚动、缩放、选择、搜索、折叠和详情。子 frame 退出即释放引用、流、图片缓存和 port。身份改变、资格失效和离开 Work 会销毁全部 frame。浏览器书签只保存数字坐标/记录身份，不保存原文或凭据；不同 run 使用独立位置键。

## 原型与体验契约

[prototype.html](prototype.html) 使用分叉基线的原生组件和原版样式作为实际背景，固定数据只演示本次新增范围条、行级入口与父子返回。原型的按钮注入/拖选模拟只用于可视化，不进入产品实现。原型构建与走查记录在 [evidence/native-design-walkthrough.md](evidence/native-design-walkthrough.md)。

| 类型 | 必须兑现的体验 | 入口 / 状态 | M1 退出标准 |
| --- | --- | --- | --- |
| must-match | 一个原生派生界面；表格密度、时间线、搜索和详情辨认方式保留，没有双视图开关 | Work；1280 / 820 / 390 | R1 / W2 |
| must-match | 从发起行看到用途、状态及 fork 并进入正确执行，后台维护可发现 | 主动 / memory / skills | R2 / W1 |
| must-match | 范围条、时间概览与过程对应同一次执行，继承历史可回看，未知终点不能伪装完成 | fork / 重复 epoch / running / unknown | R3 / W1 |
| must-match | 从嵌套逐级返回，父级原生阅读状态保持 | 父→子→孙→返回 | R4 / W2 |
| must-match | 窄屏能完成检查；原生请求/原文/图片能力不丢失，身份/权限不扩大 | 非管理员 / 附件 / 身份失效 | R5 / W2 |
| may-adapt | 新操作在行末或换行排列，保持紧凑且完整可读 | 820 / 390 | R1 / R5 |
| out-of-scope | 不改 DSH 执行逻辑，不新增聊天控制或第二套 Agent Loop | 全部 | W1 |

## Runbook for Reviewer

复用此 unit 的隔离栈和真实历史，不另建生产连接。worktree 为 `/Users/czj/.codex/worktrees/unit-feat589/nano-multiagent`，现有 IM 地址 `http://127.0.0.1:63084`，进入 `/settings/agents/nav589?view=work&work_view=trajectory`（最终验收前由作者核实实际 Agent 路由）。管理员测试账号 nano / nano1234；非管理员 reader589b / reader589b-pass。只有这一隔离库的测试账户。

构建：`pnpm --filter @nano/trajectory-ui build`、`pnpm --filter @nano/dsh-trajectory-viewer build`、`pnpm --dir src/IM/frontend build`。现有服务使用 worktree 静态目录，页面重载后取新资源；若需重启执行子进程，用 `node apps/node/lib/cli.js restart --config .gateway-config.yaml`。先核对 `.e2e-ports.env`（不输出 secret）和 owner，再使用 `./scripts/e2e-up.sh --wt <worktree>` / `e2e-down.sh`；up 会清隔离状态，不在已有 fixture 上随意重跑。

保留已生成的普通、fork、嵌套、后台 memory/skills、失败/取消、同一子会话多 epoch 与 unknown 真实记录作为受控 fixture。只在缺失状态时补充真实 DSH 用例。既有 backend 证据按版本保留，新 UI 必须独立实际走查。授权图片正/负例使用此前有效 PNG 私聊记录，不复用失败的坏 PNG。最终测试服务按用户要求保留，交付 PR 时提供经核实的准确 URL 和账号。

## Milestone

继续 M1-navigation，不新增横向层级里程碑。原运行事实实现保留；本轮 UI 与接线替换、源码许可和测试一起完成。

| ID | 依赖 | 并行组 | 文件范围 | 退出标准 |
| --- | --- | --- | --- | --- |
| M1-navigation | 无 | 单 milestone | trajectory-ui、viewer、必要的 Work 位置键、架构契约、unit 文档 | [reviewer] R1–R5 为上表五项 must-match，实际跨屏走查并与原生基线对照。[worker] W1：原运行事实/只读权限有效；新范围、epoch 隔离、后台行与恢复有窄测试。[worker] W2：新包 typecheck/build、最终 bundle、前端与依赖/docs CI 通过；真实浏览器截图及独立产品/静态审查完成。 |

## Changelog

旧双视图路线已撤销。Round 3 Gate 2 Approved 后已接入单个原生派生插件；最终实现、真实服务走查与独立验收以本轮 M1 记录和报告为准。

## 用户反馈修正

2026-10-13：按 spec 最新原话，移除过滤投影与本次/历史切换。宿主用当前 frame 通知同步执行选择器；手动选择会话仍重新打开对应会话。原过滤相关验收结论失效，针对完整历史选区、返回、选择器及恢复执行独立局部复验。
