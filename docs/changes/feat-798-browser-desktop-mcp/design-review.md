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
