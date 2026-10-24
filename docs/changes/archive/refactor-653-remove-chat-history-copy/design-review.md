# refactor-653 Design Review

## Round 1

### Metadata

- reviewer: `/root/remove_copy_design_review`（独立 reviewer，未参与设计或实现）
- reviewer target: `docs/changes/refactor-653-remove-chat-history-copy/`
- review_mode: `full`
- mode_reason: 首轮 Gate 2，完整核对 motivation、design、delta-spec、M1 骨架及真实产品组装入口。
- validated_at: `b071ffcafdc348be1b31537ce9eedc8dba907b07`
- executed_base: `c097a63219d5d303526c2ede583df39b6f81ff9d`
- started_at: `2026-10-25T00:36:35+08:00`
- completed_at: `2026-10-25T00:37:02+08:00`
- duration: `27s`（计时为最终证据核验区间；此前已完成文档与源码读取，未采集其起始时间）

### Verdict

**Approved — 0 CRITICAL / 0 WARNING**

现有设计能够在不改 DSH 原生存储、会话恢复、fork 配置快照和提炼消费者接口的情况下，停止 workspace 聊天历史副本的全部自动和显式写入。没有发现会使下游实施实质走偏的未解决问题。

### Coverage 与证据

1. **需求与边界。** motivation 明确普通聊天、重启、fork、显式导出均不创建或修改 `.nanoassistant/chat_history/`，已有文件保留、不部署；design 的关键决策和 M1 退出条件一致。保留原始快照而删除可读投影符合用户针对“第二份”的诉求，不会扩大到删除原生历史。未把旧文件清理解释为本次授权。
2. **实际组装与所有触发。** `packages/dsh-integration/src/index.ts:125` 构造 `NativeHistory`；`:285` 在 initialize 中恢复副本；`:365-375` 将真实 fork/export RPC 接入该实例；`:639` 在 shutdown 排空写入。`src/history.ts:109-115` 的 turn/end 监听、`:279` 的 fork 导出、`:438-451` 的启动恢复及 `:459-461` 的显式导出共同到达 `:292-361` 的 workspace 写入。design 删除监听、fork 自动导出、recoverExports 与正文投影，覆盖了全部这些入口；保留 stop 排空显式请求合理。
3. **Context、恢复与消费者。** 当前 capability 契约 `docs/specs/gateway/agent-capabilities.md:796-818` 将连续性归于无摘要换窗和原始历史恢复。`src/agent-context.ts:1-22` 与 `src/workspace-tools.ts:128` 通过公开 profile API 安装 `dsh-agent-context` 并提供 notes/history/new_context/get_context_remaining；应用源码没有读取 chat_history 的恢复接线。`index.ts:391-396` 的 observation 读取原生 session，`history.ts:121-177,197-278` 的配置/fork 状态也独立于可读投影。`packages/personal-assistant/src/history.ts:152-175` 的提炼消费者显式请求 session.export，并将返回路径交给 Skill 延迟读取。保留原始完整事件、版本头、持久化屏障及原子发布，覆盖该真实消费者需求。此项是源码与契约核实，未声称执行过新的恢复试验。
4. **数据流与失败边界。** design 保留显式请求队列、live session 捕获 seq 后 flush、冷 observeSession 及冷转 live 后重新 flush，与现有 `history.ts:372-434` 的持久化切面和同名临时文件串行约束对应。取消自动任务后不需要保留 raw/rebuild 标志与 WeakMap 游标；显式失败仍向调用者传播，不返回旧快照冒充成功，后续请求允许重试。没有需要新增协议、fallback 或兼容层的缺口。
5. **Delta-spec。** delta 正确锚定 `docs/specs/gateway/routing-delivery.md`：REMOVED 可读副本 requirement；MODIFIED 原生导出 requirement；MODIFIED 真人 envelope requirement 只删除可读副本正文条款及其专属 Scenario，保留其余八个 Scenario。延迟读取、分支前缀、不混入源会话后续、失败显式重试及旧文件不动均有消费者可观察结果。current specs 尚未提前改写，符合 active delta 边界。
6. **Milestone 与验收可行性。** M1-remove 只有 `.gitkeep`，未预填执行记录；单 milestone 范围没有并行冲突。现有 `tests/history.test.ts` 使用真实 RuntimeClient 子进程、临时 home、fixture provider，已有 fork、配置继承、原始导出和重启继续路径；`tests/native-human-source.test.ts:85` 和 `tests/history-export.test.ts` 暴露需替换的副本断言。M1 明确先取自动生成红测，再验证缺少副本/旧字节不变，以及原始导出的切面、并发、失败、冷观察，足以指导实施。runbook 给出了构建、测试和清理方式。本轮未运行实现测试，也未验证声明的本机 Node/pnpm 版本；这些属于实施前置检查，不影响方案可执行性判断。
7. **架构与职责判断。** DSH 继续拥有会话记录，NativeHistory 保留 Nano 配置/fork 事实和既有显式导出职责，PA 继续通过 runtime RPC 消费路径。删除无消费者的投影、游标和启动扫描比新增开关或第二种历史抽象更简单，且避免每轮和启动时不必要的文件 I/O。没有扩大 DSH 接入面、跨包私有导入或新增运行循环。保留既有原子快照实现和请求合并能力具有真实消费者与并发写入依据。
8. **用户补充的文档/副作用清理。** 主 agent 补充用户要求清理相应文档、代码及副作用，并指出 `docs/operations/pa-workspace-layout-migration.md:99` 仍要求出现新 chat history。独立读取确认该操作说明与目标行为冲突，应在实施中移除这一验收要求并声明历史适用范围；内置 `skills-tools-memory.md:40` 的“可读历史导出”表述也在既定说明清理范围。此处接受为已确定删除行为的文档一致性落实，不新增设计机制。历史变更归档及评测历史样本不应作为 current 契约整体重写。

无前端布局或交互改动，无需 prototype 或平台 UI 适配方案；本轮不以静态检查替代后续真实产品旅程验收。

### 历史问题闭环

无；本轮为首次审查。

### Issues

无。

### Recommendations

无额外建议；文档清理与副作用验收按已定 M1 范围落实。

### Author Resolutions

无实质问题。接受 Approved 结论；补充说明与operations清理属于已确认范围。设计无实质变更。
