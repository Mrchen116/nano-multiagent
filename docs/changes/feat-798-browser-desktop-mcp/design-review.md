# feat-798 设计审查

## Round 1

- Reviewer 为独立 Gate 2 reviewer `/root/design_review`。目标为 `unit/feat-798-browser-desktop-mcp` 上的 `spec.md`、当前未提交的 `design.md`、两份 Gateway delta 和 `M1-host-tools/`。
- `review_mode: full`。本轮为首次设计审查，涵盖 Agent Context 设计模式。
- `started_at: 2026-11-27T01:05:38+09:00`，`completed_at: 2026-11-27T01:07:39+09:00`，`duration: 2m01s`。
- **Issues Found**，0 CRITICAL，3 WARNING。无历史问题。

### Coverage 与证据

- 对照 Node 的 `apps/node/src/lifecycle.ts`、安装脚本和随包 CuaDriver 0.38.0 手册，应用身份、后台定向输入、无提示权限状态各有可用入口。Node 管本机配对，integration 在产品工具与后端间负责目标、执行和回收，职责与现有 DSH 接入边界吻合。窗口身份应由宿主绑定后重新核对，旧 Bash 路径保持原审批。无需前端原型或一次性迁移。
- `ConfigurationScopes.attachPreset` 负责注册，`ToolSelection.selection/refresh` 影响每个 Agent 的可调用集合，`NanoApproval.review` 挂在原生 pre-execute。一个简短入口加按需 describe/status 可行，需在实现时覆盖未保存工具名单的默认配置。未配对样例能告诉模型下一步，历史 ref 失效后可再次观察。M1 应按 spec 对照同任务真实出站首轮、读到工具结果后的下一轮及恢复请求，并观察模型行动。这里仅判断设计，未运行模型或读取真实剪贴板。
- `LocalWorkers.start`、report bridge、三个 drivers 提供可复用的生命周期和通信。邻近 feat-797 checkout 的 `worker-permissions.ts:86` 中 `hostedWorkerMcp(parent)` 当前固定注册 `nano-parent/send_message`，三个 drivers 从这里取配置和精确工具名。扩展此处并保持宿主一次判定可行，普通 native CLI 操作沿用 797；执行前仍需解决下述授权绑定。
- 两份 ADDED delta 锚定现有 Gateway 能力和审批条目，语义允许不同后端实现；无 MODIFIED 场景待保留。M1 安排涵盖两浏览器身份、原生窗口、三种 CLI、取消拒绝及资源回收。浏览器内存剪贴板、系统剪贴板首次异步前占用、读取结果不进审核日志的设计与用户澄清一致。实现证据应使用合成内容和可丢弃目标。

### Issues

**R1-W1 · 普通直接输入没有稳定的原话字段。** `design.md`「剪贴板与原始用户输入」把直接交办的唯一来源写为 `directHumanText`，并称 PA 仅分发说明。实际 `packages/personal-assistant/src/single-thread.ts:315` 仅在批次或 thread root 时填写此字段。普通单条人类消息可以完全缺失；同文件 `messageContent` 还可能拼接引用、群成员和卡片背景。按设计会漏掉有效请求，直接回退到渲染全文又可能把他人在引用中的话认成当前指令。请明确由已认证入站边界提供当前发送者原文并核实其对本节点的授权，补上必要的 PA 接线范围。M1 覆盖普通直达交办和只有引用里含该指令两种消息，保留已定下的零弹窗、零审核模型。

**R1-W2 · 宿主如何把一条交办授权给指定 Worker 尚未定义。** `design.md` 把工具挂载和剪贴板共享消费位都建立在“授权委派”上。`packages/dsh-integration/src/global-mode.ts:22` 的真实派工参数只有 action、label、message 和 worker_id，`local-workers/manager.ts:249` 接收自由文本与执行上下文。现有桥可确认是哪个 Worker，却没有指明在同一个 root 处理多条交办时，应把哪个已认证来源绑定给此次 activation，也没有界定何种派工获得窗口/浏览器工具。仅按 root 开关会让同 root 下另一项工作也获得能力；解析转述与设计自己的来源规则冲突。请确定产品派工入口和宿主绑定条件，标明普通派工在关闭时的首轮影响。用同一 root 并发两项交办验收，只有承接对应操作的 Worker 能取得该 seat 和一次消费位，主会话与它竞争时最多成功一次。

**R1-W3 · 后台连接还受 Chrome 版本限制。** `design.md`「任务与连接」要求探测扩展能力并检查浏览器已在运行，但微软文档说明 token 模式的连接页在后台打开还需要 Chrome 158.0.8127.2 或更新版本，扩展本身支持后台只要求 0.5.0。在扩展符合要求、Chrome 已启动但版本较旧时，第一次连接已可能抢走焦点，连接后再观察已来不及。请明确连接前对浏览器与扩展组合的处理，或选择有证据可满足同一前台体验的接入方式，并在状态与验收中覆盖不满足条件的组合。[微软扩展的后台模式说明](https://github.com/microsoft/playwright/blob/main/packages/extension/README.md#working-in-the-background)

### Recommendations

无。

### Round 1 resolutions

- W1：PA 在渲染引用、背景前提供每条认证用户消息的直接原文；旧记录缺失时不凭拼接正文授予权限。
- W2：仅启用工具时扩展 delegate_worker.start，显式选择真实交办引用，由宿主验证并绑定单一 activation，root 与获委派者共用一次消费位。普通委派没有该能力。
- W3：后台连接前核实 Chrome、扩展版本和运行状态，避免旧浏览器的连接页抢焦点。

## Round 2

- Reviewer 为独立复审者 `/root/gate2_closure`，目标为 `4dad7cf14` 的 `design.md` 及两份 Gateway delta。
- `review_mode: closure`。三项修订限于直接消息取证、委派绑定与后台连接前置条件。其他设计判断沿用 Round 1。本轮包含 Agent Context 设计审查。
- `started_at: 2026-11-27T01:08:45+09:00`，`completed_at: 2026-11-27T01:09:19+09:00`，`duration: 34s`。
- **Issues Found**，0 CRITICAL，1 WARNING。

### 历史问题闭环

- **R1-W1 · still-open（R2-W1）**。作者将 PA 原文来源固定为组装引用前的 `input.message.content`，并规定旧记录缺少 `directHumanText` 时无读取资格。对照 `single-thread.ts:311–315,334–338`，这已解决普通直聊缺原文、引用或卡片混入的问题。对直接消息的发送者是否有权操作本节点仍欠明确规则，见下。
- **R1-W2 · closed**。作者在启用能力时才向根会话的 `delegate_worker.start` 增加 `computer_request_ref`。与 `global-mode.ts:21–30` 和 `local-workers/manager.ts:249` 对照，宿主可以在启动时解析本轮取得的真实消息，检查归属及操作范围后绑定特定 activation；普通派工无需参数且无此工具。根会话与承接同一消息的 Worker 共享消费位。M1 已安排双交办并发、关闭能力时的出站 schema 及模型实际选参检查。
- **R1-W3 · closed**。作者要求连接前确认浏览器进程已运行、Chrome 至少为 158.0.8127.2、所选 Profile 的扩展至少为 0.5.0，并为前置条件不足返回启动或升级指引。微软说明分别把两项版本约束用于 token 连接页和后台任务页，且要求浏览器已运行。M1 已包含旧浏览器连接前停止与双任务后台操作。此次核实的是设计条件，实际前台焦点由 M1 验证。[微软扩展后台模式](https://github.com/microsoft/playwright/blob/main/packages/extension/README.md#working-in-the-background)

### Issues

**R2-W1 · 对直接人类输入，系统剪贴板的一次性资格仍缺少节点授权判据。** `design.md:29` 对 Global Inbox 明确要求主人交办，对 single-thread 直接路径则规定取已认证发送者原文、明确肯定请求即产生资格。宿主能确认一条消息来自真人，同时也允许非主人的定向协作消息进入会话。现有 `attention.ts:13–24` 明确区分 `ownerDirect` 与 `directToAgent`，`input-source.ts:25–27` 的真人来源检查也未比较节点主人。若协作者请求整理自己刚复制的内容，按现有文字实现的根会话可能直接读出主人机器上的剪贴板。请把直接路径签发资格限定到持有本节点授权的真实发送者、其本人发出且确实交办给当前 Agent 的消息，说明沿用的可信身份映射。M1 以主人和已认证协作者发送相同文本对照，一者可用一次，另一者直到返回均没有触碰系统剪贴板。此处为已确认的设计遗漏，尚无运行时读取结论。

### Recommendations

无。

### Round 2 resolution

直接系统输入要求真实 actorId 匹配节点主人，Global Inbox 须有宿主认定的 owner + participant，代理与协作者不能授予资格。M1 对相同主人/协作者原话做成对验证。

## Round 3

- Reviewer 为独立复审者 `/root/gate2_owner`，审查版本为 `cfc248a95`。
- `review_mode: closure`。本轮复核 R2-W1 修订的主人来源判据及 M1 验证安排。其余判断沿用 Round 2。
- `started_at: 2026-11-27T01:10:44+09:00`，`completed_at: 2026-11-27T01:11:22+09:00`，`duration: 38s`。
- **Issues Found**，0 CRITICAL，1 WARNING。

### 历史问题闭环

- **R2-W1 · 直接路径已关闭，Global 来源接线仍需修订。** 作者将直接路径限定为本人发出的原话、真实 `actorId` 与节点绑定的 `ownerId` 相等，并排除观察、代理代发和仅渠道账号相同的消息。`single-thread.ts:311–315` 的直接发送者、独立的渠道关联账号和代发标记支持该判断。`design.md:29,35` 及 Round 2 resolution 共同给出了 M1 对照：同一句交办，主人可读一次，协作者从请求到返回的系统读取次数为零。

### Issues

**R3-W1 · 普通 Global Inbox 缺少修订中指定的两个来源字段。** `design.md:29` 要求 Global Inbox 同时使用 `sender.is_owner` 与 `participant`。实际 `packages/personal-assistant/src/inbox.ts:773,823–836` 只在具有 `personal_delivery` 的 PA 输入上投影这两项。普通 Global 页有真实消息 ID、发送者 ID、类型与 target，即使主人直接交办也没有这两个字段。按该判据，合法的 Global 主会话和它授权的 Worker 都取不到一次读取资格。请将 PA 与普通 Global 的宿主判断分别落到实际来源，例如 Global 以本轮完整读取的消息核对真实发送者、节点主人、会话目标及对当前 Agent 的交办。M1 的主人/协作者同文对照应覆盖普通 Global 的真实 Inbox 入口。

### Recommendations

无。

### Round 3 resolution

普通 Global 从 Inbox 真实读到的 RelayInput 判断实际主人与目标；PA 额外核实 participant。M1 分别验证真实 Global 入口和 PA。
