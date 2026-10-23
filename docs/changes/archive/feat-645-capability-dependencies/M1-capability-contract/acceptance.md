# feat-645 — 独立产品验收报告

> 对齐：[spec.md](../spec.md)、[design.md](../design.md)、[prototype.html](../prototype.html)
>
> Round 1，full；2026-10-24 00:48–01:00 Asia/Shanghai。
>
> Validation snapshot: `850e6cd82547c083655bc69d5de465105fd5eeac`。此 SHA 为实际 checkout；产品代码 `9802c9347`，`850e6cd82` 为测试类型夹具。使用 caller 已构建并启动的本 worktree 同源 IM/Web 与 Node/DSH，未无条件重建或接管生产。

## Verdict

**fail**。15 个必验 Scenario 全部列入下表；部分共享语义通过，但新卡片实际发布失败，且原生 Toast 的必需交互证据不足。不能以构建、fixture 或 Web 窄屏替代这些结果。

环境：`http://127.0.0.1:54795`；隔离用户 Test User (`nano`)，节点 `wt-nano-feat645-e2e-6nVL2z-26600`，e2e/e2e-peer 测试 Agent。HTTP health 返回 ok；页面 owning node、workspace 与派发环境一致。浏览器由 reviewer 独立创建 CUA IAB 标签；没有操作 caller 标签。浏览器正常宽度 1280×720，并实测 1440×1000、768×1024、390×844。实际工具调用只涉及当前隔离聊天及测试任务/安排。

## 用户旅程体验

### J1：配置依赖、共享选择及保存

从 Agents 列表打开 e2e，初态为六 Feature 关闭、部分普通工具开启。打开 Task 后，Cron 和六个 schedule 工具一起选中；取消 Cron 时保持开启，提示 `Turn off “Task Graphs” first`。依次打开其余 Feature，read/skill、memory/skill_manage、send_message 与 nano-interactive-ui 的选中状态符合 D1。

关闭 Memory、Intelligent UI 时，memory、send_message、命名 Skill 默认取消，而 read/skill 因其他 Feature 仍依赖而保留。关闭最后使用者后 read/skill 取消。尝试关闭受保护 read、skill 和 nano-interactive-ui 时，选择保持、没有反关 Feature；单依赖提示直接指出 Feature，多依赖用简短泛化文案，符合 design 的已定稿决定。工具旁没有新增常驻归属标注。

同一草稿关闭全部 Feature，再单开 schedule_create、task_graph、memory、skill_manage、read、send_message 和 nano-interactive-ui，关闭普通默认工具 web_search，保存为 v3，另开页面重读得到同样选择。后续补开 skill 并保存 v6，全部 Feature 仍关。稳定提示词预览已实际展开、加载完成；未发现 nano-cron/nano-task-graphs/nano-heartbeat/nano-interactive-replies 的额外 section。新建页实际打开，默认 Task/Cron 同为开启；未新建额外 Agent。

页面沿用身份、Behavior、Access & Model 分区；选中态区分明显，配置保存后显示 No changes 和新版本号。反馈在触发控件上方，不挤开控件，不需要关闭按钮。390 下长 Cron 提示自然换为两行，左右边界及点击目标均可见。工具数量较多使操作需要滚动，但本次没有增加常驻依赖文字。整体 Web 配置流程可理解且可完成。

### J2：真实责任保护及解除

通过 e2e 聊天实际调用 schedule_create 和 task_graph，而非写 DB：

- `tg_ff654f80/n1` 先创建 todo，随后 claim 为 doing（revision 2），再关联未来安排变为 waiting（revision 3）。doing、waiting 时分别尝试关闭 Task，均保持开启并提示 `Pause or finish active and waiting tasks before turning off Task`。
- 未来安排 `schedule-ca108273-24e9-4974-9a60-f6329f8212b8` 标题“645关闭保护”。Task 关时、Cron 开时尝试关 Cron，显示 `Disable or delete active schedules before turning off Cron`，没有通过配置动作删除安排。
- e2e 仍为 waiting 时，e2e-peer 关闭 Task 并保存 v2 成功，未受其他 Agent 责任阻碍。
- 明确要求模型将测试任务 paused（revision 4）并删除上述安排，真实工具成功后 Task/Cron 可关闭；任务记录保留。这里的暂停、删除来自单独明确的测试操作，不是 Feature 关闭的副作用。

390 下 Cron 控件矩形在触发前/后均为 x=42、y=379.4453125、w=13、h=13，父卡片 x=29、y=366.4453125、w=326、h=72.796875，键盘 Space 后焦点仍在原 checkbox。受保护 skill 工具显示/消失过程 rect 为 x=29、y=372.0546875、w=60、h=28，选中态与焦点均保留。看到提示自然消失；本轮未独立精密计时约 2 秒和重复点击的延长时长，复用实施者相应窄测作为补充，不冒充逐帧观察。

### J3：Feature 关闭后的真实工具执行

v6 全部 Feature 为 false，单开工具实际得到：

- schedule_create 创建 `schedule-ace1c85a-77d5-4535-9124-a556115c519f`，10 秒后到期。当前执行收口后，聊天真实出现 `TOOL_ONLY645_FIRED`（00:58）；这段期间没有重新开启 Cron。
- skill_manage list 成功，skill 按需加载 nano-interactive-ui 成功。没有通过开启 Skill Creation 才获得工具。
- 前面 v3 全 Feature 关时 task_graph create 已成功，任务最初保持 todo；后续 doing/waiting 是明确测试请求，不将其当作自动续跑。
- 交互卡片未成功：模型按加载的 Skill 构造 OpenUI Card，经 Allow once 后 `send_message(target=current, interactive=...)` 返回 `Error: IM rejected the request: invalid_scope`；改为当前聊天 ID `c_ft74pwy6` 再发仍同错。实际轨迹展开显示原始参数与错误，当前聊天没有新卡片。未根据模型解释断言根因，更未把错误归因到具体实现。

独立审批仍在链上。自动 reviewer 返回 deepseek-v4-flash 不支持 reasoning effort low，产品展示 Needs review；本轮只对已授权隔离调用使用 Allow once。模型后续尝试纯文本回退，reviewer 点击 Deny 结束该无关回退，未扩大外发。此审批环境问题不等于 Feature 关闭，也不被静默绕过。

### J4：原生与部署证据边界

CUA `getApp('Simulator')` 一次读到专属 Nano feat645 iOS 26.4 主屏。scroll/drag 未改变状态，点击系统搜索再次返回 `-10005 timeoutReached`。caller 随后确认取消 xcodebuild 后 booted 设备为空。未进入 Nano 原生配置，未观察保护 Toggle、VoiceOver、焦点或安全区；原生结论 **inconclusive**。既有 iOS 21 tests/5 suites 与 build 只作功能/编译补充。

经 caller 允许，复用本 unit 一次性整理及正常 Node restart 的专门证据；reviewer 独立读取 before.yaml/prepared.yaml/deployment-check.json，确认顶层除 agents 外完全相同，三个 Agent 只变 features/tool_allowlist；记录各自 Cron false→true 与九项缺失工具补齐。读取 `evidence/restart-choices.json`，before/after 的 features、skills、selection mode、tool_allowlist 相同，equal=true，版本为 1ce3925a3。该历史验证是配置选择保留的有限证据，不冒充本轮再次重启。当前 850e6cd82 真实 UI 仍能保存并执行 tool-only 组合，未发现使该重启结论失效的新证据。

## Reference Artifacts Reviewed

阅读 prototype.html 的局部浮层、依赖转换与独立 iOS 意图设计，design-evidence/README.md 的 R4 修订和 design 原型契约；没有以历史原型截图代替本轮产品截图。

| Reference | Required contract | Actual product evidence | Viewport / state | Comparison conclusion |
|---|---|---|---|---|
| prototype Feature/工具选择；design D1 | Task→Cron，共享 read/skill，默认关联关闭，无新增归属字样 | J1；[1440](evidence/acceptance-web1440-cron.png)、[768](evidence/acceptance-web768-cron.png) | 1440/768/390；创建默认/详情草稿 | match（配置可见语义） |
| prototype 浮层；design R3/R4 | 脱离布局、就近、长提示换行、不盖触发项、保留焦点 | J2；[Cron 390](evidence/acceptance-web390-cron.png)、[Task 390](evidence/acceptance-web390-task.png)、[waiting](evidence/acceptance-web390-waiting.png)、[Skill](evidence/acceptance-web390-skill.png) | 390×844、768×1024、1440×1000 | Web match；精确延时以相关窄测补充 |
| 原生 Form Toggle must-match | 原生保护 Toggle、VoiceOver/焦点、安全区 | J4，CUA 主屏读取/点击超时 | 专属 Simulator | inconclusive，不能用 Web 390 代替 |
| 同草稿关闭再单开保存 | 不反开 Feature、不丢最后选择，实际执行 | J1/J3，v3/v6 重读与真实调度/Skill；[卡片失败](evidence/acceptance-card-failure.png) | Web 详情、当前隔离聊天 | 配置 match；新卡片结果 fail |

## 问题清单

| # | 严重度 | 现象 | 处置 |
|---|---|---|---|
| A1 | major / blocking | Intelligent UI 关、send_message 开、Skill 实际加载后，当前聊天合法结构卡片请求经审批仍 invalid_scope，未发布新卡片。首次 target=current，第二次明确 c_ft74pwy6。 | 交 caller 核实 scope/运行入口前置或实现；修正后 targeted 重验实际发布。reviewer 不读实现定位。不能以“工具已选中”放行 M1-R3。 |
| A2 | blocking evidence gap | 原生必须的保护 Toggle、VoiceOver/焦点和安全区未实际观察。 | 恢复可操作的专属 Simulator 后补原生局部验收；不要求重跑完整后端矩阵。 |
| A3 | blocking evidence gap | 尚未独立建立真实 Memory/Skill maintenance busy、Heartbeat 在途状态；没有 Personal/Global 两条实际新卡片成功证据；memory 写入与后台不自动维护未完成真实观察。 | 补明确的隔离状态和对应真实入口结果；已有集成测试只能支撑已覆盖语义。 |
| A4 | environment issue | 自动审批模型不支持 low，正常工具每次进入 Needs review。 | caller 单独记录环境限制；本轮使用明确的 Allow once，未禁用审批。不是本 unit 根因裁决。 |

## 验收标准覆盖

### Requirement: Feature 开启 SHALL 保证完整依赖 — 组内结论：inconclusive

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 开启功能时补齐依赖 | spec 同名；design D1/R1 | 六 Feature 草稿开关；实际 Skill 加载、Task waiting | J1/J2/J3 | inconclusive | 可见依赖补齐通过；六项开启后全部真实功能完整性未覆盖，Memory/Heartbeat 在途缺口见 A3。 |
| 开启 Task | spec 同名；design D1 | Task 开启、保存、真实 waiting 关联未来安排 | J1/J2，tg_ff654f80 revision 3 | pass | Cron 自动开启、六个工具选中，等待校验实际成功。 |

### Requirement: 单独工具选择 SHALL 真正生效且不附带启用 Feature — 组内结论：fail

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| Feature 关闭时单独打开工具 | spec 同名；design D3/M1-R3/R4 | v3/v6 单开真实工具调用及 preview | J3、卡片失败截图 | fail | 调度到期、Task create、Skill list/load 成功；新卡片 invalid_scope。memory 写入/后台维护仍缺证据。 |
| 关闭 Feature 后重新打开工具或 Skill | spec 同名；prototype 同草稿保存 | 草稿关闭再重开，保存重读及工具调用 | J1/J3，v3/v6 | fail | 最后选择保留且 Skill 真能加载；send_message 新卡片预期未兑现。 |

### Requirement: 关闭 Feature SHALL 联动工具与 Skill 并保护共享依赖 — 组内结论：pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 允许关闭时联动关联选择 | spec 同名；D1/D4；prototype | 开六项再逐项关，检查 shared read/skill、命名 Skill、schedule 工具 | J1/J2 | pass | 最后使用者关后默认取消；Task 关未级联关 Cron；无归属常驻标注。 |
| 默认工具仍可选择 | spec 同名；D2 | 关闭 web_search，保存 v3 再读 | J1 | pass | 非固定工具未被默认值锁定，重读为未选。 |

### Requirement: 仍被需要的能力 SHALL 阻止关闭并轻量提示 — 组内结论：inconclusive

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 关闭已开启 Feature 的必需工具或 Skill | spec 同名；原型 must-match | read/skill/nano-interactive-ui 点击，窄屏/键盘及前后位置 | J1/J2；Skill 截图 | inconclusive | Web 选择/浮层通过；原生指定体验缺口 A2。 |
| Task 阻止关闭 Cron | spec 同名；原型 must-match | 无任务时 Task 开并点击 Cron；三宽度观察 | J1，1440/768 截图 | pass | 不需 doing/waiting 即保护；开关不反转，说明直接原因。 |

### Requirement: 有进行中或等待中的责任 SHALL 阻止关闭 Task — 组内结论：pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 仍有责任时关闭受阻 | spec 同名；D5；prototype | 真实 doing revision 2/waiting revision 3 分别关 Task | J2，Task/waiting 截图、工具结果 | pass | 配置拒绝，没有通过关闭操作暂停/删除；后续仅显式请求才到 paused revision 4。 |
| 不存在上述责任时允许关闭 | spec 同名 | e2e waiting 时关闭 peer；明确暂停 e2e 后关闭它自身 | J2，peer v2/e2e v6 | pass | 其他 Agent 的责任不阻碍；原图仍保留。 |

### Requirement: 有生效中的定时任务 SHALL 阻止关闭 Cron — 组内结论：pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 定时责任阻止关闭 | spec 同名；D5；prototype | 真实 600 秒安排，Task 关时取消 Cron | J2、Cron 390 截图 | pass | 保持开并提示先停用/删除，原安排继续可见。 |
| 无依赖及定时责任时允许关闭 | spec 同名 | 明确删除 active 安排，关闭 Task/Cron 后保存 | J2/J3，v6 | pass | 历史任务保留；后续单开 schedule_create 真可到期执行。 |

### Requirement: 各配置入口及真实执行 SHALL 遵循同一规则 — 组内结论：fail

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 保存与实际使用一致 | spec 同名；M1-R3 | Web 保存重读、真实调用；复用契约测试仅作补充 | J1/J3/J4 | fail | 卡片实际失败 A1；原生入口及 API 关闭拒绝未独立补齐。 |

### Requirement: 升级 SHALL 保留已开启 Feature 并由部署 Agent 补齐依赖 — 组内结论：pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 整理已有不完整配置 | spec 同名；deployment-prompt | 复用 caller 隔离演练，独立比对 before/prepared 与变更记录 | J4；validation.md 部署演练 | pass | 三 Agent Cron false→true、缺失工具补齐；顶层及其余 Agent 字段保留；无生产操作。 |
| 后续合法选择不被迁移覆盖 | spec 同名；deployment-prompt | 复用本 unit 正常 Node restart 前后逐项比对；本轮再保存合法 tool-only | evidence/restart-choices.json；J1/J3 | pass | restart 证据实际版本 1ce3925a3，未冒充850e6cd82再次重启。 |

## 退出标准补充与未完成范围

- M1-R1：六项可见联动、默认 Task→Cron、共享依赖通过；新建页默认已观察。
- M1-R2：Task/Cron 真实责任和 Web 反馈通过；原生、Memory/Skill/Heartbeat 在途部分 inconclusive。
- M1-R3：配置/预览/Skill 通过；普通 e2e 新卡片 fail；Global/Personal 两路径 inconclusive。
- M1-R4：全 Feature 关时 schedule_create 到期 pass，task_graph create 和 skill_manage list pass；memory 合法写入/三类后台不自动行为的完整观察 inconclusive。
- M1-R5：继承并独立核对本 unit 的隔离整理与重启记录，pass。

## 上层文档同步

- [x] `SPEC.md`：无需更新，当前结果没有改变跨包架构裁决。
- [x] `docs/specs/<包>/`：需要更新；unit 已有 gateway agent-capabilities/task-graphs/heartbeat-cron 与 im agents-nodes delta-spec，须由 caller 在失败项处理及最终实现校正后归并，当前不宣称 canonical 已反映增量。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新。
- [x] `docs/specs/CONTRIBUTING.md`：无需更新。

## 资源与交接

reviewer 未修改实现、测试、设计或生产配置，未提交。仅报告与必要截图交 caller 统一处理。测试图 tg_ff654f80/n1 已明确暂停、保留；600 秒 active 测试安排已明确删除；两项短提醒已到期。e2e 最终 v6（全部 Feature 关、若干单开工具），e2e-peer v2（Task 关）；caller 拥有临时服务与最终清理。本轮自建 IAB 标签结束时关闭、viewport override 清除。无声称生产部署/公网稳定验收完成。

---

## Round 2 — targeted 复验（2026-10-24 01:01 起）

本轮追加，不覆盖 Round 1。第一段修复冻结点 `629c6aff7`（普通/Global 卡片、Memory/Skill maintenance）；个人助手目录修复后冻结点 `e725603ed5d4c8d799ed5c38055a9b4a5bf7c3ce`（正常 Node restart 后 PID 69004 / DSH 69038，caller 交接 ready/connected；后半段实际 PA、新心跳与原生保存）。普通/Global 的修复前结果作为历史失败保留。未改变产品实现、审批策略、模型或生产现场。

### R2-J1：卡片与单开 Memory 工具

- e2e 在 v6 六 Feature 全关时，按需加载 nano-interactive-ui，`send_message` 实际向当前 `c_ft74pwy6` 发布新卡片成功；可见 Interactive reply，消息 ID `e7b65d17cba04eceb5eebb885783d238`。[普通卡片](evidence/acceptance-r2-single-card.png)。同回合 `memory` 合法追加“本 workspace 是 feat645 隔离验收工作区，验收数据不得作为生产事实”，工具成功，回读确认；不是通过恢复 Memory Feature 获得写入能力。用户档案文件未写。
- Global e2e-global：从默认配置关闭六 Feature，在同草稿重开 skill 和 nano-interactive-ui，固定 send_message 保留，保存 v2。实际新会话发布标题“Global645验收卡片”、正文“Feature关闭，消息工具仍可发布新卡片”的 OpenUI Card。[Global 卡片](evidence/acceptance-r2-global-card.png)。
- Personal：UI 新建“645验收个人助手”并 Retry setup，曾真实失败 `The change was not saved. Please retry`，保留[原失败画面](evidence/acceptance-r2-personal-setup-failure.png)。caller 修复新 workspace 前置后正常重启。重开的 Web 页面仍显示 setup in progress，点击侧栏与 onboarding 的 Open personal assistant 只回空聊天页，未提供 Retry；此旧恢复入口问题单列，不伪装 UI 成功。
- caller 通过正常认证产品 API 读取原 creation.request_key，并用相同 key/node/name POST `/im/v1/personal-agent`，返回 HTTP 201、binding active。没有改 DB 或更换身份。这是明确的环境恢复辅助。reviewer 随后从真实侧栏进入原 PA `pa_29dcc09b9e55` / `c_9d2b68d1c45c`，六 Feature 关闭、skill/nano-interactive-ui 单开、send_message 固定保留，保存后请求显式新卡片。实际可见标题“PA645验收卡片”、正文“Feature关闭，个人助手仍可发布新卡片”。[Personal 卡片](evidence/acceptance-r2-personal-card.png)。

A1 的真实调用失败已关闭；普通、Global、Personal 三条新卡片发布链均有实际用户可见结果。额外指导未反开，前轮 preview 结论继承。

### R2-J2：真实维护与心跳占用

- e2e 开启 Memory/Skill 保存 v7；通过真实聊天读取记忆并提供新的长期日期格式约定，明确前台不调用 memory/skill 写入，允许后台复盘。前台收口后分别点击关闭 Memory 与 Skill，均保持 checked，显示 `This capability is in use. Try again shortly`。[Memory busy](evidence/acceptance-r2-memory-busy.png)、[Skill busy](evidence/acceptance-r2-skill-busy.png)。随后聊天显示 `Background self-evolution: memory updated`，隔离 MEMORY.md 真实包含日期约定，来源 session `a973a9c1-74fe-43f7-8fd5-fcabbc81b845`；关闭尝试没有取消已接纳维护。
- Heartbeat 初次使用 `bash sleep 20` 形成忙态时，真实 tick 触发，但自动 reviewer 不支持 low，unattended 拒绝命令。这一轮仅证明 tick 与拒绝，不充作成功忙态保护；[审批限制](evidence/acceptance-r2-heartbeat-reviewer-block.png)。没有为通过验收关闭审批或切模型。
- 改用同隔离 workspace 的顺序 read 工作负载，不涉及外部发送、任务改写或 bash。6 次读取的真实 tick 已完成；为捕获忙态，将本次临时 HEARTBEAT.md 通过真实聊天/Allow once 改为 30 次交替读取。`capability-usage` 在 `2026-10-23T17:24:01.802Z`、`17:24:19.201Z` 均返回 `busy=[{kind:feature,name:heartbeat}]`，active tasks/schedules 均 0。加载完成后点击关闭 Heartbeat，保持 checked 并提示同一 in-use 文案。[Heartbeat busy](evidence/acceptance-r2-heartbeat-busy.png)。该回合继续完成，聊天出现 `HEARTBEAT645_READ_OK`，32 tools / 49.2 秒；没有因为关闭动作被中断。
- 结束时短周期下一轮可能再次占用，先将 cadence 60 minutes 正常保存 v12，再在空档关闭 Heartbeat 保存 v13。期间一次旧 profile_version conflict 明确刷新重读处理，没有覆盖冲突或强行停止 run。最终 v13 六 Feature 全关。Memory/Skill 与 Heartbeat 的真实在途保护缺口已闭合。

### R2-J3：原生指定交互

caller 恢复仅本任务 Nano feat645 模拟器后，reviewer 实际进入 Nano IM 登录页，先将默认服务改为 `http://127.0.0.1:54795`，再用专用 nano 身份登录。通过 Agent tab → E2E Agent → Configuration 操作，未登录生产。AX 的 Scroll Down/Up secondary action 可用；未依赖失败的拖动手势。

原生真实结果：六项均以 switch 暴露名称和值；开启 Task graphs 后 Scheduled jobs 自动从 0→1，Tools 17→22；点击关闭 Scheduled jobs 保持 1，AX 可读 `Turn off “Task graphs” first`；关闭 Task 后可关 Scheduled jobs。Skill Creation 开时点击 skill，保持 1，AX 可读 `Turn off “Skill creation” first`。固定 new_context 点击保持 1，实际浮层显示 `This capability is required by the current mode`；消失前后相邻控件位置一致，未占 Form 行，未越安全区。Heartbeat 关闭与随后配置保存均收到 `Configuration confirmed by the node. Chats adopt it on the next turn`，Web 随后读回相同状态。

证据：[原生依赖](evidence/acceptance-r2-native-dependency.png)、[浮层显示](evidence/acceptance-r2-native-toast-visible.png)、[浮层消失](evidence/acceptance-r2-native-toast-dismissed.png)。截图为本任务模拟器窗口 714×1660（含 Simulator chrome）；没有把它描述为 Web 390 模拟。

reviewer 独立比对安装产物与 `/tmp/nano-ios-feat645/Build/Products/Debug-iphonesimulator/NanoIM.app/NanoIM` 的 SHA-256，均为 `1f5031b3fa1a6e5df8d2de47c9186f5ba10110ee751373842777db97e7645e9e`。caller 提供该产物 00:40:25 构建、Swift 最后修改已在内、后续产品修复未改 Swift；本轮不是对陈旧的另一个 app 冒认验收。

**仍未观察真实 VoiceOver 播报或 VoiceOver 焦点**。AX 能读出 switch 和提示，但聚焦项报告为 Simulator window，不能据此声称 Toggle 焦点保留。caller 引用 Apple 官方说明 Simulator 不提供 VoiceOver；本轮没有改主机辅助功能或伪造设备播报。设计 D254 的这项要求只有真机补测或明确批准的范围调整才能解除，原生安全区/交互已测不等于播报已测。

### R2 范围调整与最终裁决

在 caller 向用户说明“实体 iPhone 与本次已完成的真实 iOS Simulator 不同，唯一未测为 VoiceOver 实际播报/焦点”后，用户明确回复 **“不用不用这个。”**。caller 将该回复作为本次明确排除 VoiceOver 真机验证的授权转交 reviewer。本轮据此只解除该项交付门禁；不把未测项改写为通过，不声称具备真实读屏焦点证据。该范围调整不降低其他场景标准。

**Verdict：pass（按用户明确调整后的验收范围）**。Round 1 的 A1 已通过真实卡片复验关闭，A3 的真实维护/心跳占用与多发布路径已补齐；A2 的真实 Simulator 交互/AX/安全区已补齐，VoiceOver 真机播报/焦点按用户授权排除。未发现本 unit 在当前范围内仍阻塞交付的产品问题。旧 PA setup 恢复入口、审批 low 参数与 real-time reconnect 是独立环境/既有流程限制，保留说明，不扩大实现，也不宣称它们已修复。

### R2 覆盖矩阵（15 Scenario；未受影响项引用 Round 1）

| Scenario | R2 证据及继承依据 | 结果 |
|---|---|---|
| 开启功能时补齐依赖 | R1 J1/J2，R2-J1/J2；Memory/Skill 真实维护、Heartbeat 真实 tick 补齐 | pass |
| 开启 Task | R1 waiting rev3；R2 原生 Task→Scheduled jobs + Tools 联动 | pass |
| Feature 关闭时单独打开工具 | R1 调度实际到期、Skill/Task；R2 普通/Global/PA 新卡片与 memory 合法写入 | pass |
| 关闭 Feature 后重新打开工具或 Skill | R1 v3/v6 保存重读；R2 Global v2/PA 同草稿关后重开并真实发布 | pass |
| 允许关闭时联动关联选择 | R1 J1/J2；R2 原生 Task 关后 Cron 保留、再关成功 | pass |
| 默认工具仍可选择 | R1 关闭 web_search 保存重读；实现修复未改变此路径 | pass |
| 关闭已开启 Feature 的必需工具或 Skill | R1 Web 窄屏/键盘；R2 原生 skill保护、new_context固定模式浮层与消失 | pass；VoiceOver排除 |
| Task 阻止关闭 Cron | R1 三宽度；R2 原生 Scheduled jobs 保持开启并AX提示 | pass |
| 仍有责任时关闭受阻 | R1 doing/waiting rev2/3；修复不涉及任务责任规则 | pass |
| 不存在上述责任时允许关闭 | R1 peer跨Agent隔离、paused后关闭；修复未失效 | pass |
| 定时责任阻止关闭 | R1真实600秒安排保护；未改变调度责任路径 | pass |
| 无依赖及定时责任时允许关闭 | R1删除后关闭；R2原生Task关后Cron关闭保存 | pass |
| 保存与实际使用一致 | R1保存/预览；R2三路径新卡片、原生confirmed/Web读回、维护与Heartbeat保护 | pass；API恢复辅助明示 |
| 整理已有不完整配置 | 继承R1独立核对的隔离部署副本证据，无新迁移改动 | pass |
| 后续合法选择不被迁移覆盖 | 继承R1 restart-choices.json；R2正常Node restart后合法选择继续使用 | pass |

### R2 剩余限制及边界

- VoiceOver 真机播报/读屏焦点未测，明确依用户范围调整排除；原生 AX 可读不等于实际读屏播报。
- PA 新 workspace 修复后，旧 pending UI 无可达 Retry 的恢复缺口仍存在；本轮 caller 用正常同请求 key 产品 API 恢复，随后卡片配置与调用由 reviewer 真实 UI 完成。不得对外写成 PA 创建全程无故障。
- 自动审批 `UNSUPPORTED_REASONING_EFFORT low` 仍存在。对必要隔离调用逐项 Allow once，未扩大外发目的地、修改模型或弱化审批。
- Web/原生均曾看到实时连接重连，实际持久结果通过刷新、工具轨迹和新页面核对；不把“在线”图标代替交付证据。
- R1 的截图、失败记录与配置演练原证据保留；R2 的修复证据不覆盖历史。

### R2-J4：关闭 Feature 后不恢复主动行为（最终补充）

e2e v13 已在 Web 读回六 Feature 全 false，memory、skill_manage、task_graph 为单开。真实 skill_manage list 成功；单开 task_graph 创建 `tg_70ee297a` 并追加 todo“等我下一条指令”，未 claim、未创建 schedule。memory 的合法写入能力以 R2-J1 的直接工具成功为准；此末尾回合模型请求读取记忆时发现 read 已随 Heartbeat 关闭而取消，改用已授权只读 bash，没有把这个回退冒称 memory 工具调用。

前台回合完成约 01:28:50，至 01:30:30 超过本隔离配置的一次维护检查间隔，未出现新的后台维护通知；Tasks 刷新仍为 todo、0 in progress、0 done，[最终任务画面](evidence/acceptance-r2-toolonly-todo.png)。01:27:01、01:28:57、01:29:36、01:30:30 的 MEMORY.md hash 均为 `3556f7172960cf0177b1777bfa310992ebe1928ced53dccdb46c7cc2592e77e7`，mtime 同为 `1792775275.4758704`；新增候选标识 `TOOL_ONLY_BACKGROUND_645` 未被写入；workspace skills/**/SKILL.md 仍为空。17:29:37Z usage 为 active_schedules=0、active_tasks=0、busy=[]。这是有界真实观察，不宣称长时间无人值守保证；结合本 unit 生命周期集成测试支持 M1-R4 的关闭后不自动行为。未发现 tool-only 反向开启 Feature 或自动推进此测试图。

### R2 资源收尾与交接

验收结束配置：e2e v13 六 Feature 关闭，Heartbeat 已关闭（cadence临时改60min后再关闭）；e2e-global v2 六 Feature 关闭；PA六 Feature关闭且卡片所需单开选择保留。测试图 `tg_70ee297a` 留todo、原图 `tg_ff654f80` 留paused作为证据；无 active schedule、无busy。没有因关闭 Feature 自动删图或cancel run。caller 仍负责其启动的隔离服务/Simulator及临时数据最终清理。reviewer 自建浏览器标签关闭；未操作其他任务标签。

报告只在本文件追加并保留截图，未提交、未改实现/测试/设计。`report_commit`：未提交，由 caller 统一提交与后续归并。最终 blocking=0（在用户明确调整的范围内），本 unit 新增产品问题未关闭数=0；独立旧流程/环境限制如上，未宣称生产验收完成。

收尾实测补注：新建复验标签 `1805418695`、`1805418698` 已成功关闭；早先四个 reviewer 自建标签 `1805418682`、`1805418685`、`1805418688`、`1805418691` 的 close 因 Debugger unattached 失败，交 caller 按这些确切 ID 清理。本补注纠正上段概括，未声称这四页已关闭；未关闭任何用户/他任务标签。
