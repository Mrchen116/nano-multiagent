# Design Review

## Round 1

### Metadata

- reviewer: 独立 reviewer `/root/design_review`（非设计作者）
- target: `refactor-672-im-contract-boundaries` 的 motivation、design、M1/M2 空骨架，以及相关生产装配与 current 契约。
- review_mode: `full`
- mode_reason: 首轮 Gate 2；独立覆盖需求、现状、职责、共享接口、兼容性和验证计划。
- started_at: `2026-10-28T10:48:30+08:00`
- completed_at: `2026-10-28T10:50:39+08:00`
- duration: `2m09s`
- validated_at: `9d7531feb0097d3fb60511cad10ce33c40dbc4a9`
- executed_base: `a34af8473`
- checkout: `codex/im-contract-boundaries`；审查开始时 clean；本轮仅新增本报告。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。**

完整配置纵切加全部中心主动 RPC 的有限命令关联，足以落实架构报告第 3 项的真实模块契约目标。方案没有承诺全仓 Row 清零，也没有把声明替换当成完成；不需要为了扩大表面覆盖而重写聊天、Work、Channel 等无关业务。当前决定与退出标准可以指导实施，未发现会使下游实质走偏的未解决设计问题。

这是实施前设计判断；未运行测试、未验证实现或模型行为，也不代表后续 verifier/code review/适用产品验收已通过。

### Coverage 与证据

#### 需求范围与现状

- 核对原报告 `docs/research/architecture-reviews/architecture-review-20261028-102827-a89b778.html:71-78`：明确建议从 Task 或配置真实 seam 开始，具名输入输出和内部存储类型，再缩小 context，并反对全仓类型重写。motivation 的配置链范围与此一致；额外收口所有主动 RPC 能覆盖原报告指出的 `request(type: string, payload: Row)` 关联缺失。
- 实际污染入口在 `apps/im-server/src/context.ts:8-19,28-30,42-46`。配置链从 `control.ts:711` 创建、`:892` PATCH、`:855` 读取进入 `ConfigOperations`，不是仅存在于测试中的抽象。`server.ts:88-91` 装配 Gateway/PersonalAgents，`control.ts:618` 与 `personal-agent.ts:314` 分别创建配置服务。
- `control.ts:167-475` 确实包含按 Agent 串行、二次授权、候选与指纹、持久 operation、状态恢复、补偿、profile/PA 身份事务与提交后 lifecycle 投递。把这些整体迁移到服务而不是只移动路由或增加 DTO，能够解除当前完整 ImContext 依赖。
- 已检查 `M1-node-rpc/.gitkeep`、`M2-config-service/.gitkeep`；骨架与 design milestone 表一致，没有预填虚构 tasks/progress。

#### 职责与接口可落实性

- 配置服务保留 SQLite 权威与同步事务是合适的：现有流程需跨 profile、operation、users、PA binding 和 conversation 一起提交，通用 Repository 层不会带来本需求所需收益。`db + request + deliverLifecycle` 足以覆盖现有依赖；`control.ts:473` 的 `new AgentLifecycles(ctx).deliver(...)` 可在装配 adapter 内实现，业务不必持有 Gateway/Identity/Messaging 对象。
- Gateway 当前 `request` 在 `gateway.ts:126-171` 拥有 ID、response 名、连接捕获、定时器与离线拒绝；回包在 `:416-450` 先核对当前连接和持久身份，再完成 pending。design 保持这个安全顺序，NodeRpc 仅拥有相关请求生命周期，不接管注册、Task 写入屏障或数据库授权，职责划分成立。
- 命令表按中心实际调用者和 `apps/node/src/main.ts:187-283` 的消费/回包建立；四个特殊响应名、`.request` 和 `session.fork.request` 特例均有现存实现。已检查 control、personal-agent、onboarding、work、conversation-actions 和 Gateway 自身的调用点；设计的“所有中心主动 RPC”包括这些适配点，不仅是配置三条命令。
- 稳定 input/output、SQL 行、业务 Candidate 和公开 ProfileView 分开建模；动态插件/provider/工具内容在字段内保留扩展，而不是在稳定对象上保留任意索引。禁止 string fallback、禁止 unknown 后直接断言冒充校验，并要求实际调用者消费类型，能够提供真实编译保护。
- 依赖方向符合 `SPEC.md:29-48`：共享产品配置契约进入 product-contracts，中心专用命令表留 IM，不引入 IM→Node/PA/DSH。未新增框架、第二执行循环或存储迁移。

#### 行为、恢复与兼容性

- 对照 `docs/specs/im/agents-nodes.md:60-126`，设计明确保留 version、完整候选 apply、确认丢失时原 operation 恢复、未知结果 pending、补偿、live 合并和旧节点缺省；`no spec delta` 合理。auth-tenancy/gateway-relay 所要求的 owner/空间/设备身份边界没有被替换为仅在入口做一次校验。
- 关键实现依据：`control.ts:267-312` 的 operation/fingerprint/agent 结果检查和安全拒绝码，`:335-401` 的版本冲突补偿，`:425-475` 的 restore 与 PA 名称事务，`:505-525` 的输入校验，`:892-925` 的省略/null 处理。design 将这些作为保留行为，而没有借类型收紧更改文本整理或额外字段策略。
- 回执保存原 payload、包括额外 wire 元数据的决定与现有 `JSON.stringify(result)` 持久化一致，避免只返回 decoder 白名单后改变已有字节。非法/不完整配置回执必须仍落入 pending，而不是冒充 applied；这是实施必须满足的已有退出约束。
- 序列化第 4 项由另一任务处理。按 design 的约束解释，当前工作保持 asciiJson/candidateFingerprint 算法、名称与语义，不重新设计或统一序列化；抽取业务边界不授权迁移算法归属。实现仍须防止新服务反向依赖路由模块。
- 没有 UI、数据库 schema 或协议版本切换；不需要 prototype 或 deployment-prompt。代码回退保持 operation 数据可读，不重置待确认操作，回退方案合理。

#### 验证与 milestone

- M1 先固定命令关联和连接生命周期、M2 再迁移配置事务的顺序合理；退出标准覆盖真实类型消费和传输/持久风险，没有依赖未定义的并行接口。
- 可复用证据面已存在：`tests/e2e/control-work.test.ts:5-70` 以真实进程 HTTP/WS 完成配置操作，并验证相同 request_id 的无关响应不能完成 apply；`tests/agent-settings.test.ts:19,104,149,192` 覆盖旧能力缺省、离线新写、待确认恢复和读取 freshness；`tests/approval-configuration.test.ts:11,37` 覆盖省略/null 策略与跨端指纹；`tests/personal-agent.test.ts:60,96` 覆盖 PA 创建与延迟配置恢复。这些是已核对的测试资产，不是本轮执行结果。
- `tests/e2e/helpers.ts` 使用随机端口、临时 SQLite、真实 IM 子进程和认证设备 WS，能够承接 runbook 的隔离边界验收。测试节点回包可验证关联和 operation 流程；它不能证明真实模型推理或真实 Node 所有能力运行。设计已明确此证据限制，未把 stub 称为真实模型验收。

#### Agent Context Design Review

- 模式：Mode A，限定配置选择与投递链；依据 `agent-context-review` 和 `docs/development/agent-context-engineering.md`。
- 相关 Surface 是 custom_prompt、features、skills/tool_allowlist、model/reasoning 配置从 owner HTTP 输入，经候选规范化与 operation、Node configuration 到后续执行的交付。`control.ts:52-107` 的字段选择/指纹与 `apps/node/src/main.ts:278-283` 的真实 handler 是边界 grounding。
- 方案的 Before/After 均为相同有效字段、身份派生、候选指纹、恢复记录和配置生效时机；没有新增 Prompt、来源选择、工具描述或上下文生命周期决定。保持省略/null、顺序和 wire 内容的要求，加配置字段保真与兼容验证，足以验证本次设计所承诺的无语义变化。
- 未读取最终 provider 请求或运行模型；此轮没有实现可供证明模型实际交付。若实施引入字段裁剪、默认规则或加载时机变化，应按真实 delta 扩大审查，不能继续沿用“类型重构”豁免。没有 Context finding。

### 历史问题闭环

首轮，无历史 issue 或 Author Resolution。

### Issues

无。

### Recommendations

- **R1-R1（可选）**：实施时把实际命令清单与成功/业务错误/缺省回包纳入 M1 的验证记录，尤其是 `node.setup.request`、动态 settings section、能力预览和 `task.wait.validate`。这些已在“所有主动 RPC”的范围内；记录清单有助于最终 verifier 防止遗漏，不要求另建大 schema 框架。
- **R1-R2（可选）**：优先补一项真实 WS 的不完整配置回执用例，断言仍返回 `503 config_apply_pending` 并保留 operation；再以原 operation 正确回包恢复。它直接保护新 decoder 与既有恢复协议的交界，也能防止把 decoder 异常意外变成通用 500。设计已明确该行为，本建议只细化最高价值的验证落点。

### Author Resolutions

- 作者核对 R1 结论及实际调用点，接受 Approved，无实质异议。
- REC-1/REC-2：采纳命令/响应覆盖清单和 malformed receipt→pending→同 operation 恢复保护，记录在实施验证中；不改变已审设计语义。
- 设计语义无变化。实现采用现有 control 模块持有配置业务与原序列化函数，HTTP 路由移到独立 adapter，避免迁移并行任务负责的算法或让服务反向依赖路由。
