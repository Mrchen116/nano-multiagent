# feat-600: 电脑页面体验重设计 — 设计方案

> 对齐：[spec.md](spec.md)。设计交付，不代表真实产品已更改。

## Changelog

- 2026-10-14 (M1)：用户授权实施并要求与 feat-596 同一 PR；复用 PR #349 分支和 worktree。采用已有 Radix Dialog 兑现焦点圈定、Escape、桌面抽屉/手机全屏，属于既定交互的实现选择；需求、数据接口和信息层级不变。

## 现状分析

### 涉及范围

- 页面入口为 `/settings/nodes`，由 Web `app/router.tsx` → `SettingsPageShell` → `NodesPage` 组装。桌面从账号菜单进入；手机从“我”进入。Shell 当前透传，不引入新的设置侧栏。
- `src/IM/frontend/src/features/settings/nodes/nodes-page.tsx` 持有列表、名称草稿、PATCH 和实时状态缓存。feat-596 的 `node-update-panel.tsx` 持有更新与取消 mutation、request ID 和进度呈现。
- 当前 main 尚无 feat-596 的更新 UI；目标代码基线为 [PR #349](https://github.com/Mrchen116/nano-multiagent/pull/349) 的 `21cdafb5d3f04b1f04ab532a6f82d3d519cba60c`，设计依赖其行为。不得因重设计删除原有请求幂等、POST/WS 竞态修复或更新屏障。

### 既有约束

只改 Web 呈现与页面内交互；不修改 IM/Node/DSH 更新契约、权限或安装器。不提前覆盖 [current agents-nodes](../../../specs/im/agents-nodes.md)。遵循 [Web IM 体验原则](../../../product/web-im-principles.md)：可辨认身份、真实可用性、合理密度、独立手机布局。未收到 Node 成功回报时不得用计时器宣告更新完成。

### 可复用能力

| 既有能力 | 决定与原因 |
|---|---|
| `listNodes` / `updateNode` / `node.status_changed` | 复用；详情读取列表中的实时对象，名称编辑仅持有 alias 草稿，不复制整份只读连接状态 |
| feat-596 `NodeUpdateView`、start/cancel mutations | 复用；改变信息呈现，不重建更新状态机；单一 active operation 作为事实源 |
| `getOnboarding` 的 install 与 owner agents | 按需复用到连接说明/详情；取得当前服务 command/origin 与该 node 的助手名称，无新后端接口 |
| `/settings/nodes/:nodeId/agents/new` | 复用；详情里的创建助手按钮进入现有页，不重新设计助手配置 |
| 现有颜色、字体、头像与导航 | 沿用低饱和青绿、白底与轻边界；局部按钮统一 token，不改全局 CSS |
| 全局 `InAppToast` | 本次不改；用户附图中的顶左遮挡与原始 ID 是邻接共享通知问题，不把原型未出现通知理解成已修复 |

### 相关历史

feat-596 已交付更新全链路并获用户“功能看着 ok”反馈，本 unit 接续页面体验。feat-585 提供连接恢复与真实在线状态，不能把普通离线误报故障。与先前大规模 Web 导航变更保持入口一致。

## 架构总览

保留 NodesPage 作为查询、选择电脑与编辑动作的 owner。页面由“标题与轻量摘要 → 电脑列表 → 一条使用说明”构成；每张卡片只有“身份和状态 → 当前版本/助手数 → 需要处理的动作”。详情是该页按需打开的子表面，列表位置不变。桌面右侧 456px 抽屉，手机 ≤680px 全屏详情，返回后维持列表滚动位置。

实现最多拆出就地 `NodeCard`、`NodeDetails`、`NodeConnectGuide` 和更新呈现函数，放同一 feature；不新建通用设备管理框架。`node-update-panel.tsx` 可保留模块名并改呈现，不为样式新建第二套操作状态。

## 关键决策

**把“需要处理哪台电脑”放在首位。** 移除 4 个统计大卡，摘要仅“2 台电脑 · 1 台在线”。卡片以名称为最强层级，状态/现用版本/助手数为次级；原始 ID、心跳、原始错误进详情的折叠诊断。无搜索、筛选或批量更新，因为本需求没有大规模设备管理依据。

**每台电脑只给当前可执行的主动作。** 有新版本才出现绿色更新条和更新按钮；没有更新时不占一整块“已是最新版本”面板。离线与同版本不显示“0.4.0 → 0.4.0”或灰掉的更新主按钮。若离线且已知有新版本，仅说明上线后可更新；不把 `reason=offline` 推断为存在更新。普通断连用中性灰；只有影响恢复的异常使用琥珀色。

**管理操作按需进入，保留上下文。** 名称与“详情”均打开同一详情表面；重命名在详情中显式开始，原位输入、取消、保存。保存前不改变列表，失败保留草稿；关闭详情等同取消未保存编辑。保存成功同时刷新列表/详情和既有联系人缓存。更新切换/恢复未完成、离线时禁用改名和创建助手，并就近说明原因。收起诊断不丢失详情上下文。

**桌面和手机共享阅读顺序，各自安排空间。** 桌面内容最大 952px，更新文字与按钮同排；手机边距 18px、卡片内更新按钮另起一行，完整 44px 热区，避免状态说明和按钮互挤。详情改为全屏独立滚动、顶部返回，不把桌面抽屉硬缩窄。标题 30/26px，卡片名称 17/15px，正文 13px 左右；普通按钮桌面 40px、手机 44px，统一 9px 圆角、13px 字重 600。文本按钮也保留同等热区。产品实现可按现有 token 做微调但不得重回混杂尺寸。

**更新反馈只说明真实阶段与下一步。** 准备（requested/downloading/installing）、等待空闲（waiting）、切换（switching/verifying）、恢复旧版（rolling_back）、完成各有直白文案，不虚构百分比、剩余分钟、任务名称或任务数。准备/等待可取消；cancel_requested 显示“正在取消”并禁用重复请求；切换/验证/回退无取消。失败/中断且旧版恢复时可重试，relay_gated 的终态优先呈现“需要恢复”。成功只由真实回报驱动，若后续又有可用新版本，新动作优先于历史成功。

**连接入口复用已有安装能力，不把老用户送回首次设置向导。** 在列表/空态打开本页连接说明；复用 getOnboarding.install，支持本地 Agent/手动命令。无安装包则说明原因，无可复制按钮。命令来自当前服务，不拼接假 URL；恢复来自 NodeUpdateView.install_command，且旧安装方式的说明必须先要求结束当前任务（沿用 feat-596），保留配置/凭据/工作目录的安全语义。原型只示意内容关系，明确不提供可执行安装命令。

## 接口与数据流

不增加后端字段。页面展示层按下表投影，跨页/刷新仍由既有服务状态重建。

| 输入 | 展示/动作 |
|---|---|
| alias / node_name / node_id | 标题优先 alias、再 node_name，空缺才友好名称“未命名电脑”；ID 仅诊断；长名称列表单行截断，详情完整换行 |
| status / last_heartbeat_at / last_error | 在线文本与点同时表达；离线显示相对时间，详情绝对时间；时间缺失显示“暂无连接记录”，不能伪造“刚刚” |
| update.current / node.version | 现用版本只显示一次；SHA 缩短展示，完整值在诊断。target 只有不同版本且可信时作为“新版本”展示 |
| operation active / terminal | 活动与 recovery 优先于普通 reason；沿用 feat-596 terminal/新 release 优先级和 relay_gated 判定 |
| requested/downloading/installing / waiting | 准备/等待状态、阶段指示、取消；命令请求中防止重复点击，错误就地显示、不遮挡进度 |
| switching/verifying / rolling_back | “正在切换” / “正在恢复旧版”；说明消息等待，停用改名/创建；不以普通离线覆盖此说明 |
| succeeded / cancelled | 已更新到实际版本 / 已取消并保留当前版本；下一次更新可重新授权 |
| failed/rolled_back/interrupted | 结合 relay_gated 表示旧版可用或需恢复，绝不仅凭 failed 字样宣称电脑可用 |
| legacy / source / incompatible / unavailable | 一次性安装指引 / 按原部署方式更新 / 不兼容说明 / 重新检查；不出现可执行更新按钮 |
| query initial-loading/error / refresh-error | 加载占位 / 可重试空状态 / 保留旧列表并标注可能过时 |

`getOnboarding` 仅在连接说明或需要助手名称的详情打开时查询，用现有 auth client，按 node_id 过滤所属助手；失败在该区提示重试，不清空电脑列表。助手名只读，创建入口走既有路由。连接弹层保留“关闭回列表”路径，绑定后由现有事件或手动刷新读到新电脑。

改名使用已有 updateNode，输入 alias 不超过既有 API 限制，trim 后空值报错；后端拒绝显示可理解原因，原始细节留诊断。键盘 Enter 保存，Escape 关闭详情并取消草稿；焦点返回打开详情的电脑按钮。实时 heartbeat 不重置输入或改变所选电脑。若电脑断连，保留草稿、阻止提交并说明需重新上线；未授权恢复离线配置路径。

更新/取消仍由原组件持有 request_id 的不确定结果处理和查询失效机制；详情与列表不发重复 start 请求。WebSocket 先到也不得被随后较旧的 POST 回包降级。字体、本地化通过现有 i18n，英文按钮允许自然扩宽/手机换行，不固定文字宽度。

## 前端原型

[交互原型](prototype.html) 默认日常列表。外层标注导航背景/设计范围/仅演示；右下演示区选择异常状态。点击更新可连续经历准备→等待→切换→成功，也可取消后再试。所有模拟计时仅限原型，不进入产品实现。

### 现有 UX grounding

| 当前产品入口 | 基线证据 | 体验事实与设计处理 |
|---|---|---|
| `/settings/nodes` | [用户附图](evidence/before.png)，PR #349 实际更新客户端 | 一台电脑同时出现名称/原始 ID、多个版本、常驻编辑、错误码与保存按钮，必须扫很大面积才能找更新；新设计让身份/可用性和单一主动作在一张紧凑卡片内闭合 |
| `/chat/:id` | [同一交付版本真实聊天截图](evidence/adjacent-chat.png) | 沿用顶部导航、浅青绿、克制边界、头像身份；电脑卡片延续轻量内容表面而非引入新仪表盘语言。未重新验收聊天交互 |
| 手机“我”→电脑 | me-page/router 来源核实；附图来自桌面，当前手机版入口没有本轮实际画面证据 | 不更改入口与底部导航，仅把当前目标页的详情设计为全屏；下游在真实手机 viewport 必须从“我”走入和返回，不能把原型背景当现状验收 |

### 原型对齐契约

| 区域/状态 | 级别 | 产品入口 | 必验 viewport/状态 | 下游验收投影 |
|---|---|---|---|---|
| 标题摘要、紧凑电脑卡、单一更新动作 | must-match | /settings/nodes | 1440×960、820×900、390×844、360×780；在线/离线/长名 | M1 A |
| 详情/原位改名/诊断层级 | must-match | 电脑名称或详情 | 桌面抽屉、手机全屏；保存/取消/空值/失败/离线 | M1 B |
| 更新阶段、取消与错误恢复 | must-match | 卡片动作 | 准备/等待/切换/成功/失败/回退/恢复/不可更新 | M1 C |
| 空态、失败、连接说明 | must-match | 列表标题/空态 | 无电脑、查询失败、已有数据刷新失败、安装包不可用 | M1 D |
| 精确灰度、细微圆角、图标 | may-adapt | 同上 | 沿用平台 tokens；无 OS/硬件类型字段时使用统一电脑图标，不推断设备类型 | N/A |
| 顶栏/底栏、创建助手下一页、安装实际执行、全局 toast | out-of-scope | 现有导航/创建/安装/聊天 | 产品保留现有功能；原型只标明交接处，不声称这些功能已通过 | N/A |

### 原型走查

见 [实际浏览器走查](evidence/walkthrough.md)。这些证据验证设计意图和原型，不能替代真实产品验收或原生 iOS 验收。

## 契约层增量 (delta-spec)

- IM：[specs/im/agents-nodes.md](specs/im/agents-nodes.md) → [canonical](../../../specs/im/agents-nodes.md)，只增加渐进管理与连接入口的稳定承诺，不重复 feat-596 更新生命周期。

## 风险与回退

主要风险是重排 UI 时错误简化了更新优先级或改名草稿。复用现有 mutation 与事件处理，以活动更新+离线、POST/WS 乱序、编辑中 heartbeat 的最窄回归保护。若需回退，恢复旧 Web 页面即可，服务数据与更新操作不受影响。页面范围 CSS，不改变其他功能的按钮样式。

## Runbook for Reviewer

本次设计无常驻业务服务。原型：在仓库根 `python3 -m http.server 18760 --bind 127.0.0.1 --directory docs/changes/archive/feat-600-computer-page-experience`，访问 `/prototype.html`，结束 Ctrl-C。端口冲突选其他空闲高位端口，不复用不明进程。

未来 M1 的真实产品验收在含 feat-596 的独立 worktree，遵循 [隔离运行契约](../../../development/worktree-runtime.md)，不得在本 main 或生产实例起测试栈。

| 服务 | 停止 | 启动/构建 | 健康检查 |
|---|---|---|---|
| 隔离 IM/Node/DSH | `./scripts/e2e-down.sh --wt <worktree>` | `pnpm install --frozen-lockfile && pnpm build`；前端目录 `npm run build`；`PATH=<main>/.venv/bin:$PATH ./scripts/e2e-up.sh --wt <worktree>` | source `.e2e-ports.env` 后 `curl -fsS "$IM_URL/health"`；指定隔离配置确认 Node online |
| Web 静态客户端 | 随隔离 IM 一同停止 | 使用刚构建的前端 dist，由隔离 IM 提供；如使用 Vite 则记录独立端口/PID | 真浏览器打开 `$IM_URL/settings/nodes`，确认资源来自受审构建 |

**Review 驱动方式**：端到端真实 Web 客户端，列表→详情→改名→返回、手机导航、更新/取消/重试/恢复说明、连接说明。状态准备可使用受控候选包/下载失败 fixture；IM、Node、更新子进程真实运行。视觉验收必须来自实际浏览器；原型与 DOM 断言不能替代。无需重新验收安装器、全局通知或物理 iPhone。

**验收前置**：本机已有 Node/pnpm、主仓 `.venv`、默认隔离配置与自动生成的 nano/nano1234 测试账号，全部使用隔离数据。feat-596 的真实更新夹具实现/记录在 PR #349 的 `apps/node/tests/node-updater.test.ts` 与归档 M1 evidence（实施时从依赖分支读取）；包构建与可重复更新故障路径已被前序真实验收，不需要新增公共 release、第三方账号或生产凭据。本 unit 前端改名/连接展示本身无需调用 LLM。M1 worker 接手需把实际启动命令、候选包、端口、PID 与受审 SHA 留入本 unit evidence 供 reviewer 复用。

## Milestones

| ID | 标题 | 依赖 | 并行组 | 范围 | 退出标准 |
|---|---|---|---|---|---|
| M1 | 电脑页面完整体验 | feat-596 | 单一 | frontend/features/settings/nodes、必要的本页安装说明复用、i18n、本 unit delta/evidence | A [reviewer] S1–S2：实际首屏身份/可用性/动作易读，桌面和手机密度合理，长名与主要动作不挤压；[worker] 四种 viewport 真截图与原型对照。B [reviewer] S3–S4：按需改名/诊断、失败保留草稿、返回上下文成立；[worker] 名称保存/取消/失败、离线及 heartbeat 回归与详情录屏。C [reviewer] S5–S6：更新各阶段和可行下一步真实清楚；[worker] 复用更新回归，真栈操作与阶段截图/录屏，证明无 POST/WS 状态倒退。D [reviewer] S7–S8：连接与查询异常下一步明确；[worker] 真实连接说明、copy 成功/失败、安装包缺失、读失败与 stale 场景证据；中英文构建、相关前端测试及 docs-check 通过。 |
