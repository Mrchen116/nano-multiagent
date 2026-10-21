# bugfix-629 Design Review

## Round 1

### Metadata

- reviewer: 独立 `change-design-reviewer`，agent `/root/design629_review`
- reviewer target: `incident.md`、`design.md`、`specs/gateway/agent-capabilities.md`、`M1-recovery/.gitkeep`
- frozen baseline: Nano `45239680d51dbb94ed2aba1fc95c881aad1cc2b7`；相关生产实现 `be6c1271b`
- plugin baseline: `/Users/czj/Repos/opensource-hub/dsh-context-rollover` 的 `origin/main=621278df757f9c5678bf7d5429b18f0485967885`，通过 `git show origin/main:<path>` 读取，未使用该目录旧 main
- DSH baseline: `/Users/czj/Repos/opensource-hub/deepseek-harness`，HEAD `5badb15009ae1756c3afe0ae0cef1faafc290ccc`；Session/Agent package version `0.2.1-alpha.1`
- review_mode: full
- mode_reason: 首轮 Gate 2；独立核对产品组装、当前实现、公开接口生命周期、需求、delta 和 milestone，不沿用 feat-627 的 Approved
- started_at: 2026-10-21T15:50:08+08:00（正式判定与报告记录起点；前置源码取证已完成）
- completed_at: 2026-10-21T15:51:52+08:00
- duration: 1m44s（正式判定与报告记录；不含前置源码取证）

### Verdict

**Issues Found — 0 CRITICAL / 1 WARNING。**

消除高频快照变化和为当前原生 turn 提供 History 入口，能在现有 DSH 公开扩展点内实现。尚有一个会让实施偏离既有能力边界的问题：Skill 是否可发现，与 `skill` 工具是否获准调用是两项独立配置；设计把两者当作同一能力，未闭合已有显式 Skill 调用在受限工具集下的换窗恢复。

### Coverage 与证据

#### 现状与产品组装

- 核对 `packages/dsh-integration/src/workspace-tools.ts:65-85`：无 workspace 路径直接挂载插件，实际 workspace 路径通过 workspace owner/原生 bundle 生命周期挂载，方案不是只改测试中的手工组装。
- 核对 `packages/dsh-integration/src/knowledge/runtime.ts:63-74`：当前确实在发现任意历史 `compaction/end` 后读取 session 用过的 Skill，并每次 assemble 加入全文。设计改为成功压缩后、持续且可按需读取的索引，直接移除了这部分重复全文来源。
- 插件 `src/index.ts` 当前 `CONTEXT_NAME` contribution 同时包含窗口和 `referenceText`，assemble hook 追加 Notes hint；DSH `packages/core/agent-loop/src/runtime-context.ts:114-170` 对完整文本比较，变化后生成完整快照。因而设计去掉每步引用及 Notes 目录的决定与真实根因一致，不是仅降低阈值或移动重复内容。
- 原始事故报告作为既有调查输入阅读，未访问生产私密日志或复跑生产，生产数值沿用报告，不将本轮源码检查表述为新的线上验收。

#### 公开接口与恢复生命周期

- DSH `packages/core/agent-loop/src/agent.ts:267-325` 先写 `turn/start`，再执行 pre-step/claim/assemble；普通输入在同文件约 421 行进入持久日志。已读直接输入与 Inbox tool result 因此可通过对应 `turn/start.seq` 归属；尚未提交的 claimed 输入继续沿现有 decision 路径保留。
- 插件 `src/history.ts` 已以 `snapshotEvents()` 规范化用户、助手和工具记录，并用 `surface.nodes` 排除活动项；增加 turn 字段与精确过滤可以复用现有分页和 `read` 偏移，不需要 Session 私有方法。原始工具结果和 source 保留，Inbox 不被重新标记成人类授权。
- 插件 `src/rollover.ts` 已通过公开 Session append/replace 和 compaction bracket 完整配对提交，checkpoint 是持久消息；在同一事务前生成 body-free turn 导航不改变工具配对、无摘要和 no-tail 约束。正常工作多次换窗时同一 `turn/start.seq` 不变，History 过滤不受 window 边界限制。
- DSH `packages/core/agent-loop/src/index.ts:845-860` 与 `packages/core/session/src/repair.ts:53-97` 显示恢复加载可给被打断的旧 turn 补 `turn/end`。本设计重启恢复依赖已持久化 checkpoint，而不是假设重启后旧 turn 永远 open，这一选择成立。验收仍须检查恢复后的真实内容与交付，不能仅看到一个 open-turn 字段就判完成。
- `agent/turn-stopping` 在最终 `turn/end` 前触发；此时导航不能作为“必有未完成业务”的断言。设计已明确原生边界不推断业务完成，并要求先核对交付避免重复发送，符合该生命周期。

#### 需求、约束与架构判断

- 动态引用改由已有 `get_context_remaining` 和 fallback 提供，Skill 索引留在 Nano knowledge，turn 历史归属与 checkpoint 留在上下文插件；DSH 继续持有请求快照与执行生命周期，职责落点合理。
- 复用 History、原生日志和现有换窗事务，优于新建任务状态存储、摘要器或 context diff 服务；没有发现为本问题新增抽象的必要。一次换窗的有限环境重建仍存在，但设计已要求与逐步增长分别计量。
- 旧 Notes 与新已读任务组合有明确恢复优先级，不把旧 Notes 当作当前状态，不要求用户重复，不删除会话或生产资料。导航本身只证明可定位，设计把实际恢复与交付留给真模型验收，证据边界明确。
- 无客户端交互变化，前端原型和视觉审查不适用。来源、权限、显式回退与受限工具集的主张已核对；其中 Skill 调用权限存在 R1-W1。

#### Delta 与 milestone

- delta 精确修改 canonical `docs/specs/gateway/agent-capabilities.md` 中“无摘要换窗的 workspace 支持持续任务与按需恢复”；原有“多次换窗后继续任务”和“恢复原始细节或说明缺口”两条 Scenario 完整保留，新场景从消费者角度描述结果，没有将 implementation 状态误写为 current。
- 唯一 `M1-recovery` 及 `.gitkeep` 骨架与跨插件/Nano 的单主线修复范围一致，无互相冲突的并行交付面。
- Runbook 明确产品 API 入口、隔离栈、默认预算、旧已完成 Notes + 已读新 Inbox + 保存前压力换窗、七 Skill/六步请求增长检查、多窗和重启/off-on，且明确实际未触发视为未覆盖。milestone 还覆盖 overflow、长内容分页、配对、来源与隔离。可以指导实施和独立产品验收，但 Skill 矩阵需按 R1-W1 补充受限调用配置。

### 历史问题闭环

首轮，无历史 issue 或 Author Resolution。

### Issues

#### R1-W1 — 已选 Skill 不等于可调用 `skill`，仅提供路径索引会丢失现有受限配置的恢复能力

- **位置**：`design.md:41`（关键决策 2）、`design.md:66`、`design.md:83-85`；delta 的“长任务按需恢复 Skill”。
- **证据**：`packages/dsh-integration/src/capabilities.ts:25-30` 用业务 `toolAllowlist` 过滤原生工具，自动保留的仅是四个 context tools；`skill` 和 `read` 不自动获准。相同文件 `89-113` 的人类 `/skill:name` 显式调用则直接通过已选择的 Skill registry 注入正文，无须先开放 `skill` 工具。现有 `packages/dsh-integration/tests/model-policy.test.ts:7-45` 恰好使用 `toolAllowlist: ['workflow']`，通过 `/skill:retained` 载入 Skill，并对插件启用/显式停用两种模式验证压缩后保留正文及重启。
- **具体失败路径**：该已有配置在压缩前可以使用人类明确选中的 Skill；改为仅有名称/路径并要求 `skill` 重读后，工具仍被白名单排除，`read` 也不可用。启用插件时可能通过 History 找回历史正文，但设计没有给这条入口；显式停用插件的摘要模式连 History 都不可用。因此“当前仍可用 Skill”不能仅以 `skills.get` 成功判断可恢复，单纯把原测试改成含索引/开放 `skill` 的测试会掩盖回归。
- **未修后果**：用户未撤销 Skill 选择，却会在换窗或重启后失去其指导；为了让新索引可用而自动开放 `skill`/`read` 又违反保留业务白名单的要求。该问题不要求扩张任务恢复机制，但需要在实现前明确能力边界。
- **闭环要求**：明确“Skill 可用性、工具调用权限、显式人类调用、历史恢复”之间的规则，为已支持的受限配置选定不扩大业务权限的恢复路径或明确的产品契约处理。把上述 `['workflow'] + /skill:retained` 的已有组合保留为回归输入，覆盖插件启用及显式回退，不用默默增加 `skill/read` 白名单消除用例。若改变消费者可观察契约，同步调整 delta；若复用已有允许的入口，应写明索引如何指向它，并验证实际正文被按需取得。

### Recommendations

无额外可选改进；不要求新增任务分类器、状态数据库或修改 DSH。

### 本轮边界

本轮只创建此报告；未修改受审文档、实现、配置或其他 dirty/untracked 内容，未建分支、提交或启动服务。结论是设计审查结论，不是修复完成、真实任务恢复成功或生产部署证明。
