# bugfix-674: Skill 使用统计 — 技术方案

对齐 [incident.md](incident.md)；用户已选择仅展示修复后新统计。

## Changelog

## 现状分析

- 涉及范围：integration knowledge/files.ts 持有 .usage.json 与样本，runtime.ts 接收 skill 成功/显式调用事件并提供 knowledge.usage；IM agent-settings.ts 白名单投影；Web Agent 详情和 iOS AgentSkillsView 展示统计。
- 既有约束：DSH 公开 exports、产品层依赖方向不变；统计不受 skill_creation 控制；现有 root 文件锁和 atomicWrite 保持单次持久化原子性。
- 可复用能力：复用 use() 的去重与锁、UTC 日桶和现有统计接口；不复用 session_refs 重建新总数；保留旧 use_count/uses_since_last_B/session_refs 供维护行为使用。
- 相关历史：feat-349 知识维护及当前 F4 逻辑读取既有字段；本修复不重构维护。当前 main 含 perf-670，基于最新 main 验证页面，避免用旧基线替代当前实现。

## 架构与关键决策

1. **单一记录内新增按 agentId 的统计聚合。** 每条 Usage 新增可选 statistics，key 为配置绑定的产品 Agent ID；值为 since、use_count、last_used_at、days（UTC YYYY-MM-DD → 次数）。运行时从 config.agentId 传入归属，模型不能传入。样本新条目附 agent_id，读取新统计仅展示该 Agent 的新引用；未标记的旧引用仍留给原有维护读取。
2. **不从旧数据初始化新统计。** 第一次未去重的新 use() 创建该 Agent 的统计值；所有统计与样本、原维护计数在同一次 atomicWrite 中提交。没有新统计的本地 Skill 保留来源/状态元信息，计数为 0、起点为空；共享 root 没有该 Agent 新统计的条目不冒充该 Agent 已使用的 Skill。
3. **累计持久、日桶有界、引用有界，三者各司其职。** use_count 不随日桶/样本清理下降，日桶保留最近 30 个 UTC 日，session_refs 仍最多 60 条，既有 recent_call_keys 200 条去重窗口不变。不同 Agent 使用共享 Skill 不混计，归属不再依赖会话是否还能被查询。
4. **明确服务端日期与统计起点。** API 每项增加 statistics_since（string|null），整体返回最早新调用 statistics_since 和 period_start/period_end（UTC YYYY-MM-DD，含首尾 30 日）。heatmap_data/trend_buckets 继续为 30 个整数，新累计数仅指新统计。旧样本或旧 raw use_count 不进入输出统计。
5. **客户端只画真实统计窗口。** Web 热力图从 365 天改为 30 天，并按 API 的 UTC 日期定位；统计起点之前的格子标为未纳入统计，不显示“0 次”。列表/Agent 视图在现有上下文中显示统计起点或尚无新调用。iOS 使用现有趋势与字段控件，明确“最近 30 天（UTC）”及新统计起点。

## 接口与数据流

- KnowledgeFiles.use(root, name, agentId, sessionId, callId, location, now?)：签名由所有内部调用者同步更新，agentId 必须来自宿主配置。
- KnowledgeFiles.usage(roots, agentId)：输出该 Agent 聚合，移除属于样本推断的异步 belongs 回调。只返回当前 Agent 的统计投影，不把 statistics 中其他 Agent 数据透传。
- KnowledgeRuntime.used() 保持原事件和 F4 判断顺序，传入 config.agentId；usage() 仍按该配置允许的 skillRoots 读取。
- IM 只显式转发新增公开统计字段；Web 的 /settings/usage 及 iOS 的 /skills/usage 两条真实接口均须核对；客户端只消费公开投影。
- 原始 use_count、uses_since_last_B、recent_call_keys、session_refs 与 curate/batch/references 的用途和保留策略不变，不改 prompt、历史恢复或工具定义；统计不新增 Context 消费面。现有知识维护回归验证该隔离。

## 前端原型

- [prototype.html](prototype.html)：现有 Skill 列表和 Agent 使用卡片的局部增量，覆盖新计数、尚无新调用及起点前日期。不是替代整页的新设计。
- 沿用现有白色卡片、灰色辅助信息、日格和列表，阅读顺序为次数 → 统计起点 → 30 天趋势。统计口径是用户判断所需信息，不展示内部文件、截断上限等实现细节。
- Web must-match：30 天实际窗口、明确 UTC、计数与起点、起点前不称零；桌面及 390px。
- iOS may-adapt：用既有 List/LabeledContent 展示同一语义；无布局/导航变更，编译和解码回归，共享链路通过 Web 验证。
- 当前 UX 来源：agent-detail-page.tsx 的 AgentHeatmapCard/SkillTrend，AgentSkillsView.swift；本地原型 file:// 自动预览被浏览器 URL 安全策略阻止，Codex 原生窗口也禁止自动读取；未尝试绕过。原型视觉未验证，不声称已实际渲染。真实产品的隔离 HTTP 入口由后续产品验收独立观察；设计审查明确保留此证据限制。

## 契约层增量

- IM：[specs/im/agents-nodes.md](specs/im/agents-nodes.md) → docs/specs/im/agents-nodes.md。

## 风险与回退

旧统计不补回，符合用户选择；保存源数据以便以后单独研究。新增聚合与旧记录共存、单文件原子写；回滚旧代码会显示旧口径，恢复新版仍读取已保存的新统计，不运行破坏性迁移。新统计起点是首次被本实现计入的调用，而非安装时间。同一个产品 Agent 在不同 root 的统计求和，窗口日期统一为 UTC。

## 一次性部署迁移

无；不对生产做批处理或删除。新增字段只在正常使用时写入。

## Runbook for Reviewer

在本 unit worktree 使用 ./scripts/e2e-up.sh --profile daily --vite；停止用 ./scripts/e2e-down.sh。端口、运行目录、配置及身份均由脚本隔离。浏览器从真实 IM 登录进入 Agent → Skills。自进化关闭场景使用隔离记录提供者驱动真实 skill 调用，不调用生产或外发。规模计数与重启持久性由最低层回归覆盖，产品 reviewer 独立观察真实接口和 Web 结果。

Review 驱动方式：改 Web 客户端，必须实际浏览器走查新统计/空态与 390px；iOS 只做相关编译、解码/文案回归，不要求复制浏览器旅程。

验收前置：已有本地依赖与 daily fixture；使用专用临时 Skill 和独立 Agent/workspace，旧记录样本仅由临时 fixture 构造，不复制用户数据。

## Milestones

| ID | 标题 | 依赖 | 并行组 | 范围 | 退出标准 |
|---|---|---|---|---|---|
| M1-statistics | 新统计聚合与公开投影 | 无 | 单组 | knowledge、IM projection、Web/iOS 统计与测试 | [reviewer] 自进化关闭仍计数；旧数据不进入新统计；用户可辨计数起点/UTC 30 天；390px 可读。[worker] >60 次/跨 Agent/跨日/重启/去重通过，维护字段不变；IM 不泄漏其他 Agent 聚合；客户端测试/构建与适用 CI 通过；真实入口证据与原型对照。 |
