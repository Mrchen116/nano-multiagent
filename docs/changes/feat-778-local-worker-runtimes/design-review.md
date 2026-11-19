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
