# bugfix-629: 上下文增长修复与 Codex Skill 生命周期对齐

## Changelog

- 2026-10-21：用户明确确认新模式只重建可用 Skill 目录、旧正文按需读取；要求删除额外已用 Skill 恢复与候选版 interrupted_turn，按原有 Notes/History 复验事故。R2 全文回退与当前 turn 导航设计因此失效，本轮重新执行 Gate 2。既有 rc.2 证据保留为候选基线，不代表新方案通过。

## 现状分析

生产事故版本 Nano `be6c1271b` 与插件 `0.3.0-rc.1`。Nano 当前实现将会话曾用 Skill 全文加入每次 runtime context assemble；插件每步变化的引用及 Notes hint 触发 DSH 完整快照追加，导致无变化正文反复增长。硬阈值换窗后模型依据旧完成 Notes 结束，未恢复已读新 Inbox 请求。原始证据与默认预算见 [incident](incident.md)。

候选 rc.2 已移除高频动态引用，但添加了已用 Skill 索引/无工具时全文回退、`interrupted_turn`、History `turn_id` 扩展。这些候选设计现按用户选择撤回。主仓原有 dirty 文件和调查报告不在本 unit 修改范围。

## 参考行为与边界

Codex 固定源码 `464add49587a7cb6032d5ab04faa8a1585947853`：
- `core/src/session/mod.rs:4854`：token-budget 换窗重建当前环境；不重跑原用户输入的 Skill 选择。
- `ext/skills/src/world_state_catalogs.rs:356`：目录属于环境贡献；`extension.rs:370` 的显式 Skill 正文属于本次输入。
- `core/src/session/mod.rs:4920`：上下文基线与增量。DSH 原生 runtime context 采用完整快照比较，因此本插件不再将每步引用、Notes 修改作为环境变化；不在本 unit fork/patch DSH 或接管所有环境贡献。
- `ext/history-notes/src/extension.rs:115`：新窗口取得 bounded Notes hint，正文由工具按需读取。后端内部提示生成逻辑不可见，本地实现不宣称服务端逐字等价。

遵守 DSH 公开 exports、Cordis hooks、原生 Session/compaction 事务。无摘要、无对话 tail、无自动 Notes 正文、无新的任务状态数据库或恢复协议。业务权限与来源保持。用户明确禁止本轮加入 interrupted_turn；如果原有 Notes/History 无法通过事故场景，报告真实失败，不能自行恢复该协议或增加隐藏提示使测试通过。

## 架构与关键决策

1. **稳定插件环境贡献。** 保留候选 rc.2 对高频贡献的修复：`agent-context:references` 仅提供窗口身份；引用仍经已有 `get_context_remaining` 与 fallback 提示按需取得。Notes hint 只在窗口构造时产生。普通工具/Notes 进展不修改插件 runtime context，避免触发整份宿主正文追加。不引入另一套 runtime projection。

2. **新模式完全取消额外已用 Skill 恢复。** Nano `KnowledgeRuntime` 的恢复 hook 在公开 `agentPresets.serviceFor(agent, 'compaction')` 返回当前 workspace owner 时直接返回 assembly，不读取 session usage references、不追加 `nano-used-skills` 索引或正文。复用 `NanoCompaction` 已有 owner 判断，不增加开关/状态机。当前内置 owner 即无摘要换窗引擎。使用统计和自动 Skill 维护职责保留。

3. **复用原生目录和按需读取。** DSH `tool-skill` pre-step 已根据活动 surface 上的目录、当前有效 Skill 集合与工具可见性重新发布目录；正文不在目录中。目录未变且仍可见时不重复。显式 `/skill:name` 首次注入不变；换窗不重放旧输入。可调用 `skill/read` 时按当前权限读取；无这些业务工具时，已加载的 `skill-invocation` 或工具结果通过当前会话 History 按需恢复，来源不升级为新的人类授权。不因恢复扩大白名单。显式停用新模式后，旧摘要模式保留原有全文恢复，不把它称为 Codex 新模式。

4. **撤掉候选自定义任务恢复协议。** 从插件删除 `interruptedTurn` helper、checkpoint `interrupted_turn`、HistoryItem/`list_items/search` 的 `turn_id` 字段与过滤、相关提示和专有测试。History 回到原有 window/item 定位、分页、来源和当前 session 范围。新窗口仅保留原有 Notes hint、窗口身份和有效环境；不补充最近输入副本或当前任务提示。不删除真实历史、Notes，也不重置生产会话。

5. **恢复效果由真实场景决定。** 保持原 Codex 适配的 Notes/History guidance；移除候选专用协议文案。Agent 自行读 Notes，必要时查原始 History。当前任务继续要求完成且不重复交付；模型如果误信旧 Notes，按失败记录。本轮不用脚本预设最终答案，不放宽默认预算或绕过 Auto off。

## 接口、包与数据流

- Nano 修改 `packages/dsh-integration/src/knowledge/runtime.ts` 及 `tests/model-policy.test.ts`；新模式跳过恢复 contribution，旧模式恢复原全文行为。
- 插件修改 `src/history.ts`、`tools.ts`、`checkpoint.ts`、`index.ts`、相关测试/README/golden，删除候选 turn 协议；每步贡献稳定化保留。
- 原生目录 source 保持 `skill-catalog`；显式正文 source 保持 `skill-invocation`，History 不重新标记。
- 已发布 rc.2 不覆盖、不重打 tag。修订版发布新的不可变 `0.3.0-rc.3`，Nano dependency/lock 精确 pin tgz 并校验下载 hash。安装包发布不等于生产部署。
- 对外 delta 见 [agent-capabilities](specs/gateway/agent-capabilities.md)，仅当前 unit 先改目标契约，完成验收后再归并 canonical。

## Runbook for Reviewer

复用隔离 worktree `/Users/czj/.codex/worktrees/bugfix-629-context-recovery/nano-multiagent`，配置、端口、workspace、identity、数据库均使用其 e2e 实例。启动/停止依照 `scripts/e2e-up.sh` / `scripts/e2e-down.sh`，运行时升级使用正常停止/启动并保留隔离数据。最终验收前提供固定包 hash、API 地址、测试身份、Agent/conversation ID 和 provider 请求路径。实际入口是 Web IM 使用的消息 API，不用私有 session.submit 替代产品验收。

默认预算 C=258400、O=32768、B=16384、R=6144；不提高 buffer、不修改 policy、不伪造压力。真实模型使用已配置的 codexOAuth:gpt-6-astra。合成工具资料需避开原生 spill 的单项上限，多项实际读取可产生压力；若本次没有实际触发目标边界，只记录未覆盖。

必验场景：

1. **原事故**：旧任务已完成，Notes 已记完成；随后新 Inbox 请求已被读取。通过实际工具结果增长，在未保存新 Notes 前触发 pressure/overflow 换窗。新窗口确认无旧任务正文、无 interrupted_turn；观察模型是否通过原有 Notes/History 恢复最新输入和资料，完整交付一次。必须检查原生事件、真实 provider 请求、History 调用与 IM 落库。失败如实报，不添加新任务导航绕过。
2. **Skill 生命周期**：使用至少七个合成 Skill（正文总计 >=52400 字符），换窗后目录按原生机制重建；无旧正文和 nano-used-skills；不少于六步普通工具/Notes 操作不增长同份正文。确有需要时真实调用 skill 重读。
3. **受限与重启**：默认新模式下 `['workflow'] + /skill:name` 首次正文出现；换窗和正常重启后不自动恢复正文或已用索引，History 可读到原 skill-invocation 正文且来源不变。不临时开放 skill/read。具备 skill 工具的配置验证原生目录与重读。显式 off 后旧摘要恢复正文；on 后再次换窗回到新规则。
4. **已有路径回归**：原窗口/item History 长记录分页、tool pairing、fork/session 隔离、Auto off、空业务白名单、主动/硬阈值/overflow、Notes 持久化沿用有效测试，凡依赖 turn_id 的证据失效重验。

## 风险与验收边界

删除自动正文后是否正确重读是模型行为，需要真栈验证。没有特殊 interrupted_turn 导航时，硬阈值场景可能仍被旧 Notes 误导；这不是补提示前先假定成功的理由。若失败，交付实测结果与剩余根因，回到用户确认后再考虑下一方案。生产数据不改、不清空；新部署需已有明确授权或最终 PR 审查后决定。

## Milestones

| ID | 标题 | 依赖 | 并行组 | 范围 | 退出标准 |
|---|---|---|---|---|---|
| M1-recovery | Codex Skill 生命周期与原 Notes/History 事故复验 | 无 | 单主线 | Nano knowledge/测试/固定包，插件候选协议撤除与稳定贡献，相关契约 | [worker] 有效红测后新旧模式、目录/正文、来源、重启及插件全量通过；不可变安装一致。[reviewer] 按默认预算复验原事故，真实 Notes/History 恢复并完整交付一次；Skill 正文无自动重放与逐步增长。失败不得记为通过。 |
