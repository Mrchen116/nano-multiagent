# feat-614 Design Review

## Round 1

### Metadata

- reviewer target: `/root/design_review_614`（独立 change-design-reviewer）
- review_mode: `full`
- mode_reason: 首轮 Gate 2；覆盖首文档、完整设计、delta-spec 与 milestone 骨架，并从产品装配入口核实复用能力和锁定依赖公开接口。
- started_at: 2026-10-15T23:48:00+08:00（约）
- completed_at: 2026-10-15T23:50:54+08:00
- duration: 约 3 分钟
- reviewed checkout: `/Users/czj/Repos/nano-multiagent`，`main`，HEAD `4b152e471`；工作区有既有修改，本轮只写本报告。
- inputs: `spec.md`、`design.md`、`specs/gateway/agent-capabilities.md`、`M1-plugin-development/.gitkeep`。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING**

方案在现有职责和已安装公开 API 内可实施，新增机制与需求规模相称。批准的是设计可执行性；不代表开发 Skill 已交付、真实模型已经理解指导、业务插件已验收或生产已部署。

### Coverage 与证据

#### 现状与产品装配

- `apps/node/src/main.ts:40` 在启动时调用 `installBuiltinSkills`；`packages/personal-assistant/src/builtin-skills.ts:15-58` 从 assets 递归复制完整内置目录并替换旧资源。`scripts/build-node-release.mjs:35-36` 将已跟踪 PA assets 纳入安装包。新增独立 Skill 及其 references/templates 可以复用该链路，无需额外发现服务。
- `packages/dsh-integration/src/agent-config.ts:35-36,89` 实际创建 `WorkspaceExtensions` 并在 preset 装配中 attach；`workspace-tools.ts:52-80` 按真实 workspace 共用 owner、在每个 preset 注册管理工具和挂载树。不是仅测试使用的孤立实现。设计关于共享安装状态、每个 Agent 各有 mount、私有服务不能假定全节点单实例的判断成立。
- `workspace-tools.ts:113-137,154-202` 复用原生 profile、PluginPackages、Loader、PluginManager、Include、HMR 与泄漏审计；现有 refresh 还为每个 mount 的 isolate label 加命名空间。既有机制适合作为生命周期 owner，不需要新插件运行时。
- `docs/specs/gateway/agent-capabilities.md:636` 起的 current Requirement 已覆盖自助安装、提示词贡献、热应用、停用、共享与隔离、第三方依赖及压缩引擎。设计维持这些契约，新增开发知识与当前接口发现，不重复实现生命周期。

#### 关键决定与公开 API

- 查验 `packages/dsh-integration/package.json` 及本机已安装包 manifest：五个 topic 对应的七个包均为 integration 已声明依赖；每个包均声明 `./package.json` export、根公开 types，且 types 文件存在。DSH 包版本为 `0.2.1-alpha.1`，Cordis 为 `4.0.5-alpha.1`，loader 为 `1.0.6-alpha.1`。按 manifest 返回实际文件位置可实现，不需要猜源码目录或依赖参考仓库 HEAD。
- 已安装 `@deepseek-ai/dsh-tools/lib/types/index.d.ts:85-102` 明确 `tools/result` 为按 `exec.agent` scope-filtered 的冻结结果 emit，而 `tools/change` 为 unfiltered。设计只推荐前者作为被动局部监听，并要求按工具名过滤及管理 cleanup，支持面有具体依据。公开声明可见的其他事件不自动获得支持。
- 已安装 `@deepseek-ai/dsh-system-prompt/lib/types/index.d.ts` 的 `section`/`context` 是 scope 注册；同名可遮蔽宿主贡献，`complete` 可替换完整 section。因此设计要求独立命名、禁用完整替换做法，与实际 API 风险匹配。
- 已安装 `@deepseek-ai/dsh-compaction-basic/lib/types/index.d.ts` 公开 `BasicCompactionEngine`、配置、自动/人工压缩方法，并注明 `summarize()` 为唯一 subclass customization hook。设计复用现成引擎、保留事务与配对逻辑，适合当前需求。实施资料应按此已声明扩展点落实。
- `workspace-tools.ts:267-270` 已将 list 查询置于 pending 拒绝之前；设计对 `describe_api` 的只读处理有直接可复用落点。接口 topic 有限、包名非模型输入、返回资料而非另造 API schema，复杂度合理。

#### 用户约束与验收

- 首文档的六类用户场景均在 design 的真实旅程表有对应目标和业务效果证据：工具、提示词、服务/局部监听、压缩、调度/交付组合、宿主边界以及生命周期/失败恢复。
- 用户特别要求观察 Agent 是否理解并创作各种插件。设计明确自然语言任务不注入 Skill 名、参数或代码，保留第一次失败与修复轨迹，记录真正读指导/查 API 的行为，独立 reviewer 自行驱动创作，并将安装、业务结果、持续行为分开。该验收方案可以识别“模板可安装但模型不会开发”的实质失败。
- 报告格式以新聊天贡献和停用撤销验证，索引以文件变化后的查询验证，压缩要求真实事务而非 no-op；不是以 Agent 自述代替效果。工具选择、同 workspace 共享、跨 workspace 隔离和恢复均列入回归。
- runbook 提供隔离启动/停止、配置与代理前置、双 workspace 和同 workspace 对照；通过 IM 产品路径执行，且不宣称浏览器视觉或物理 iOS 验收。本次没有 UI 变更，不需要前端原型。

#### Delta 与 milestone

- delta 路径准确对应 canonical `docs/specs/gateway/agent-capabilities.md`；仅 ADDED 开发指导 Requirement，保留既有生命周期的原 Scenario，不错误覆盖 current。新增条目从使用者角度描述版本准确的指导、选择尊重、范围说明和真实验证，不把内部 topic schema 固化成长期产品契约。
- 单个 M1 覆盖开发发现、资产、相关测试和真实创作验收，退出标准同时包含工程检查与独立产品证据；无多 milestone 并行写入冲突。
- `M1-plugin-development/` 当前仅含 `.gitkeep`，符合 `docs/development/change-workflow.md:109-111` 与 `docs/changes/README.md:65-66` 的设计阶段骨架要求，不需要提前编造 tasks/progress。

#### 架构判断

运行时包解析留在 integration，PA 只持有随包知识资产，Node 复用现有安装和配置路径；依赖方向符合 `SPEC.md:40-50`。管理、持久化、工具选择与资源释放继续归现有 owner；指导不接管权限、路由、消息交付或调度。相较引入完整 DSH inspection 或新 API 注册表，有限 topic 返回公开资料路径避免维护第二份接口事实。可信代码与 OS 沙箱的区别明确，没有用现有 scope 审计作强安全承诺。

### 历史问题闭环

首轮，无历史问题。

### Issues

无。

### Recommendations

无额外要求；按设计中现有真实模型旅程和退出标准执行即可。已有测试本轮只做内容核对，未运行实现验收，也没有以本轮文档审查替代后续业务效果验证。

### Author Resolutions

- R1 无 issue；作者核对公开包资料、现有装配链和验收范围，与审查事实一致，接受 Approved（0/0）。无实质修改，进入默认简化实施流程。
