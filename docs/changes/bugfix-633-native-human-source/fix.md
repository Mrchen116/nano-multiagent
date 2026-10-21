# bugfix-633：恢复直接真人输入的 DSH 原生来源

## Relations

- Related: refactor-581
- Related: feat-627

## 原始报告

用户在侧聊确认并派发：

> 恢复直接真人输入的 DSH 原生来源语义。请实际实施、验证并按仓库流程交付，不只提出方案。
> Nano 直接真人消息 source.kind 从 nano-human 改回 DSH 原生 user，保留 actorId、channel、messageId、contextEnvelope 等必要身份与来源元数据，通过 DSH 公开扩展方式接入。
> 同步调整 Nano 审批、Workflow、历史展示等消费者。注意原生子 Agent 初始任务也可能是 user，不能只凭 kind=user 就赋予真人授权；保持宿主身份与子 Agent/父任务来源区分。旧历史中的 nano-human 在读取时兼容，不改写已有会话历史。
> 直接消息显式 Skill 识别优先复用 DSH 原生机制，撤除重复适配，保证只注入一次。保留现有产品契约；如原生语法与 Nano 已有入口有具体差异，核实后只保留必要的薄适配，不另造通用框架。
> 来源资格不等于用户同意任何目标，不放宽具体意图或安全审批。

范围已收口：同一真人轮次先执行其他工具后仍可创建目标；新的真人输入重置重复工具计数；系统、定时、Agent 来源不获真人资格；审批、Workflow、历史与显式 Skill 回归正确。Global/PA Inbox 真人资格桥接、nano-system、nano-skill 去重 ID、换窗取消检查、Issue #377 均不在本次范围。保留 839880856 的原生压力裁剪/Inbox Skill 修复。交付 PR，不合并或部署。

## 现象 / 复现

审计基线为 main c88536f59，开工同步到 origin/main 536d5a29f；DSH 0.2.1-alpha.1、dsh-agent-context 0.3.0-rc.5 未变。

直接真人输入被写为 nano-human，原生 create_goal 的 root Agent 当前开放 turn 检查只认 user；先 read 或其他工具后仍在同一 turn，但来源不匹配导致 GOAL_TOOL_AUTHORITY_REQUIRED。原生重复工具提醒也只在 pre-step 接收 user 时清零，因此新的真人要求没有重置计数。侧聊已对实际安装包做纯内存 user/nano-human 对照，实施阶段补 runtime 回归。

## 根因

refactor-581 原意是使用未修改 DSH 的原生 loop、工具与 Skill，保留 Nano 的可信身份、来源、审批及产品路由边界（历史 design 的关键决策 3、4、6、9）。c67e07a699 首次引入 nano-human 与宿主输入映射，使身份元数据与来源 kind 耦合；后续 e8adc2784e 添加 contextEnvelope。消费者与自有 Skill 适配均围绕 nano-human 编写，未覆盖 DSH 依赖 user 的目标资格及重复计数，导致原生语义失效。

安装包 MessageSourceMap 是公开可扩展的来源联合，原生 user 不携带 Nano 身份；原生子 Agent 初始任务也可能使用 user。修复需保留宿主元数据作为 Nano 真人识别依据，不能将所有 user 无差别提升为真人授权。

原生 tool-skill 在直接 user 文本中识别空白分隔的 /name；Nano 旧入口额外接受 /skill:name 与紧贴方括号标签的 /name。常规 /name 应由原生负责，只对确有差异的旧入口与旧历史保留薄适配。live Inbox 的原始结果提取、Agent-local 待处理队列和 nano-skill 持久去重保持。

采用 Bugfix lite：单一来源映射根因，无新产品/架构设计；M1-fix 同步有限消费者并验证原生公开入口。

## 修复

- 通过公开 MessageSourceMap 增补带 Nano 身份的原生 user 联合分支；新的直接输入写 user，历史 nano-human 只读兼容。actorId/channel/messageId、contextEnvelope 和 background_returns 原样保留。
- Nano 的真人消费者同时要求原生 user 的宿主身份；原生子 Agent 的裸 user 初始任务仍是父任务。同步审批来源/路由、Workflow 显式入口及输入关联、可读历史，以及 PA 工作来源展示和 task_graph 的 source_message_id。
- 常规直接 /name 完全交给原生 tool-skill；薄适配仅覆盖 /skill:name、紧贴标签的入口和旧 pending nano-human。原生中间件可在 Nano scope 返回后追加注入，兼容层仅检测同名原生语法来抑制重复，不另加载一份原生 Skill。live Inbox 原始结果提取和 nano-skill 去重保持。
- 更新依赖旧来源名的模型夹具，使其结合宿主身份识别原生 user。Guardian 生命周期夹具关闭无关自进化，防止其将原生子任务误当真人并产生额外审查；Guardian 产品实现未改。

## 验证

修前隔离 runtime 测试确认直接输入仍落为 nano-human，原生 inline Skill 不被识别。修后实际安装的未修改 DSH 子进程通过：同一 turn 内 read → create_goal → update_goal complete（4 个 step、3 个成功工具结果）；系统/定时/其他 Agent/原生子 Agent 拒绝创建目标；新真人输入重置重复计数，系统输入继续累计。目标资格不绕过自动审查与人工拒绝。

显式 Skill 覆盖原生 /name、兼容 /skill:name、标签前缀、混合及重复语法、关闭名单、重启幂等和 legacy nano-human 原始记录保留。原生路径的 injection ID 不使用 nano-skill；Inbox 现有裁剪/三轮完成/重启去重测试保留。

- `native-human-source.test.ts`：3 项通过。
- `approval-sources.test.ts`：11 项通过，覆盖新旧真人、无身份 user、父任务、Agent/系统/定时来源。
- PA `source-provenance/global-agent/store`：62 项通过。
- `pnpm build`、`pnpm typecheck` 通过；Python 非 E2E 62 passed / 31 deselected；ruff check/format 和 docs-check 通过。

证据边界：使用真实原生 runtime、文件工具与持久化，模型输出由确定性 fixture 提供；没有声称真模型、Web/飞书/实体客户端或生产验收。独立 code review、最终 CI 与归档结果在交付前补记。
