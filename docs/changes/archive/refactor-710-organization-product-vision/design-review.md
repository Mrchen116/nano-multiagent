# Design Review

## Author Resolutions

作者核对 R1/R2 的来源与结论：无 CRITICAL、WARNING 或待处理建议。R1 仅适用初版；用户新增主动性、并行、整体上下文与记忆方向由 R2 full 完整覆盖。接受 R2，Gate 2 对 `23add7367` 有效；后续报告保存与归档路径修正不改变方案。

## Round 1

### Metadata

- reviewer target: `/root/vision_design_review`（独立 reviewer，未参与首文档及设计编写）
- review_mode: full
- mode_reason: 首次 Gate 2 审查，覆盖完整需求、设计、现状依据及 M1。
- reviewed_commit: `20b1bb57a7eec007cc534a38b8742e6b750193e8`
- base_commit: `0287088be`
- started_at: 2026-11-04T12:58:41+08:00
- completed_at: 2026-11-04T12:59:51+08:00
- duration: 70s（显式计时区间；此前已开始文档阅读）
- checkout: `/Users/czj/Repos/nano-multiagent`，`main`；已有无关 untracked 内容保持不动。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING**

方案能够兑现本次产品方向文档修订，没有发现会使后续实施实质走偏的未解决问题。此结论批准文档方案，不代表组织数字员工的专业履职效果已经实现或验收。

### Coverage 与证据

#### 用户约束与需求覆盖

逐项对照 [motivation.md](motivation.md) 的用户原话及目标状态和 [design.md](design.md) 的关键决策：组织级平台、IM 作为协作与工作的主体、每人 PA、专业 Global 数字员工承担独立职能均有明确落点。设计以服务对象和责任区分角色，说明多来源请求不会替代长期职责；同时保留个人独立开始使用、私人信息边界、配置 owner 与请求者的区别。岗位示例明确属于方向，不冒充已内置产品能力。

长期数字员工与任务内部 subagent 的身份不同，内部委派不转移对外责任；方案没有把组织职能误写成无限权限或自动接单、自动派工，也没有新增组织架构、岗位调度或审批机制。

#### 当前事实与实际装配

- 已读六份目标文档：根 README、SPEC、`docs/README.md`、`docs/product/README.md`、`docs/product/vision.md`、`docs/product/web-im-principles.md`。旧定位确实聚焦个人在自己的机器上运行多个助手；根 SPEC 已把数字人、内部 subagent、独立 IM 中心及 DSH 执行职责分开。本次只修订产品定位与摘要，不改变这些软件架构边界。
- [IM PA](../../../specs/im/personal-agent.md) 的固定主人、私人聊天与 Work，以及 [Gateway PA](../../../specs/gateway/personal-agent.md) 的完整 Global 复用，与设计一致。实际创建入口 `apps/im-server/src/personal-agent.ts:462` 将 PA 配置为 `work_mode: 'global'` 并独立携带 `personal_agent`；`apps/node/src/configuration.ts:89` 将模式与个人身份分别传入运行配置，`apps/node/src/main.ts:334` 按模式路由至 Global。这支持“产品角色不是互斥技术类型”的设计决定。
- [组织与权限](../../../specs/im/auth-tenancy.md) 的资源空间、公司准入、聊天访问及配置 owner 边界，和 [Work](../../../specs/im/agent-work.md) 的公司 Agent 整体轨迹可见性，为现状断言提供依据。Work 可见不等于源聊天可读或配置可管理；设计保留原权限且不承诺新增可见范围。
- [Global](../../../specs/gateway/global-agent.md) 的跨聊天连续工作、Inbox 条件接收及显式交付，以及 [Task](../../../specs/gateway/task-graphs.md) 的本人 doing 责任持续推进，支持“已有机制可作为基础”，不支持声称任何专业岗位已通过端到端验收。设计保留了这一证据边界。
- [feat-705](../../feat-705-global-task-delegation/spec.md) 的“当前阶段”和最新澄清明确 Task 改造暂缓；设计只链接后续主从职责方向，不将自动记录、执行者绑定、Task 联动等未完成目标纳入 current 或本次范围。

#### 架构、职责与复用判断

完整产品方向继续由 `docs/product/vision.md` 唯一维护；README 负责最短使用入口，SPEC 负责跨包架构，两个目录负责导航，Web IM 原则负责长期界面取舍。六份文档只对齐必要摘要，较新增另一份组织总纲更容易维护，不造成平行权威。

方案复用现有 Global、PA、Task、Work 与权限契约解释当前基础，没有新软件模块、接口、数据流或依赖；DSH、Node、PA、Channels 与 IM 的职责保持原样。单一文档 milestone 无并行文件冲突，不需要迁移、部署或数据回填。

#### Agent Context：有界 Design Review

按 `agent-context-review` Mode A 核对实际消费者，区分仓库开发 Agent 和已安装 Nano Agent：

- 开发 Agent 从仓库开工路由进入文档地图与产品目录，再按需读取 vision/current specs。设计保留唯一权威、入口链接和目标/current 分层；Before 为个人多助手定位，After 为组织协作及三类角色，不改变开发指令优先级或运行权限。更新原位置、旧版本留 Git 历史，能避免新增相互矛盾的常驻总纲。
- 产品运行时实际装配为 `apps/node/src/configuration.ts:92` 的配置提示词、`packages/dsh-integration/src/agent-config.ts:150-162` 的产品身份/Persona/Global/Skills，以及 `packages/personal-assistant/src/builtin-skills.ts:14-19` 的随包技能目录。对 `apps/`、`packages/`、`scripts/` 搜索本次产品文档引用，仅文档检查脚本引用 `docs/product`；未见六份文档进入已安装产品 Prompt/Skill 的自动装配链。
- 因此无需新增产品请求抓包、模型试跑或运行 Context 生命周期验收。静态检查仅支持本次无装配变化的范围判断，不宣称模型实际履职效果已验证。实现后仍须核对最终文字与链接，确保方向与 current 的边界完整保留。

#### delta-spec、milestone 与验证

`no spec delta` 合理：本次不修改任何用户可观察运行行为、API、配置默认值或权限契约；没有需要归并的行为 Scenario。M1 覆盖六份文档、角色与隐私边界、共享 Global 执行和 current 分层，要求独立 code review/verifier，零运行产品用户旅程故跳过产品 reviewer，符合当前 workflow。

无需前端原型、真实页面走查或部署提示词：Web IM 原则是产品长期取舍文本，当前没有页面与交互变更。

本轮验证：

- `git diff --check 0287088be 20b1bb57a`：通过。
- 初次 `./scripts/docs-check` 因系统 Python 缺少 `yaml` 未执行成功；改用现有环境 `PYTHON=.venv/bin/python ./scripts/docs-check` 后通过：290 maintained Markdown sources、68 required routes。
- 未启动服务、未运行产品回归或模型实验；六份产品文档尚未实施，此处检查不是其最终交付验收。

### 历史问题闭环

R1，无历史 finding 或 Author Resolution。

### Issues

无。

### Recommendations

无必需或可选补项。


## Round 2

### Metadata

- reviewer target: `/root/vision_design_review`（延续独立 reviewer）
- review_mode: full
- mode_reason: 用户新增长期主动履职、多事项并行、PA 整体上下文及辅助长期记忆，改变需求与 M1 退出标准，按 full 复审；复用 R1 中未受影响的实际装配及权限证据。
- reviewed_commit: `197c21264cf4e1552bdd95b6b8de1923393c6626`
- effective_commit: `23add7367ebdef94888543ef0b7c6fa0e5251228`
- formatting_delta: effective commit 仅恢复 feat-705 两段引文的原有空格；已核对真实 diff 与原文，无设计变化，本轮一并覆盖。
- base_commit: `0287088be`
- started_at: 2026-11-04T13:02:30+08:00
- completed_at: 2026-11-04T13:04:02+08:00
- duration: 92s

### Verdict

**Approved — 0 CRITICAL / 0 WARNING**

新方向已完整进入设计与 M1：所有长期 Agent 持续主动履职并能推进多个事项；PA 理解主人整体上下文、辅助主人履职；长期记忆支撑相关判断和经验积累。批准范围仍是六份产品文档修订，不代表对应产品能力均已实现或通过运行验收。

### Coverage 与证据

#### 用户需求与设计决定

重新通读 [motivation.md](motivation.md) 和 [design.md](design.md)。设计关键决策 3、7 及架构总览覆盖新增方向，并把它们接成长期职责、持续感知、主动协作与并行推进、成果经验、记忆辅助判断的关系。PA 不被缩成仅处理主人私聊；其工作与生活相关背景均在愿景中，同时明确接入范围和授权限制，不宣称当前掌握所有信息。

“一项等待不阻塞其他工作、仍能交流、把更正带回对应事项”使并行的用户价值清楚；没有要求固定并发数、每条消息委派或凭空新增 Task 调度。主动性是职责内有价值的行动，既非只等新请求，也非无限通知或扩大外发授权。岗位职责、配置管理者、请求者、长期 Agent 与内部 child 的区别仍完整，R1 的三类角色及权限判断继续成立。

#### 历史原话与状态

逐条读取溯源表链接原文，核对以下内容的作者身份、原句和附近语境：

- feat-554 `spec.md:14` 的公司式人和 Agent 协作。
- feat-676 `input/chatgpt-conversation.md:2631-2640` 的第 11 轮“用户”段，明确 PA 长期服务用户、专家独立履职、组织人机协作及工作生活帮助；该段在 ChatGPT 回复之前，未将后续模型建议当成用户决定。
- feat-616 旧需求原件第 11 行与最终 spec 第 7-8 行；feat-623 第 16-17 行的直接交办/背景信息和合并感知。
- feat-394 Q1 第 34 行的后台主动性；feat-546 Q4/Q7 的统筹上下文及整体 Work；feat-635 第 94 行的 doing 持续推进。
- feat-705 第 11 行的完整事项与主 Agent 沟通；effective commit 的两段引文现已保留原有空格。其“当前阶段”仍明确 Task 改造暂缓。
- feat-676 spec 第 58 行的沟通背景与执行经验；feat-658 第 18 行的代表主人发送；feat-617 第 13 行的通用交互表达。

短摘保留原意，提炼与原话分栏。已核对 feat-665 的退役决定与 feat-667 的最终澄清：旧整包未合入、独立观察者暂不引入、聚合查询与持久关注等仍待以后按需立项；本次没有把这些历史方向变成 current 承诺。feat-394 旧 cron 语义、feat-546 当期 Task 范围、feat-616 旧专属机制均有显式状态边界。无必要恢复这些旧机制。

#### 当前契约、架构与 Agent Context

R1 已核对的六份目标文档、角色/权限、Global 实际装配、唯一产品总纲和按需阅读路径未变；`20b1bb57a..23add7367` 只改本 unit 的 motivation/design，没有运行代码或 current spec 变化，相关证据保留。

本轮新增核对 [能力契约](../../../specs/gateway/agent-capabilities.md) 的角色化记忆、纠正、正式写入和 Dreaming 生命周期：当前纠正可立即影响会话与原执行者，正式记忆只由后续 Dreaming 写入，未整理不声称已保存或跨聊天即时同步。`packages/dsh-integration/src/knowledge/runtime.ts:54-57` 实际装配 DocumentMemory/Dreaming；`document-memory.ts:39-55` 明确正式库只读边界、当前纠正立即采用及 Dreaming 后续维护。设计关键决策 7 与此一致，没有恢复前台并行写者。

继续按 `agent-context-review` Mode A 处理开发 Agent 的按需消费：新增内容要帮助开发者理解产品责任，而非改变已安装 Agent 的 Prompt、技能、工具或记忆加载时点。由 vision 保留产品原则，历史原话集中在 unit，current 细节仍链接 canonical specs，职责与消费层次清楚。未要求新增 Memory 系统、观察者或第二套执行循环，无架构维护代价增加。

#### delta、milestone、验证和限制

重新核对完整 M1，退出标准已包含长期主动履职、多事项并行、PA 整体上下文、辅助记忆和原话可追溯；仍覆盖三类角色、IM 主体、共享 Global 执行、隐私、方向/current 分层、六文档一致性及静态门禁。`no spec delta`、无迁移/部署、跳过零运行用户面的产品 reviewer 继续适用。实现阶段需审最终文字，不能把此次设计批准写成能力完成。

`PYTHON=.venv/bin/python ./scripts/docs-check` 在本轮设计基线上通过（290 maintained Markdown sources、68 required routes），`git diff --check 0287088be 197c21264` 通过；最后格式增量仅空格恢复。未运行模型、启动服务或进行产品行为验收；本轮结论为文档方案与来源一致性判断。

### 历史问题闭环

R1 无 finding。新增需求使旧版批准不覆盖更新方案，本 R2 已完成全范围复审并替代当前适用结论；未改写 R1 历史。

### Issues

无。

### Recommendations

无。引文空格差异已在本轮 effective commit 校正。
