# feat-502 — 验收报告

> 对齐: `spec.md` 的验收标准

> Validation snapshot: `e6f8b617a7beb1dc68e1a116f368eaf05c764606 → ea59765053a8bc8fb253f5b3f1ae3dc6d73cda0b`

> Review round: 2；Revalidation: post-review progressive-reference delta

> Round 1 的 IM/UI/资源刷新证据继续覆盖未变化场景；PR review 将产品手册从单文件改为入口 + references 后，所有涉及正文可达性的结论以下述 Round 2 真实模型轨迹为准，Round 1 的“无 `read`”轨迹仅保留为历史证据。

## Verdict

- Verdict: **pass**
- Highest Required Action: **pass**
- Issues: blocking 0 / major 0 / minor 0
- 17 个 Scenario 全部通过；无 fail、inconclusive 或 not-applicable。

## 验收口径与环境

- 使用 worktree 隔离的 `HOME`、运行数据、IM/Gateway 端口与 node identity，启动真实 IM、Gateway 和 Web IM；登录使用 E2E 固定隔离 Test User。
- 使用真实模型 `deepseek:deepseek-v4-flash`，从 Web IM 完成 Agent 新建、skill 关闭/恢复、产品问答、普通任务、边界问答、现场状态和最新版问答。
- Round 2 用真实 PA Kernel、真实模型和仅含 `nanoassistant-docs` 的 skill 选择，工具只开放默认的 `skill_view` + `read`，不开放网络工具；轨迹确认先读入口、再只读命中主题的 reference 并正确作答。
- 在隔离全局 skill root 中预置旧版/本地改写的 `lark-doc`、已退役额外文件和非内置 `my-custom-skill`，通过两次正确版本 Gateway 启动观察刷新、选择保持和非内置资源保护。

## 用户旅程体验

1. **首次启动与默认启用**：Gateway 启动后，旧 `lark-doc` 的本地改写和额外文件被当前包版本完整替换，`my-custom-skill` 内容保持不变，`nanoassistant-docs` 出现在全局列表。打开 Web IM 的新建 Agent 页面，产品手册、`skill_view` 与 `read` 均为默认选中。通过 UI 原样保存新 Agent `Docs UI Default` 后询问“Web IM 和 Gateway 各自负责什么”，模型调用产品手册并给出正确职责边界。
2. **渐进读取闭环**：Round 2 为真实 PA Kernel 只选择产品手册，只开放 `skill_view` 与 `read`。询问首次启动顺序以及终端出现 `Gateway started` 是否代表已经可聊天时，工具轨迹严格为 `skill_view(nanoassistant-docs)` → `read(.../references/getting-started.md)`，没有读取其他专题；回答正确说明“先 IM、后 Gateway、再绑定/聊天”，并明确 started 不等于聊天链路就绪。
3. **按需触发与范围边界**：同一 Agent 计算 `37 × 19` 时直接回答 `703`，没有工具轨迹；询问 Coding CLI、Agent Kernel 内部调度和仓库开发流程时，回答明确说明超出 PA 产品手册边界，没有把内部开发知识冒充为 PA 产品说明。
4. **用户可关闭且可恢复**：在 Web IM 详情页取消产品手册并保存后，再问 heartbeat 与 cron，轨迹没有调用 `nanoassistant-docs`；重新选中并保存后询问节点离线排障，模型恢复调用产品手册并给出正确排查顺序。
5. **升级不扩宽显式选择**：再次关闭 `Docs Review 2` 的产品手册并保存，随后把 `lark-doc` 改回旧内容、加入额外文件并重启正确 worktree Gateway。资源再次被完整刷新，Agent 页面仍显示产品手册未选中；刷新没有改写显式 profile。
6. **版本与网络边界**：Round 2 的基础问答只有产品手册、`skill_view` 与 `read`，没有网络工具，仍从随包 reference 完成。Round 1 的 `Docs Live` 在会话授权官方仓库访问后完成最新版对比，明确区分远端 `main` 与本机 unit worktree，没有把远端行为说成本机已具备行为；该次真实远端查询约耗时 3 分 45 秒，但最终完成且结果边界正确。
7. **规则与现场证据分开**：入口继续要求把产品规则与现场观察分开；Round 2 工具轨迹确认 `skill_view` 与 `read` 的真实使用。Round 1 追问不存在的 `QuantumSync` 模式时，回答明确说明手册和现场均无证据，不编造配置项或命令。

关键验收证据：

- 新建页默认选择截图：`.playwright-cli/page-2026-08-05T07-02-23-490Z.png`
- 最小工具 Agent 产品问答截图：`.playwright-cli/page-2026-08-05T07-06-15-287Z.png`
- 最小工具 Agent 过程快照：`.playwright-cli/page-2026-08-05T07-06-12-958Z.yml`
- UI 默认 Agent 产品问答截图：`.playwright-cli/page-2026-08-05T07-24-40-611Z.png`
- UI 默认 Agent 过程快照：`.playwright-cli/page-2026-08-05T07-24-37-811Z.yml`
- Web IM 对话：`Docs Review 2`、`Docs Offline`、`Docs Live`、`Docs UI Default`。
- Round 2 前向验证：真实 Kernel/模型终端轨迹摘要见 `M1-product-docs-skill/progress.md` 的 `PR review revision`，包含精确的 `skill_view` → `read(getting-started.md)` 调用序列和最终回答。

## Reference Artifacts Reviewed

N/A。spec/design 未引用原型、设计稿、reference screenshot 或视觉一致性契约；`nanoassistant-docs/references/` 是运行时产品资料，不是本节所指的外部设计参考物。

## 问题清单

无。

## Side Findings

- 明确查询远端最新版的真实模型旅程耗时约 3 分 45 秒；需求未规定该路径的性能目标，且结果最终正确完成，因此记录为观察项，不作为本 unit 问题。

## 验收标准覆盖

### Requirement: 产品说明书作为可关闭的默认 PA skill — 组内结论: pass

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 新建 Agent 默认启用产品说明书 | `spec.md` | Web IM 打开新建页，不改变默认 skill；创建 `Docs UI Default` | 新建页截图 `07-02-23-490Z.png`；详情页与真实对话 | pass | 产品手册可见且默认选中 |
| 使用默认 skill 集合的 Agent 获得产品说明书 | `spec.md` | 通过 UI 原样保存默认 Agent，询问 Web IM/Gateway 职责 | `Docs UI Default` 对话；截图 `07-24-40-611Z.png`；过程快照 `07-24-37-811Z.yml` | pass | 成功调用 `skill_view(nanoassistant-docs)` |
| 升级不改写已有显式选择 | `spec.md` | 为既有 Agent 保存不含手册的显式选择，刷新内置资源并重启 Gateway | 重启后 `Docs Review 2` 详情仍为 profile v4，产品手册未选中 | pass | 资源刷新与 profile 选择相互独立 |
| 用户关闭后不再使用产品说明书 | `spec.md` | Web IM 取消保存后提问，再重新选中保存并提问 | 关闭后的 heartbeat/cron 轨迹无产品手册调用；恢复后的离线排障轨迹成功调用 | pass | 关闭和恢复均在真实会话生效 |

### Requirement: 随包内置 skills 与当前 PA 版本一致 — 组内结论: pass

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 升级后刷新全部内置 skills | `spec.md` | 隔离 root 预置旧 `lark-doc`、本地改写和已退役文件，启动 Gateway | 两轮正确 worktree Gateway 启动后，包内容恢复且额外旧文件消失；产品手册存在 | pass | 覆盖现有 Lark 与新增产品手册 |
| 本地修改的内置 skill 被产品版本替换 | `spec.md` | 启动前修改保留名称目录，启动后再次检查 | 两轮启动均移除本地标记并恢复当前包内容 | pass | 完整目录替换可重复成立 |
| 用户自建的其他 skills 保持不变 | `spec.md` | 在同一 root 预置不同名称 `my-custom-skill`，刷新前后比对 | `SKILL.md` 的 `user-owned skill` 内容保持不变 | pass | 非内置名称未被触及 |
| 刷新不改变 Agent 的 skill 选择 | `spec.md` | 保存关闭部分内置 skill 的显式 profile 后重启 Gateway | `Docs Review 2` 重启后仍保持产品手册未选中 | pass | profile v4 保持 |

### Requirement: Agent 按需用说明书回答 PA 产品问题 — 组内结论: pass

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 从任一 PA 对话入口询问产品能力 | `spec.md` | Round 1 从 Web IM 验证入口触发；Round 2 用真实 PA Kernel 验证渐进读取 | Web IM 对话；Round 2 `skill_view` → `read(getting-started.md)` 轨迹 | pass | 入口触发和最终 references 链均由真实模型覆盖 |
| 普通任务不触发产品说明书 | `spec.md` | 对已启用手册的 Agent 提交算术任务 | 回答 `703`，无 Process/tool 记录 | pass | 启用不等于每轮强制加载 |
| 问题超出 PA 说明书边界 | `spec.md` | 询问 Coding CLI、Kernel 内部调度和仓库开发步骤 | `Docs Review 2` 回答明确指出不属于 Nano PA 手册范围 | pass | 未冒充 PA 产品事实 |

### Requirement: 回答与用户正在使用的 PA 版本一致 — 组内结论: pass

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 基础产品问答无需联网 | `spec.md` | Agent 只启用手册、`skill_view` 与 `read`，不提供网络工具，询问本机产品用法 | Round 2 真实模型轨迹与随包 `getting-started.md` | pass | 本地 reference 读取不依赖联网 |
| 用户明确询问最新版或升级差异 | `spec.md` | `Docs Live` 显式启用网络工具，查询官方仓库并对比本机 | Web IM `Docs Live` 15:13–15:17 对话 | pass | 分开描述远端 main 与本机 unit，不混淆能力 |
| 远端信息不可用 | `spec.md` | `Docs Offline` 无网络工具时询问远端最新版 | 回答明确无法确认远端，只限定在已安装手册事实 | pass | 未猜测版本或变化 |

### Requirement: 产品说明与现场状态有清晰证据边界 — 组内结论: pass

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 用户询问当前配置或运行状态 | `spec.md` | 要求按会话实际工具与现场状态核实后回答 | Round 2 轨迹确认 `skill_view`/`read`；Round 1 现场问答证据 | pass | 产品规则不替代现场观察 |
| 现场行为与说明书不一致 | `spec.md` | 比对“新建默认启用”的产品规则与既有显式 profile 的现场关闭状态；重启后复查 | `Docs Review 2` 的产品手册在刷新后仍未选中；回答与 UI 证据均按现场事实描述 | pass | 没有用默认值覆盖已保存状态 |
| 说明书没有覆盖答案 | `spec.md` | 询问不存在且无法现场核实的 `QuantumSync` 模式与配置 | `Docs Offline` 明确说明资料未覆盖、无法确认，未给出虚构命令 | pass | 有界不确定性成立 |

## 上层文档同步

- [x] `SPEC.md`（跨包顶点架构）：**无需更新**；本 unit 不改变跨包职责或依赖方向。
- [x] `docs/specs/<包>/`（长青行为契约层）：**需要更新**；`docs/specs/gateway/agent-capabilities.md` 与 Gateway 目录入口需纳入内置 skill 托管刷新及产品手册问答契约，`docs/specs/im/agents-nodes.md` 与 IM 目录入口需纳入产品手册默认选择/可关闭语义。由 orchestrator §7.1 根据最终实现归并 canonical。
- [x] `AGENTS.md` / `CLAUDE.md`：**无需更新**；没有新增仓库协作规则或架构红线。
- [x] `docs/specs/CONTRIBUTING.md`（文档规范）：**无需更新**；没有修改文档体系本身。

需要更新的长青文档将在本 unit 收尾 commit/PR 中归并；本验收报告不直接改写 canonical specs。
