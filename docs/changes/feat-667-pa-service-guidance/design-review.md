# feat-667 Design Review

## Round 1

### Metadata

- reviewer target：`/root/design_review_667`（独立 reviewer，未参与受审设计编写）。
- review_mode：`full`。
- mode_reason：首次 Gate 2 审查，覆盖首文档、全部设计、delta-spec、M1 骨架与两份用户附件；在同一轮应用 `agent-context-review` 的 Design Review 模式。
- started_at：2026-10-27T12:09:00+08:00（近似，开始时未单独采集时钟）。
- completed_at：2026-10-27T12:12:44+08:00。
- duration：约 4 分钟。
- source baseline：`/Users/czj/Repos/nano-multiagent`，`main`，`69d01e4557bcc87a5f7194dcb947c7473ead20d9`；设计及 delta 为工作区未提交输入。审查只写本报告，不修改受审文件、产品代码、分支或生产数据。
- 受审内容 SHA-256：
  - `spec.md`：`939846cc9e9d89f458bc6584d6ff308a00693683d8ce7a93fcd6eab67d3aa994`
  - `design.md`：`f28d9a7cbd08396330a6be074c726bc814f95f8ce01053709c90b6e9b540b3a4`
  - `specs/gateway/personal-agent.md`：`fe025c8a08e22bbcbc54034c5dd0529cebd005b23944b1e6891127ab87e99c38`
  - `input/split-instructions.md`：`9f699734035ce6d46eacf2ccd37fd23b9868e2705894ac8bc2f12cd66821505f`
  - `input/pr414-review.md`：`e67c56b6f6fb8dbfa4c53d717d126a41ed210e7c0367284e656fabc383d8434c`
  - `M1/.gitkeep`：空文件，目录内无预填 tasks/progress。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。**

三份产品文本的设计边界可进入实施。此结论仅认可方案及其验证约束，不代表真实原生二级委派、并行更正/停止、等待响应或轻量准备已验收。设计明确要求关键旅程不支持时标 blocker/B，M1 不完成、PR 保持 Draft；不得把本次 Approved 用作产品通过或 Ready 的依据。

### Coverage 与证据

#### 现状与实际产品装配

- 默认指导的真实入口已核对：`apps/im-server/src/personal-agent.ts:319-347` 的 PA 创建路由仅在未恢复既有配置时构造含 `personalAgentDefaultInstructions` 的 candidate；active binding 直接返回。`apps/node/src/configuration.ts:79-105` 将 `custom_prompt` 映射为 `systemPrompt`，携带真实 Skill roots 与选择模式；`packages/dsh-integration/src/agent-config.ts:126-163` 在 Agent 上挂载 Persona/Skills，配置清空会 dispose Persona，不从默认文件回填。因而修改默认文件不等于给既有 PA 自动替换自定义指导。
- 随包 Skill 已接入正式节点启动：`apps/node/src/main.ts:50` 调用 `installBuiltinSkills`；`packages/personal-assistant/src/builtin-skills.ts:18-67` 遍历目录、刷新随包名称。新增目录无需增加注册 API。`configuration.ts:98-105` 将 workspace roots 排在 owner/global roots 前；`packages/dsh-integration/src/capabilities.ts:137-158` 在 list/get 两路过滤 allowlist/denylist，并按 root index 提供 rank。设计对用户选择和原有发现路径的复用有代码依据；随包方法升级仍须与自定义 prompt 保真分别验证，不能声称既有 Agent 的全部行为逐字不变。
- 固定来源/权限规则来自正式 preset，而非默认文案：`agent-config.ts:105-111` 安装 GlobalMode 与 PersonalTools；`personal-security.ts:132-136` 提供可信 owner、participant/observer、原始授权、主 PA 代表发送及披露边界；`global-mode.ts:18-43` 区分公开发送、内部 child 回执与私人草稿。A 不触碰这些接口，私人准备不自动转成外发许可，与现行规则相容。
- 观察数据及唤醒有既有路径：`packages/personal-assistant/src/global-agent.ts:237` 允许主人正常来信时读取已积累背景；`:257-308` 保留背景期限、observer 提醒及无授权升级语义；`:358-404` 摄取观察事件。A 复用这一通路，不需要新 attention/query receipt 服务。
- 已检查现有测试的证据能力：`personal-child-delivery.test.ts:14-34` 使用 fixture 主动 fork、直接执行工具及替代模型 stream；`personal-security.test.ts:69-99` 检查 Skill/普通工具与清空、禁用后的装配。这些可复用作工程回归，但不能证明真实模型会主动读 Skill、继续二级分工或接住并行更正。设计对此已有明确区分。

上述为当前 main 中生产代码路径的静态核对，未连接或检查线上部署版本，未运行生产服务。

#### 用户约束、决定与职责

- 两份附件要求先 A、保留 #414、从 main 拆取；不带入新记忆、统一检索、关注库、执行绑定、文件发布及新调度器。`design.md:19-26,38-46,69-77` 明确保留这些限制，也没有把旧 #414 的白名单执行者作为前提。附件中的旧版本缺陷仅作为范围依据，本轮未将其当作当前 main 的缺陷。
- 首文档七个场景均能映射到验证计划与 M1：小事直答/长事真实结果；两个独立事项中的更正、短问题、单项停止；有内容的私人准备、已处理/无新价值/覆盖不足；自定义、清空、禁用。`design.md:91-101` 要求真实输入、工具回执和用户结果，而非字符串存在或 spawn 成功。
- 架构职责合理：IM 保留首次创建默认值，PA 随包 Skills 持有可复用工作方法，Node 安装与提供配置，integration 继续持有运行时与安全装配。复用 Inbox/Task/Heartbeat/schedule/文件及 Memory，避免为方法指导另建状态权威或执行管理器；没有新增跨包依赖、private import 或第二 Agent loop。
- 单 M1 适合三份紧密相关文本及同组真实旅程验证，拆并行 milestone 无独立交付收益。原生能力不明是已识别的实施验证风险；设计给出失败后保持 Draft 的处理方式，因此不构成需要先暗中扩入 B 的设计空洞。
- 无前端变化，采用实际客户端使用的登录/聊天/配置 API 验收符合本片范围；无需 UI 原型。无部署迁移，回退区分随包文本与已经持久化的新 PA custom_prompt，未承诺回退代码会重写用户配置。

#### Agent Context — Design Review

- **Surface / Consumer**：主 PA 的默认 Persona、按需 Skill 元数据/正文、现有 Inbox 与 conversations 来源、原事项记录及子 Agent 交接。普通 Global Agent 可消费共享持续工作方法；可信身份仍由宿主提供。
- **发现与时点**：常驻指导提供选择原则，复杂工作方法按需加载；默认创建、配置更新、禁用和 Skill roots 均有正式入口。真实模型请求、目录发现、正文读取及工具回执被列入验证与退出标准，未把磁盘文件存在等同于模型消费。
- **语义与组合**：Before/After 将“仅跟进已交办消息”扩展为“重要观察可核对并私人准备”，同时保留不创建新外发授权、核对后续状态、不把确认收到视为交付。与固定安全提示及 Global 显式发送机制无确定性冲突。设计中“子 Agent 只收到所需交接信息”按 `design.md:42,56` 的整体语境理解为交接文案最小化要求，不解释为新增运行时上下文隔离保证。
- **更新与恢复**：原工作记录保留真实执行 ID、当前要求和等待条件；更正/取消回到原事项，晚结果不成为复活理由。当前文件与工具可用性、跨事项真实行为必须由实施证据验证；没有用新 schema 或跨重启保证补齐未知能力。
- **证据状态**：当前装配与验证计划有直接源码/文档依据（CONFIRMED）；候选文字实际进入 provider 请求、模型正确发现 Skill、二级执行返回、并行取消及静默行为仍未验证。本轮无可成立的 Context CRITICAL/WARNING，不从未知模型行为推定缺陷或成功。

#### Delta-spec、验收与回退

- delta 正确锚定 `docs/specs/gateway/personal-agent.md` 的“默认服务指导复用普通配置和 Skill”；完整保留原“用户调整服务方式”“跨轮次持续工作”两个 Scenario，新增“重要观察后的私人准备”。新增行为有默认指导、来源可读和 Skill 未禁用的前提，不改变 IM 配置协议。
- Runbook 使用仓库 e2e 脚本、独立 `/tmp/pa667-review` 数据与合成账号；`scripts/e2e-up.sh:31-35,112-115` 支持由脚本确定代码根、用 `--wt` 指定隔离数据位置。真实模型可用性先做小请求核实，功能及失败分支不推迟到生产；未要求生产写入、迁移或重启演练。
- M1 退出标准明确全部七个场景、真实 Skill/二级委派能力、有限基线对照与选择保真。关键缺口仍阻断完成，与附件要求一致；Draft 中可审阅文本不等于允许跳过 M1 退出条件。

### 历史问题闭环

无历史 Round；无待关闭 issue。

### Issues

无。

### Recommendations

- **R1-R1（可选，证据表述）**：实施记录可单独标记观察准备来自十分钟背景通知还是主人正常来信提前触发（`design.md:89`）。两者均是已有合法入口；后者能证明读取后的准备行为，但不能单独证明到期自主唤醒。保持这一证据边界即可，不要求为 A 修改通知节奏或增加运行时机制。

### Author Resolutions

- R1-R1: accepted。实施证据区分十分钟背景通知与主人来信提前触发；后者不证明定时自主唤醒。不改变受审产品范围、设计或验收要求。
- Author 已核对报告与当前代码；无实质异议，受审文件未修改。Gate 2 R1 retained。
