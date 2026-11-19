# feat-778 本机 Global 一级派工设计审查

## Round 1

| Metadata | 本轮记录 |
|---|---|
| reviewer | Codex 独立设计审查者 `design_review` |
| target | `313fa81c8`，对照 `origin/develop` 的 `a1fe9937d`，审查 `spec.md`、`design.md` 与 `M1-local-workers/` |
| review_mode | full |
| mode_reason | Gate 2 首轮，覆盖机器配置、执行、回传、权限、记忆、Work 与验收安排 |
| started_at | 2026-11-20T02:00:00+09:00 |
| completed_at | 2026-11-20T02:06:00+09:00 |
| duration | 6 min |

**Verdict — Issues Found，0 CRITICAL / 3 WARNING。**

### Coverage 与证据

- **需求与职责。** 原话及澄清选定机器级配置，同步作用于 PA 和普通 Global，首期只做本机。`apps/node/src/main.ts` 的真实组装经过 `NodeConfiguration`、`RuntimeSupervisor` 和 PA 的 `GlobalAgent`。配置归节点，CLI 适配与 DSH 根派工归 `dsh-integration`，IM 持有 Work 投影，可使三个框架共享业务交付，保留 Node 到 DSH 的既有 stdio 入口。锁定依赖 `@deepseek-ai/dsh-subagent` 的 `ContinuableStartSpec` 接受 `childId`，原生 DSH 路径可复用。外部会话回传另见 R1-W3。
- **Agent Context。** `packages/dsh-integration/src/agent-config.ts` 装配 GlobalMode、子角色和功能，`global-mode.ts` 区分 root 公开交付、可继续子会话的中间汇报与原生结束通知。`knowledge/document-memory.ts` 解析所属业务 Agent 的记忆目录，`memory-sources.ts` 的冻结目标确含 children。设计覆盖新交办、同会话更正、历史待整合摘要和 `source_history`。主会话实际收到的工作成果可作为主经历，普通文件权限维持现状，这与用户原话一致。M1 比对真实模型请求与 Dreaming 入选材料的办法能判断注入与取材行为。返给 Router 的身份与来源见 R1-W3。
- **Web Work。** `packages/personal-assistant/src/global-agent.ts` 的 `projectRootPage` 与 `projectChildRows` 分别处理根分页与子目录。`src/IM/frontend/src/features/settings/agents/agent-work-delegation.tsx` 当前整张节点按钮调用 `openSession` 并展示会话轮次、token；`agent-work-panel.tsx` 另有原生轨迹入口。设计将新关系作为只读节点，按标题、框架和状态辨认事项，保留旧 DSH 节点导航。沿用同一张派工图，这项交互取舍已有充分说明。界面判断仅及设计，实际双事项、更正、旧子入口与根轨迹由 M1 Web 走查；本轮未验视觉呈现。
- **交付与验证。** 单一 M1 对同一条 IM 链路实施并验收，无并行文件所有权冲突。隔离服务、真实 CLI、可控协议对端分别用于产品旅程、账号与模型成功回包、确定性失败分支。核对本机可执行版本为 Codex 0.169.1、Claude Code 2.1.325。首文档仅有 Codex 成功探针，Claude 的账号验证错误仍需在实施验收时如实记录。未发现需上线执行的一次性数据迁移。

### Issues

**R1-W1 · `design.md` 第 26–29 行只有目标文件清单，缺少可归并的契约增量。** Unit 未含 `specs/`。这已影响实际实现选择。`docs/specs/im/agent-work.md` 的「Web Work 可以从派工关系进入同一工作记录」保证每个节点可点且携带会话统计，新关系节点恰好改变这两项。`gateway/agent-capabilities.md` 的「角色化文档记忆」「Dreaming 按交流与任务经历组织记忆」要求子会话消费与提炼，且「固定基础工具与可配置工具区分」把 `subagent` 固定给 root；`packages/product-contracts/src/capabilities.ts` 的 `fixedTools()` 落实这一点。`gateway/tool-approval.md` 还对普通子执行统一规定 DSH 审批。按 `docs/specs/CONTRIBUTING.md` 为实际变化的 area 写出 ADDED/MODIFIED/REMOVED，保留旧条目仍适用的场景。特别区分外部 CLI 明确续做与原生 DSH 掉线后的自动续做，后者已有 `gateway/global-agent.md` 的「主及各级子会话在进程恢复后自动继续」及 `interrupted-work.ts` 的实现。这样采用同名替换派工工具或换名更新固定工具均可基于用户可见保证判断，也能查出旧配置同时暴露原生派工入口的回归。

**R1-W2 · `design.md` 第 14–16、33 行未说明怎样结清正在等待的原生权限请求。** 第 16 行规定将决定转给父级、把新信息交给原 worker，但普通追加文本与正在等待的协议请求有不同效果。Codex 的 server request 需要按 request ID 响应，原请求也可能在中断时失效。Claude 的运行时同样区分最终拒绝、需宿主判定的工具调用及模型提问。若实现只转发用户消息，worker 可以一直等待；若把普通更正当作同意，又会放大原授权。请选定最小闭环，例如先向原请求返回不放行，父级取得新材料后让同一会话重新判定；若选择保留请求，则限定只能响应仍有效的同一个请求。用可控对端分别验证正常补充、有效新决定、不可推翻的最终拒绝及停止后的迟答，并区分停止请求受理与终态。协议依据见 [Codex App Server](https://developers.openai.com/codex/app-server/) 和 [Claude 的许可与提问协议说明](https://code.claude.com/docs/en/agent-sdk/user-input)。

**R1-W3 · `design.md` 第 17–18、23 行未确定外部 worker 的中间消息和最终答复如何投给真实父级。** `global-mode.ts` 将原生内部通信转交 `nativeSend`，锁定依赖 `@deepseek-ai/dsh-subagent` 的 `sendMessage(sender, targetId, ...)` 要求真实在线的 DSH sender 向相邻会话发送；外部 CLI 无此 Activation。宿主另有可复用的 `packages/dsh-integration/src/index.ts` `submit`，它支持持久输入标识及繁忙/空闲 root 的消息接收，但须明确绑定与来源。请确定外部 MCP 及原生回合结束共用哪个**宿主回传**入口，如何从绑定得出 root/worker、如何让 Router 识别要回复哪个 worker，以及恢复/重复递送时如何只产生一次同一结果。可用两个外部事项中一个提问、另一个完成，再重放同一完成事件来核对父级实际收到的来源和次数。原生 DSH 可沿用现有相邻通信与收尾行为。

### 历史问题与建议

首轮无历史问题；无额外建议。

### Author Resolutions

- R1-W1 accepted。unit/specs 增列派工、能力、审批与 Work 条款。
- R1-W2 accepted。设计决定 4 完成原请求拒绝、原会话重判和迟答边界。
- R1-W3 accepted。决定 5 指明宿主绑定身份、root 唤醒、回传去重与原生 DSH 的区别。

## Round 2

| Metadata | 本轮记录 |
|---|---|
| reviewer | Codex 独立设计审查者 `design_review` |
| target | `4cb0a165c`，对照 R1 的 `313fa81c8` |
| review_mode | delta |
| mode_reason | 首次提交四份 delta，需对照 canonical 检查归并后果；设计决定 4、5 的修订仅影响原权限和回传问题 |
| started_at | 2026-11-20T02:07:23+09:00 |
| completed_at | 2026-11-20T02:07:45+09:00 |
| duration | 22 s |

**Verdict — Issues Found，0 CRITICAL / 1 WARNING。**

### Coverage 与历史问题闭环

- **R1-W2 — closed。** Author Resolution 选定即时结清原请求。决定 4 明确按原 request ID 回送拒绝或取消，授权答复通过同一会话的新输入重新判定，已终局拒绝与停止后的迟答均有确定结果。可控协议对端可以按此区分原请求是否结束与后续输入是否被接收。
- **R1-W3 — closed。** Author Resolution 选定宿主 report 路径。决定 5 将外部消息绑定到持久 worker/root 身份，模型收到 worker 标识、标题与消息性质，使用回合或调用标识形成持久输入键，复用 root 的 steer/空闲唤醒。该路径可覆盖不同事项同时回传和同一终态重放，也避免把内部汇报误作用户授权。
- **R1-W1 — still-open，见 R2-W1。** Author Resolution 已把新派工、记忆、审批与 Work 的目标行为放入镜像文件；四份文件中的正文均已核对。现有主从职责、Scope、页面阅读路径、隔离验收与 milestone 未发生实质变更，`retained_from: Round 1`。本轮为设计审查。

### Issues

**R2-W1 · 四份 delta 还不能按现有规则归并（延续 R1-W1）。** `docs/specs/CONTRIBUTING.md` 要求 MODIFIED 按同名 Requirement 替换完整条目并保留仍适用的 Scenario。当前 `specs/gateway/tool-approval.md:1` 以原来的 **Scenario**「子 Agent 统一采用委派权限」作为替换标题；`specs/gateway/agent-capabilities.md:5` 则用一个新标题合并多个现存 Requirement。即使人工匹配，也无法从段落判断应如何处理现行「旧子会话续做」中“必须生成新摘要”与新设计的冲突。反过来，直接用 `specs/im/agent-work.md:3` 替换现行 Work 条目会丢失仍适用的“返回图保留范围与来源节点”及定时投递入口保证。Global delta 同样遗漏 R1 指出的外部 worker 中断后明确续做与既有 DSH 自动恢复的适用范围。请对变动的既有 Requirement 使用原名和完整 Scenario，另列真正新增或退役的条目；可复用 canonical 原文，仅修订受影响场景。复审核对目标为同一输入在归并后有唯一预期、旧场景保持可判定。

### Recommendations

无。

### Author Resolutions

- R2-W1 accepted。四份 delta 现按 canonical 同名完整 Requirement 归并，保留 Work 返回、定时投递等旧场景；分别限定外部与原生恢复、旧工作子摘要资格、根工具与子角色适用范围。
