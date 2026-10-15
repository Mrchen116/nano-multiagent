# feat-614 Code Review

## Round 1

### Metadata

- reviewer: `/root/static_review_614`，未参与受审实现的独立 reviewer
- skill: `change-code-review`
- review_mode: `full`
- validated_at: `7befe5a7971dbb85b37a73c46e409f18f1ca923d`
- executed_base: `46d3e8c8e`
- reviewed diff: `46d3e8c8e...7befe5a79`，23 个文件，386 insertions / 22 deletions
- checkout: `/Users/czj/.codex/worktrees/feat-614-plugin-development/nano-multiagent`
- branch: `codex/feat-614-plugin-development`
- reviewed working tree: 开始审查时 clean；本轮只新增本报告，不修改源码、测试、设计或配置，不提交。
- scope: 仅代码审查；不兼任 verifier，不执行真实模型产品验收，不操作主 Agent 管理的共享栈。

### Verdict

无存活代码 finding。本轮范围内未发现 maintainer 需要处理的具体正确性或维护风险。

```json
[]
```

### 检查范围与依据

- 完整阅读新增 `plugin-development.ts`、管理工具接线、测试增量、新 Skill 与全部 references/templates、产品手册修订和两个文档入口增量；结合 unit spec/design、current 插件行为契约判断需求边界，不将真实模型理解能力当成静态审查结论。
- `describe_api` 只接收五个固定 topic，包名来自静态映射；七个包均为 integration 已声明依赖。独立核对当前安装 manifest：版本与公开 `package.json`/types exports 存在，解析逻辑适用当前锁定格式。返回公开声明/可选 README 的绝对路径和支持边界，没有读取用户配置、凭据或其他 workspace 状态；缺失声明文件与非法 topic 明确失败。
- 查询经现有 Agent 管理工具执行，放在 pending mutation 检查和串行变更链之前；未加入网页 mutation 入口。其他管理动作的执行、持久化、工具选择、服务审计和生命周期路径保留。
- 核对当前公开 types 中的 `tools.register` 输出契约、`systemPrompt.section`、Cordis `provide`/`effect`、`tools/result` scope-filtered frozen emit 与 BasicCompactionEngine 的公开 summarize 扩展点。模板与指导使用当前公开能力；服务 provider/consumer 在同一隔离 group，监听由 Cordis 生命周期管理，过滤自己的工具名；文档准确说明每 preset 实例、共享安装状态、可信代码及宿主保留职责。
- 核对现有 `installBuiltinSkills` 的递归复制/刷新与 Node 启动调用，以及 `scripts/build-node-release.mjs` 的已跟踪 assets allowlist：新增 Skill、references、JSON/YAML/MJS 模板会沿既有链路随包交付，无需新增安装机制。
- 新增回归从真实 runtime 的管理/执行 seam 验证主题解析、非法主题、pending 查询、模板安装使用、提示词贡献、跨 workspace 事件隔离及停用/恢复/移除；复用既有 workspace 生命周期测试，没有删除已有保护。真实模型是否自然发现并正确创作插件交由独立产品验收。

### Validation 与限制

- 复用 caller 提供且与受审 tree 相符的可信证据：`/tmp/feat614-query-red.log`（入口未实现）、`/tmp/feat614-query-green.log`（1 passed）、`/tmp/feat614-templates.log`（2 passed）、`/tmp/feat614-typecheck.log`（递归 typecheck passed）与 docs-check（239 documents / 64 skill entries passed）。本轮读取 green/templates/typecheck 原始日志，并核对对应测试代码的覆盖；没有因角色更换重复运行有效测试。
- 独立执行 `git diff --check 46d3e8c8e...7befe5a79`，通过；核对 HEAD 与分支、起始 clean 状态、当前安装包 manifest 和公开声明。
- 本报告不证明真实模型创作、客户端视觉体验、物理 iOS、生产部署或完整 unit 一致性；这些不属于本轮派发范围。未留下需要追加核验的争议候选。

## Round 2

### Metadata

- reviewer: `/root/static_review_614`，保持独立于受审实现
- skill: `change-code-review`
- review_mode: `patch`（caller 所称 delta 复验，对应本 skill 的 pre-fix 到固定 HEAD 范围）
- validated_at: `246c484aeba1c4905f902b40b52cb74a191e29b8`
- executed_base: `46d3e8c8e`（沿用本 unit 的已执行基线）
- pre_fix_head: `7befe5a7971dbb85b37a73c46e409f18f1ca923d`
- reviewed diff: `7befe5a79..246c484ae` 中 feat-614 的修复、测试与指导增量；排除 merge `59b7b3dc9` 引入的 feat-615 首文档。
- checkout/branch: 同 Round 1；开始时有本报告及 `M1-plugin-development/validation.md` 两个未跟踪文件，仅追加本报告。
- scope: 热更新修复及受影响生命周期、公开接口和架构边界；暂不执行 verifier，不操作运行栈，不提交。

### Verdict

无存活代码 finding。真实模型发现的“同名同版本更新后仍执行旧模块”已有明确红绿证据，本轮补丁修复与当前公开 loader/Fiber 契约一致。

```json
[]
```

### 检查范围与依据

- 阅读 `WorkspaceOwner.refresh` 完整刷新、审计及清理链路和修复 diff：先收集现有 fiber、递归收集新配置的 id/name，只有同 id 的 module name 变化才通过所属 `EntryGroup.remove` 退役旧条目；等待其 unload transition 后，继续由原生 `root.update` 创建新条目，既有审计、故障撤销、工具集合更新和 resolver 回收顺序保留。未引入第二套 loader、运行时补丁或 private import。
- 独立核对已安装 loader 的公开根 export 确实 re-export `Entry`/`EntryGroup`/`EntryTree`，公开声明包含 `entry.parent`、`EntryGroup.remove`、`root.update`；Cordis 公开 `Fiber.inertia`。核对对应安装源码确认 remove 会 dispose fiber、从 group/store 移除旧条目，active entry 的普通 update 不重新 import 新 name；fiber disposal 同步启动卸载，inertia 覆盖受管资源 cleanup。修复针对实际缓存机制，未强制重建全部 workspace 或宿主 preset。
- 热更新路径继续在现有串行 mutation 与 HMR exclusive 内执行，依赖解析表在旧 fiber 清理期间保留，全部 mount 处理后才收缩至新解析表。相同 workspace 的各 preset 均走替换路径；不改变跨 workspace owner、命名空间隔离、禁用选择或静态工具白名单。
- 新回归使用原生 `plugin_manager install_bundle` 更新同包名、同版本及同 row id 的真实源码，再在同一轮原生调用核对 `UPDATED:HOT_UPDATE`，并在同 workspace 另一 Agent 核对 `UPDATED:PEER_UPDATE`；能直接挡住此次发现的故障。修复后运行的是包含既有安装失败/修复、模板、隔离、启停、重启与压缩路径的完整 workspace-tools 测试，而非独立模拟 loader 的测试。
- 工具指导新增的 `exec.agent.session.header.cwd` 与当前公开 ToolExecution/Agent/Session 路径及 Nano `SessionBinding.cwd` 创建链路一致；要求以会话 cwd 或明确 workspace 为基准，没有引入 process cwd fallback。design Changelog 只记既定更新场景的验收发现，不改变开放面。

### Validation、retained 与限制

- 阅读 `/tmp/feat614-hot-update-repro.log`：原实现实际返回 `{ "echo": "HOT_UPDATE" }`，未包含期望的新前缀，故障条件已直接确认。
- 阅读 `/tmp/feat614-hot-update-fixed.log`：同一 workspace-tools 真实 runtime 测试修复后通过，1 test / 1 file passed，28.08 秒。复用该有效证据，未重复运行全量测试。
- 独立 `git diff --check 7befe5a79..246c484ae -- packages docs/changes/feat-614-workspace-plugin-development` 通过。未把排除范围内 feat-615 文档的格式问题作为本 unit finding。
- Round 1 中 API topic/版本发现、Skill 资产发布、模板内容、查询 pending 行为和未修改文档入口的检查继续保留；本轮覆盖热更新及 cwd 指导增量。此 retained 仅说明代码审查覆盖，不替代最终集成基线的门禁失效判断。
- 本轮仍不证明真实模型全部创作旅程或完整 unit 一致性，后续 verifier 与产品验收独立执行；没有需追加核验的存活候选。

## Round 3

### Metadata

- reviewer: `/root/static_review_614`
- review_mode: `patch`
- validated_at: `972b047acac0448c4f6e9c24a2f5e2a1fc2d7933`
- executed_base: `46d3e8c8e`
- reviewed diff: `246c484ae..972b047ac`，只增加 `references/verification.md:19` 的全局主会话手动调度排队指导。
- retained: Round 1/2 运行时代码、测试与资产结论有效到本 HEAD；运行时代码仍为 `246c484ae`，本轮只复核上述指导增量，不重跑有效全量测试。
- effective_base: `08b06c57b`
- effective_through: `a60a3239e39836e22a09a8478a52a3eb0ca0fc19`
- final sync retained: 独立核对 `972b047ac..a60a3239e` 与上游 `59b7b3dc9..08b06c57b`：仅 feat-615 的 7 个 active design/review/prototype/delta 文档、336 insertions，无运行时代码、当前 specs 或 feat-614 资产变化。无需重跑已有效代码审查或测试。

### Verdict 与依据

```json
[]
```

无存活 finding。核对 `global-agent.ts:149-157` 将主会话 `schedule.run` 发送为同 session 的 `schedule.command`，及 `index.ts:474-485` 验证任务归属后 `agent.followup` 入队、返回 input evidence 的实际链路；accepted/pending 不等于业务任务已完成。新增指导要求交代状态、结束当前轮、随后核实消息，不在当前轮 sleep 等待后续输入或重复触发，和原机制一致。`cron.test.ts:56-61` 保留手动输入 admission/稳定身份去重覆盖；此次没有运行时行为变化或新回归风险，不增加逐句文案测试。`git diff --check 246c484ae..972b047ac` 通过。

本轮只追加本报告并更新 verifier 的有效范围；产品最终证据仍由独立 reviewer 提供，不以本轮静态核对替代旅程验收。
