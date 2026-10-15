# feat-610 — 产品验收报告

> 对齐：spec.md 全部 7 个 Scenario；Round 1，full。
> Validation snapshot：`9182699fca58d42fbf166f3de7445c635dcb3527 → 33ef0d76d342a10c411ccbc0828f82d0d564e810`。
> 执行日期：2026-10-15（Asia/Shanghai）；checkout `codex/feat-610-workspace-tools`，开始时 HEAD 与 validated_at 一致、工作树干净。调用方已在此版本构建并准备隔离栈；reviewer 未修改实现或构建产物。

## Verdict

**pass**。7 个用户场景均完成真实产品路径验证；无 blocking / major 问题。Highest Required Action：pass。

## 用户旅程体验

通过 Web IM 使用的真实 HTTP 消息、配置、fork 和审批接口驱动 IM → Node → DSH → 真实 `deepseek:deepseek-v4-flash`。没有使用确定性模型，也没有绕过聊天直接调用 runtime RPC。没有更改客户端；本单元没有新增 UI，按 design Runbook 授权的接口代驱动，不声称浏览器视觉或移动端验收。

用户先建立带口令的既有聊天，再要求助手自己写一个整数翻倍工具。模型自行查阅已安装 DSH 的工具作者说明、写 package/patch/JS，随后调用 `plugin_manager` 安装并在同一轮实际调用新工具。Reviewer 只描述目标与产品手册中的 bundle 形态，没有代写成功实现。创作过程约 5 分钟，包含模型自行探索和人工审批等待；最终回复区分了安装状态与真实执行结果，并保留旧口令。后续同 workspace 另一聊天无需安装直接调用；另一 workspace 查不到且真实调用被拒绝。

首次配置准备将测试 Agent 的显式空工具集通过正常配置 API 设为 `read/write/edit/bash/glob/grep/plugin_manager`，符合场景 GIVEN 的“已获准管理与文件写入”；`web_search` 保持禁用。安装开始后未再改工具选择，两个新名字从未写入白名单。故意加载失败后收到 `application: failed` 和具体错误，模型修正同一源目录并重装成功。两次正常节点重启分别证明安装与撤销选择持久化。整个过程可由聊天结果完成判断，无需用户改白名单或以重启促使安装生效。

正常 Auto 审核数次返回 `Reviewer returned no valid verdict`，产品给出人工审批卡。Reviewer 在专用测试授权内通过正常 `allow_once` 路径批准具体读取/写入/工具执行；其余调用正常自动通过。未关闭 Auto 或扩大权限。该回退没有阻断目标，不把模型审批服务稳定性认定为本单元实现缺陷。

## 环境与证据

- IM：`http://127.0.0.1:54267`；节点：`wt-nano-multiagent-96374`；专用测试账号 nano。
- A：Agent `e2e`，workspace 为本 worktree `.gateway-workspace/e2e`；B：`e2e-peer`，`.gateway-workspace/e2e-peer`。
- A 原聊天 `c_pp1ump8j`；从初始口令回复 fork 的同 workspace 聊天 `c_c2gdxrqz`；B 聊天 `c_fnnsjlbc`。fork 在安装后进行，但取安装前口令消息为分叉点，第二聊天未继承安装操作正文。
- 本地完整 HTTP timeline 与 WS 事件：`/tmp/feat610-review/a-timeline.json`、`a2-timeline.json`、`b-timeline.json` 和同目录 `*.jsonl`。这些为本次本机证据，不提交。报告下方保留可复查消息 ID 和结果。
- 重启前 Node/DSH PID `96473/98548`；第一次正常 `pnpm pa restart --config <worktree>/.gateway-config.yaml` 后 `99934/99938`，新心跳 `2026-10-14T16:12:42.704Z`；第二次 `505/511`，新心跳 `2026-10-14T16:14:13.707Z`。两次 `pa status` 均 ready=true；只重启隔离节点，未动共享模型代理或生产。
- `before-restart.json`、`after-restart1.json`、`after-restart2.json` 保留配置与节点观测；前后静态白名单完全相同。

## Reference Artifacts Reviewed

N/A。spec/design 无原型、reference screenshot 或 must-match 视觉要求。已读取 design Runbook、worktree-runtime 与 current agent-capabilities spec。

## 问题清单

无阻塞问题。以下是证据边界，不作为本单元缺陷：

- A 中要求真实模型强行调用缺席的 `web_search` 时，模型未发该调用，曾重复调用其它已安装工具；用户补充“停止重复”后结束。A 的结论依据实际配置保持与模型可用目录缺席，不伪称获得了 A 的执行层拒绝。B 在相同静态工具选择下确实发出 `web_search`，得到 `UNKNOWN_TOOL`。不以模型自述代替其他场景的实际工具结果。
- Auto 分类偶发无有效判定，使用既有人工回退完成；未调查实现根因或修改审核配置。

## 验收标准覆盖

### Requirement: Agent 可自助创作并安装工具 — 组内结论：pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 在既有聊天创建并使用新工具 | spec.md 同名 Scenario；design Runbook | 原聊天先记口令，再由真实模型创作、安装、立即调用 | 用户 `02b8a1836578421db56efa06ea6838b1`；回复 `5396431d1906441286f02352c2b0acf6`：模型 write 三个 bundle 文件；install 返回 `application: applied`、`tools: [orchid610_double]`；调用 `n=21` 返回 `{value:42,marker:ORCHID610}`；回复保留口令 | pass | 安装未改白名单、未重启；真实工具调用而非 bash 计算 |

### Requirement: 新装工具按 workspace 隔离且持续可用 — 组内结论：pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 同 workspace 的多个聊天共享新装工具 | spec.md 同名 Scenario | 从安装前消息 fork 另一聊天，直接要求调用 | 聊天 `c_c2gdxrqz`，用户 `73b49d6123b74f1f92fd855f9efba8ad`；回复 `d4485057c54a454b9a2a108577035f06`，原生调用 `orchid610_double({n:17})` → `{value:34,marker:ORCHID610}` | pass | 新聊天未安装或写文件 |
| 其他 workspace 不获得私有工具 | spec.md 同名 Scenario | B 查管理列表与 capabilities；真实模型追加实际调用尝试 | 回复 `7cbb97059add42819d3c7fdbdf452f31`：`list_bundles={entries:[],diagnostics:[]}`；B capabilities 无 orchid 工具。回复 `4bb371bf31994388a1ce358a0294f0f1` 中实际 `orchid610_double({n:11})` → `ToolNotFoundError / UNKNOWN_TOOL` | pass | 无 B 安装；实际错误来自 tool result |
| 重启后继续使用 | spec.md 同名 Scenario | 正常重启隔离 Node 后继续 A 原聊天 | 用户 `1e061681d1c94394ac0ca64a9fecca45`；回复 `c32346bef98a47b19ed6a35b670fce9a`：double(31) → 62/ORCHID610；repair(31) → 32；原口令仍在 | pass | 未重装、未改配置、未新建聊天 |

### Requirement: 自建工具不改变其他已有工具选择 — 组内结论：pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 安装不重新启用既有禁用工具 | spec.md 同名 Scenario | 安装前排除 web_search；安装及重启后核对正常配置与聊天可用目录，新工具同时实调 | `before-restart.json`、`after-restart1.json`、`after-restart2.json` 的 allowlist 均只有准备时 7 项；A 回复 `b65603b2cb594182b9b1135cefcbf4cb` 的新工具 double(23) 实调 → 46，同时目录无 web_search；另一聊天 `1ddfa603e16c4b5fb7638e7d749b5cdd` 同样不可用。B 回复 `4bb371bf31994388a1ce358a0294f0f1` 的实际 web_search → UNKNOWN_TOOL | pass | A 未生成 web_search 调用，不能声称 A 派发拒绝已验；配置与可用目录保持证据成立 |

### Requirement: 安装与停用结果准确可恢复 — 组内结论：pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 安装失败后修正重试 | spec.md 同名 Scenario | 模型创作第二 bundle，顶层故意抛错，安装后调用旧工具，再自行修正重装并调用新工具 | 用户 `323bba044f924020a86ab1f30823c4fd`；回复 `f84b9ba1b2f5425cba52fffada113f80`：首装 `application:failed`，warnings 含 `ORCHID610_LOAD_FAIL`（包管理 exitCode=0 不掩盖加载失败）；double(9) → 18；模型重写 tool.mjs 后重装 `application:applied`，repair(9) → 10 | pass | 重装使用同源目录，无重启；未把失败声称为可用 |
| 停用或移除自建工具 | spec.md 同名 Scenario | 同聊天停用 double bundle、移除 repair bundle，立即尝试；再正常重启后查状态及再次实际调用 | 回复 `eaf55d06b8114acf8ad84cef84627d03`：set_bundle false / remove_bundle 都 applied，tools 最终 []；两工具 n=5 均 UNKNOWN_TOOL。第二次重启回复 `b0c82836429f46b9829e75b1f118f26f`：list 保留 double enabled=false、repair 缺席；两工具 n=7 均 UNKNOWN_TOOL | pass | 覆盖停用与移除两条分支，源目录保留；无需重启即可撤销，重启后不恢复 |

## 上层文档同步

- [x] `SPEC.md`：无需更新，本次未改变既有包边界。
- [x] `docs/specs/gateway/agent-capabilities.md`：需要由 orchestrator 收尾归并本 unit delta-spec；当前仍描述静态两层工具，尚未反映 workspace 自助安装自动启用例外。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新。
- [x] `docs/specs/CONTRIBUTING.md`：无需更新。

## 交付与清理

本报告未提交，遵守 caller 的“只写 acceptance.md、不提交”。Reviewer 未启动额外服务；隔离共享栈由 caller 最终清理。两次 `pa restart` 后应以实际 lifecycle state 核实当前 PID `505` / DSH `511`，不能将原 `.gateway.pid` 外部 marker 当作仍有效的当前进程身份。本地脚本、事件与 workspace 产物未暂存。

---

## Round 2 — targeted：配置页 workspace 工具状态

> Validation snapshot：`9182699fca58d42fbf166f3de7445c635dcb3527 → 4122379c8ef39fc110c553302ea23081830f595f`。
> fix_delta_range：`d8f3a6b0d..4122379c8`；2026-10-15 00:38–00:42 Asia/Shanghai。开始时 HEAD 对齐、工作树干净。调用方已构建并部署该版本至同一隔离栈；本轮不重启服务、不修改 e2e/e2e-peer 配置。

### Verdict

**pass（targeted）**。新增第 8 个 Scenario 的实际启用展示与继续调用路径通过；R1 七场景按下表保留。无新增 blocking / major / minor 产品问题。

范围按 caller 明确约束：真实浏览器验证桌面/窄屏启用路径；不为验收保存或关闭用户正在使用的 Agent 配置。保存不污染静态名单与 Unavailable 分支采用本轮前端/原生自动化证据并明确边界，不声称完成这两项真人操作或 Unavailable 实际画面观察。

### 实际用户体验与画面证据

Reviewer 创建自己的 Chrome 标签，仅访问 `http://127.0.0.1:54267/settings/agents/e2e`，未控制用户原标签。登录态为专用 Test User。桌面实际 CSS viewport `1537×944`，窄屏 `390×844`（校准浏览器已有缩放后的实际 innerWidth/innerHeight，不把请求尺寸冒充实测）。

- 原有 Tool Allowlist 的灰色/绿色可编辑 pill 保留。其下 Workspace tools 是独立标题、管理说明和只读工具卡，读者能区分“我可选择的静态工具”和“助手自动安装、现在已可用的工具”。
- 唯一 workspace 卡片是 `expense_summary`，名称旁直接显示 `Enabled`，下方有完整用途和输入说明。`schedule_run/history/create/list/delete/update` 均留在静态区，没有误分类为自建工具。
- 文案明确 `Managed automatically; no allowlist entry needed. Ask the assistant in chat to disable or remove a tool.`，用户不必猜测未勾选是否代表未生效。workspace 区没有按钮或开关（DOM 辅助核对 button 数量为 0）；静态 plugin_manager 按钮 enabled=true，页面保持 No changes / Save disabled。
- 窄屏中工具名与 Enabled 同行可辨，说明自然换行完整可读，提示与工具卡相邻；上下文仍保留静态工具区及下方模型选择。实际 document scrollWidth=390、innerWidth=390，没有横向内容溢出。没有观察到遮挡工具状态或迫使用户跨屏记忆其含义的问题。

真实页面截图（本地本轮证据，不是原型）：

- [桌面 1537×944](/tmp/feat610-review/r2/desktop.png)
- [窄屏 390×844](/tmp/feat610-review/r2/mobile390.png)

浏览器已有缩放使最初 requested 390 宽对应实际 487 CSS 像素；该中间截图 `mobile.png` 不作为 390px 结论依据。最终校准截图与上述实际尺寸对应。完成后 reset 临时 viewport 并关闭自建标签，用户原页保留。

### Reference Artifacts Reviewed / must-match 对照

已读 design 的“配置页状态补齐”、active IM delta、共同体验标准。`prototype.html` 仍是未渲染草稿：先前 file:// 策略拒绝没有被绕过，本轮不声称完成草稿像素级视觉对照。按已确认的设计契约和真实产品页面核验信息关系：

| Required contract | 实际证据与比较 | 结论 |
|---|---|---|
| 独立 workspace 来源 | 桌面/窄屏截图的 Workspace tools 区仅 expense_summary，与静态名单分开 | match |
| 实际启用状态 | 页面 Enabled；真实 capabilities 为 source_group=workspace、enabled=true、default_on=false；真实聊天实际调用成功 | match |
| 无需勾选及聊天停用说明 | 两种 viewport 都完整显示说明，无 workspace 开关 | match |
| 静态项仍可编辑，保存不添加 workspace 名称 | 静态按钮可编辑，workspace 零按钮；实际配置前后一致；下述自动化验证选择变化不携带 expense_summary | match，保存动作采用限定自动化证据 |
| 管理关闭的 Unavailable 状态 | 本轮没有关闭现有 Agent 管理能力；前端/原生用例覆盖 enabled=false 状态，未观察真实浏览器该状态 | 本轮真实画面未覆盖；按 caller 定向范围保留证据边界 |

### 继续使用与静态配置证据

从用户指定回复 `f5084f651ba04857b5473dd4b2f223b0` fork 自有聊天 `c_0ezz00si`，未向用户正在体验的原聊天发送消息。用户测试消息 `72c6c69b309c40d3a323e589f82c02e7` 请求汇总 2026-10：餐饮 12.5、交通 7.5、餐饮 20 元，另给 9 月 99 元应排除。

真实 DeepSeek 回复 `9434fdb1756d480aab3fe0162bd4e5e4`，工具调用 `call_00_zPNdKiudh5TYTVLwiVmZ8726` 直接调用 `expense_summary`，完成结果：`2026-10 支出汇总：3 笔，合计 ¥40.00；餐饮 ¥32.50；交通 ¥7.50`。没有安装、写文件或 bash 代算。本轮没有确定性模型替代。

`/tmp/feat610-review/r2/config-before.json` 与 `config-after.json` 完全相同，profile_version=3，tool_allowlist 始终是 `read/write/edit/bash/glob/grep/plugin_manager`，不含 expense_summary。`capabilities.json` 中仅 expense_summary 具有 workspace 来源。完整新聊天 timeline 与事件保留在 `/tmp/feat610-review/r2/chat-timeline.json` 及 `/tmp/feat610-review/r2chat-*.jsonl`。

### 自动化补充证据及边界

Caller 提供本轮结果，reviewer 读取日志核对通过数量，未读实现寻找根因、未修改测试，也没有重复运行全量：

- `npm test -- --run src/features/settings/agents/pill-selector.test.tsx src/features/settings/agents/agent-detail-page.test.tsx src/features/settings/agents/agent-create.test.tsx`：3 files / 37 passed，`/tmp/feat610-ui-frontend-tests.log`。Caller 说明新增交互用例经过 normalizeAllowlistOptions，静态 read 选择只产生 `[plugin_manager,read]`，不带 expense_summary；管理关闭 metadata enabled=false 的 rerender 显示 Unavailable 且不新增 onChange。此为组件交互覆盖，不等同真实浏览器点保存。
- `pnpm exec vitest run packages/dsh-integration/tests/workspace-tools.test.ts apps/node/tests/capabilities.test.ts apps/im-server/tests/control.test.ts`：3 files / 18 passed，`/tmp/feat610-ui-native-tests.log`。Caller 说明覆盖 late Cron 静态来源、无 manager/显式空集时 workspace_echo enabled=false、正常 enabled=true、default_on=false 及 IM route 字段投影。此为原生进程/接口证据，不等同 Unavailable 页面截图。
- 同版本全量补充：native 84 files / 314 passed（`/tmp/feat610-ui-full-tests.log`），frontend 95 files / 882 passed（`/tmp/feat610-ui-full-frontend.log`）。这些不取代本轮实际画面与真实调用。

### Scenario 覆盖

| Scenario | R2 结果 | 证据与继承理由 |
|---|---|---|
| 在既有聊天创建并使用新工具 | pass，retained | R1 自行创作/安装/同轮调用证据保留；本轮已装 expense_summary 原生继续调用成功，未要求重新安装 |
| 同 workspace 的多个聊天共享新装工具 | pass，retained + refreshed | R1 fork 调用证据保留；R2 新 fork c_0ezz00si 实际工具调用成功 |
| 其他 workspace 不获得私有工具 | pass，retained | R1 B 空列表和实际 UNKNOWN_TOOL 证据保留；本轮未改变 workspace 归属/管理状态 |
| 重启后继续使用 | pass，retained | R1 两工具重启后真实结果与旧口令证据保留；本轮不重启用户使用中的栈 |
| 安装不重新启用既有禁用工具 | pass，retained + refreshed | R1 选择保持证据保留；R2 前后完全相同的 7 项 allowlist，无 expense_summary；静态 web_search 仍未选 |
| 安装失败后修正重试 | pass，retained | R1 application failed、无关工具可用、模型修正后 applied 与结果证据保留；本轮未重跑破坏性失败旅程 |
| 停用或移除自建工具 | pass，retained | R1 在线撤销及重启后 UNKNOWN_TOOL 证据保留；本轮按 caller 约束不撤销用户当前体验工具 |
| 自建工具显示实际状态且不要求手工加白名单 | pass，new | spec.md 新增 Scenario 与 design must-match；真实桌面/窄屏只读来源+Enabled+说明、唯一 workspace 项；真实 fork 调用结果；实际配置未含工具名；保存分支按明确约束由上述交互自动化补充 |

R1 继承不表示旧进程旅程在新版本逐项重跑。该 delta 涉及 catalog 来源/状态及 UI，相关风险由 R2 真实 capability/画面/调用及 caller 原生完整回归覆盖，没有观察到使上述旧结论失效的副作用。

### 上层文档与清理

新增 `docs/specs/im/agents-nodes.md` 的配置页状态增量需 orchestrator 按最终实现归并；gateway delta 的收尾要求延续 R1。SPEC、AGENTS、文档体系无新增修改需求。

只追加本报告，不提交。未改两个既有 Agent 配置、未停启服务、未操控用户原浏览器标签；自建标签已关闭、临时 viewport 已 reset。保存/Unavailable 真人状态未执行的边界如上，未用测试成功冒充真实画面。

## Round 3 — 完整插件管理体验（2026-10-15）

- **validated_at**: `df579de5e8fb7c09626e132a28fd23f5663dae18`（实际运行服务版本；写报告时 HEAD 已前移，不将后续提交冒称已验）。
- **Verdict: fail / incomplete evidence**。观察到的主要用户旅程均通过，未发现 blocking/major/minor 产品缺陷（0/0/0）；但两个必验 Scenario 含尚未取得充分证据的分支，按 reviewer 门禁记为 inconclusive，不能以主要流程正常替代完整通过。
- 本轮 supersede R2 的只读 workspace tools UI 结论：当前产品为独立 Plugins 页签及整包管理。只追加报告，未改实现或测试。

### 环境、实际入口与整体体验

真实隔离 IM `http://127.0.0.1:54267`，Test User，节点 `wt-nano-multiagent-96374`，Agent e2e/e2e-peer。使用 caller 已准备的原生 Node/DSH 和真实模型。浏览器为自建 Chrome 标签；桌面及实际 CSS `390×844` 窄屏。使用既有登录与专用测试数据，不访问生产。

从 Agent 设置进入 Plugins，第一屏先说明 workspace 共享范围，再逐包呈现名称、描述、版本、实际状态和开关。零工具 `expense-report-style` 与工具包平等列出，未因工具数为零消失；详情承载来源及诊断，卸载需展开并确认具体包及共享影响。Config 保留原静态工具 pill，使用 Manage workspace plugins 跳转，旧只读 workspace 卡不再重复展示。开关不依赖 Save，等待时保留实际开关状态并禁用重复动作。空列表、失败、离线分别给出创建引导、诊断、无法确认提示，没有用空列表伪装请求失败。窄屏内容自然换行，实际 scrollWidth=innerWidth=390，操作未被遮挡。未发现整体信息层级或完成路径的交付障碍。

### 实际旅程与证据

1. 读取原真实创建 timeline：助手已在既有会话编写并安装 `expense-report-style`，使用 `systemPrompt.section`，零新增工具，与 `expense_summary` 一起产生报销月报。另在 reviewer 新聊天真实继续调用，无重新安装要求。
2. 浏览器关闭样式插件后，通过产品 prompt-preview 分别核对 e2e/e2e-peer 均撤销“标题固定为「报销月报」”贡献；重新开启即恢复。旧聊天仍可能沿历史模仿格式，因此不把旧聊天文风当成提示词是否撤销的证据。对应文件 `prompt-enabled.txt`、`prompt-e2e-disabled.txt`、`prompt-e2e-peer-disabled.txt`、`prompt-reenabled.txt`。
3. 实际 `bash sleep 35` 在途时关闭 expense-summary，页面显示等待空闲；在途请求正常完成 BUSY610_DONE（回复 `195fa333f1f04676938881d208d6c96b`），随后状态变为 Disabled。后续真实工具调用不能再找到 expense_summary。未取消任务或重建聊天。
4. 对 `orchid610-bundle` 经 Details→Uninstall→Confirm uninstall，确认页写明包与共享范围；列表移除，workspace 中原 `tool.mjs` 保留，其他插件未被移除。
5. 通过真实聊天让助手使临时 repair bundle 加载抛错 `R3_PLUGIN_LOAD_FAIL`，安装失败，页面保留条目并显示 Needs attention。浏览器将其关闭；助手修复并更新版本 0.1.1，install_bundle 省略 enabled，结果仍 false/applied，而非悄悄开启。显式开启后 `orchid610_repair(41)` 真实返回 42（回复 `7ecde40ae31e4370852ff9f3b921974b`）。
6. 在 idle 时正常 stop/start 本隔离 Node。停机页面显示 Status unavailable/503，保留旧列表并禁用动作；恢复后 style enabled、summary disabled、repair disabled/version0.1.1、已卸载 orchid 不复现。此证明已完成选择持久化和真实离线反馈，不证明 pending 中强制重启。
7. B workspace 的真实 Plugins 页面为空且有聊天创建引导，prompt 无 A 样式贡献；工具隔离沿用 R1 B 实际 UNKNOWN_TOOL 证据。静态 Config 七项 read/write/edit/bash/glob/grep/plugin_manager 未被变更。
8. 清理临时安装项，恢复两个体验包均 enabled。新建干净体验聊天 `c_dkpuwqw4`「插件体验：报销月报」，只有用户与 e2e。自然请求仅给三笔支出与分类，未指定月报格式；真实 `expense_summary` 返回 3 笔/80 元（交通50、餐饮30），模型输出报销月报、分类表和核票提示。回复 `dc4154c80ccf4df9b924bfa3ee784b0e`，真实调用 `call_00_oOnUD87qa2SjObFSpCnw4056`。聊天与服务保留供用户体验。

### Reference Artifacts Reviewed / must-match

已读当前 spec、design、IM delta 与共同体验标准，并查看 design-assets/plugins-states.png 概念状态板。HTML 原型因既有 file:// 策略未渲染，不声称像素级对照；以下按设计要求的信息关系与真实截图比较。

| 必须匹配的关系 | 实际证据（均 `/tmp/feat610-review/r3/`） | 结果 |
|---|---|---|
| 独立 Plugins 入口与共享范围 | desktop-list.png，实际设置页进入 | match |
| 整包开关、等待、最终真实状态 | style-disabled.png、pending.png、recovered-persistent.png | match |
| 错误、空、离线不混淆 | failed-plugin.png、empty.png、offline.png | match |
| 卸载确认明确包及范围、来源可查 | uninstall-confirm.png，源码保留核对 | match |
| 390px 无横向溢出、操作可达 | mobile390.png，实际390×844 | match |
| 可直接继续体验两个插件 | final-enabled.png、clean-demo.png，真实会话结果 | match |

### Scenario 逐项裁决

| spec Scenario | 结果 | 来源及实际证据 |
|---|---|---|
| 工具和非工具插件在既有聊天生效 | pass | 原创建真实 timeline、R1工具创建，以及本轮零工具 prompt 贡献/实际调用/干净月报 |
| 同 workspace 共享，其他 workspace 隔离 | pass | 同workspace两Agent prompt共同撤销；B空页面/无贡献；R1 B UNKNOWN_TOOL保留 |
| 已完成的选择跨重启保留 | pass | idle真实重启与recovered-persistent；已禁用同名修复更新保持false/version0.1.1 |
| 查看全部已安装插件 | pass | enabled/disabled/failed/零工具真实列表，详情及独立入口；B真实空态 |
| 关闭与重新开启整个插件 | pass | 真实工具和提示词撤销/恢复；事件资源生命周期由下述native测试补充，不冒称浏览器直接观察 |
| 卸载插件 | pass | 真实确认/条目消失/源码保留/其他插件继续调用 |
| 忙碌时等待安全应用 | inconclusive | 真实在途sleep未取消、等待到idle后应用通过；同workspace并发管理不覆盖/不死锁目前仅caller源码审查说明，缺独立对应执行证据 |
| 安装失败可以修复 | pass | 真实抛错诊断与异常条目，修复重装保持禁用，开启后真实42结果 |
| 离线或待应用期间重启 | inconclusive | 真实停机/恢复反馈通过；未在pending中重启，不能证明未完成操作恢复及允许重发分支 |
| 安装新插件保留既有禁用选择 | pass | 静态配置未改变、R1既有选择证据；显式空集/子任务/可信身份由原生与HTTP测试补充 |

### 自动化补充与边界

Reviewer 读取 caller 提供日志：`/tmp/feat610-plugins-native.log` 1 file/1 passed，`/tmp/feat610-update-green.log` 1 file/1 passed。Caller 说明包含根服务污染隔离、systemPrompt、异步 ctx.effect teardown、A排队且B继续、更新禁用保持；UI与HTTP补充日志为 `/tmp/feat610-plugins-ui.log`、`/tmp/feat610-plugins-tests.log`。这些用于原生生命周期/权限边界补充，未替代浏览器截图或冒称独立重跑。Caller 明确无 pending 强制重启专门用例，且并发模型管理主要由源码审查支持，因此如上保留 inconclusive。

### 交接与清理

体验入口：`http://127.0.0.1:54267/chat/c_dkpuwqw4`；管理入口：`http://127.0.0.1:54267/settings/agents/e2e?view=plugins`。两个体验包 expense-summary-bundle、expense-report-style 均启用。临时 orchid/repair 安装项已移除，源码保留。仅 stop/start 本隔离节点一次用于授权重启场景；没有停止 caller 的 IM/模型代理，最终服务保持运行。临时 viewport 已 reset，自建浏览器标签已关闭，用户原标签未动。

需要补齐的只是上述两项证据，未观察到需修复的产品缺陷。插件页目标行为的 current spec 归并由 orchestrator 处理。


### Round 3 补充裁决 — 新增原生并发与中断证据收口

**最终 verdict：pass，blocking/major/minor 0/0/0。** 上文“无相应用例”和两个 inconclusive 是补充材料到达前的阶段判断，现由本节明确替代；保留原记录以区分证据到达顺序。产品实际 validated_at 仍为 `df579de5e8fb7c09626e132a28fd23f5663dae18`，新增测试提交为 `c4ba8d5ead802dbfaa911e0cd7ff5c0e6dd1198a`，该提交只改一个测试文件（7 additions / 1 deletion），未改变受验产品实现。

Reviewer 独立读取 `/tmp/feat610-pending-restart.log`（1 file / 1 passed，14.05s）并核对新增测试实际断言。它通过 RuntimeClient 启动真实 DSH subprocess，不是仅 mock 页面状态，也不只基于 worker 成功叙述：

- 真实 session 进入 running，网页等价 `plugins.manage` 设置停用形成 pending；同 workspace 另一个 session 的 `plugin_manager` 再发管理请求真实返回 busy；原任务继续完成，pending 清除，目标工具从两 session 撤销。此与本轮实际网页 waiting→Disabled 和原请求完成的证据共同覆盖并发不覆盖、不死锁。
- 当前插件已 disabled；真实 session running 时再次请求开启产生 pending，随后明确 `client.process.kill('SIGKILL')` 并等待 exited，在同一持久目录启动新 subprocess。恢复后 pending 不存在，旧 disabled 状态仍使 capability 不含工具；重新发开启请求可成功应用并真实调用返回 USER_ENABLED_AGAIN。该证据验证中断前未完成的开启没有被误记成功，并允许重发。

| 原 inconclusive Scenario | 最终结果 | 完整证据组合 |
|---|---|---|
| 忙碌时等待安全应用 | pass | 54267 实际网页等待、在途请求完成、终态Disabled + 新原生真实peer管理busy/共享撤销 |
| 离线或待应用期间重启 | pass | 54267 实际离线不可确认、保留旧列表、恢复展示 + 新原生SIGKILL pending/磁盘旧状态/重新发起成功 |

这是原生边界和页面体验的组合证据，未声称在 54267 浏览器页面打开时执行过 pending SIGKILL。现有真实网页已覆盖相关不确定态与恢复体验；新增真实 subprocess 已覆盖缺失的中断持久化及并发行为，足以完成这两个 Scenario，无需再次干扰保留给用户体验的服务。十项 Scenario 最终均 pass，must-match 对照齐全。此补充只修改验收报告，没有重启或停止最终体验服务；干净聊天 `c_dkpuwqw4` 未追加测试消息。

## Round 4 — 第三方 rollover 插件独立增量验收（2026-10-15）

- **mode**: targeted；第三方标准包安装、workspace 配置恢复、真实 rollover 与持久笔记回读。此前完整管理旅程沿用 Round 3 最终结论；本轮不冒称重验开关、卸载、并发和重启。
- **validated_at**: `084b4ac18`；executed_base `48ecbfec267343bf6df6f2d577c21fb1a8ea7733` + 本提交增量。Caller 确认 DSH integration、PA、Node 已 build，11:26:55 重启的 Node 11849 / DSH 11859 对应此源码；Web/IM 无增量沿原产物。Reviewer 不重启服务。
- **verdict: pass**；本次范围 blocking/major/minor = 0/0/0，highest_required_action=pass，needs_re_review=false。
- 独立身份：新建 Global Agent `rollover-independent-1015`（原生插件独立验收 · 雾松），新默认 workspace；模型 `codexOAuth:gpt-6.1-sol`、推荐中强度，其他默认。新主 Session `89d8a060-2be3-41d3-83c2-2f4d527f0172`，聊天 `c_9w6n1cua`。从 Nano Web 真入口创建并发送一次自然请求，未复用 caller 样本或旧失败上下文。

### 请求、恢复与可观察结果

请求安装 GitHub 项目 athif23/dsh-context-rollover，允许官方 npm 预构建包，禁止批准/运行 GitHub 构建脚本与修改宿主；用插件保存“验收代号雾松-842，预算1357元”，实际 rollover 后读回。Reviewer 没有教配置命令、代安装、代写 workspace、修改源码或补发干预提示。

Agent 自行读 nanoassistant-docs 与官方 README，安装 npm `dsh-context-rollover@0.2.2`。默认 compaction 注册冲突如实返回 failed；Agent 自行将已有 context-rollover 行在 workspace user overlay 配置 isolate.compaction、modelSurface=always 与 workspace notesDir，随后 diagnostics 为空。首次 new_context 返回接受但没有实际替换；Agent 对照上下文用量和已装官方包实现，自行识别默认保留尾部过大，并仅将 workspace retainTokens 调至 2048 后重试。未把第一次请求接受冒称成功。

### 原生与页面证据

所有独立证据位于 `/tmp/rollover-independent-1015/`：完整解压 `session.jsonl`，抽取 `compaction.json`，`plugins-enabled.png`，`chat-final.png`。来自原生 session.v4.jsonl.zstd，sessions 数据库按本 Agent 精确取得 session_id。

| 必验结果 | 实际证据 | 裁决 |
|---|---|---|
| 新 Agent 自助安装官方第三方包并恢复配置冲突 | tool/call57 install_bundle；58 原始冲突；69 自主 workspace edit；183 list_bundles installed=true/enabled=true/diagnostics=[] | pass |
| 插件真实保存指定状态 | notes.write87/result88 成功保存 acceptance-wusong-842.md | pass |
| 真正执行 rollover，非请求接受 | new_context153 后 compaction/start156、summary157、end159；compactionId=65299a85-556e-4991-9ad1-ad5c87169e44；provider=dsh-context-rollover；model=deterministic/window-1；shadowedRange10–134、shadowedTokenCount17536 | pass |
| rollover 后通过插件回读并恢复历史 | notes.read171/result173 完整返回雾松-842/1357；history172/174及180/181恢复旧请求；get_context_remaining175/176显示约16468tokens | pass |
| 用户收到真实最终交付、插件页状态准确 | send_message200/result201 status=sent，message6bbc64f4ddf74204a6c08b1aa75cf9bf；浏览器可见完整最终回复；插件页0.2.2已启用；turn/end206 completed | pass |

### 体验与范围边界

已读本 unit spec/design/current gateway 契约与共同体验标准。真实桌面视口约1538×1014：插件卡片明确显示名称、版本、描述、开关和已启用状态；下方说明同 workspace 共享。聊天内先确认任务、再报告冲突恢复进展、最终明确区分首次无效请求与实际 rollover，用户能辨认过程和最终结果。此增量未改变布局，原型结构和其他管理状态沿 Round 3 证据。

Side observation：该浏览器测试身份出现“实时更新暂时繁忙，30秒重试”提示，刷新后可读已持久消息；未发现其改变插件执行与最终投递结果。实时无刷新投递不由本轮证明，此现象关系未明且不据此扩展插件增量结论。

服务与插件均保留，未启动额外服务、未重启或停止 caller 服务。Agent 默认技能创建能力另自主写入了 workspace-rollover-acceptance skill；它在 rollover 及回读之后产生，不是安装成功的前置。第三方包重启持久性由 caller 后续单独验证，本轮不借用尚未发生的证据。

- Chat: `http://127.0.0.1:54267/chat/c_9w6n1cua`
- Work: `http://127.0.0.1:54267/settings/agents/rollover-independent-1015?view=work`
- Plugins: `http://127.0.0.1:54267/settings/agents/rollover-independent-1015?view=plugins`

本轮按 caller 指令只追加报告，不提交。上层 current/design 已包含配置入口及 preset compaction 让出约定，本轮未发现需新增的契约差异。
